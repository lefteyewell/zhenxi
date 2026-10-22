# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""人脸聚类归一化：余弦相似度 + 并查集连通分量 → persons。"""
from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np

from photo_manager.core.db import Database

log = logging.getLogger(__name__)

# 真实照片实测：同人余弦相似度 0.5~0.9、跨人 0.05~0.15，取 0.5 可分且不漏。
# 0.637 原值对应 SFace 论文余弦距离 0.363，对真实照片过于严格，导致同一人分成多人。
DEFAULT_SIM_THRESHOLD = 0.5
MAX_GLOBAL = 30000  # 超过后按事件域聚类（内存/耗时保护）


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_matrix(descriptors: np.ndarray, threshold: float, progress_cb=None) -> list[int]:
    """返回每张脸的簇代表索引。分块矩阵乘法控内存。"""
    n = descriptors.shape[0]
    uf = _UnionFind(n)
    norm = descriptors / np.linalg.norm(descriptors, axis=1, keepdims=True)
    chunk = 1024
    done = 0
    for start in range(0, n, chunk):
        block = norm[start:start + chunk] @ norm.T
        np.fill_diagonal(block, 0.0)
        sim = block > threshold
        rows = np.nonzero(sim.any(axis=1))[0]
        for r in rows:
            idx = np.nonzero(sim[r])[0]
            for j in idx:
                uf.union(start + r, int(j))
        done += block.shape[0]
        if progress_cb:
            progress_cb(done, n)
    return [uf.find(i) for i in range(n)]


class FaceClusterer:
    def __init__(self, db: Database, threshold: float = DEFAULT_SIM_THRESHOLD):
        self.db = db
        self.threshold = threshold

    def run(self, progress_cb: Callable[[int, int], None] | None = None) -> dict:
        t0 = time.perf_counter()
        faces = self.db.conn.execute(
            "SELECT f.id, f.descriptor, ep.event_id FROM faces f"
            " LEFT JOIN event_photos ep ON ep.photo_id = f.photo_id"
        ).fetchall()
        if not faces:
            return {"faces": 0, "persons": 0, "scoped": False, "sec": 0.0}

        n = len(faces)
        dim = 128  # SFace 固定 128 维
        expect = dim * 4
        # 逐条校验：只比对总长度不够严谨 —— 个别 descriptor 偏短/偏长时总长仍可能
        # 达标，reshape 会"成功"但数据整段错位，聚类结果全错且无任何报错；
        # descriptor 为 NULL 时 b"".join 还会直接抛 TypeError。
        bad = [r[0] for r in faces if r[1] is None or len(r[1]) != expect]
        if bad:
            log.warning("人脸特征异常，跳过聚类：%d 条（示例 id=%s）",
                        len(bad), bad[:5])
            return {"faces": 0, "persons": 0, "scoped": False,
                    "sec": round(time.perf_counter() - t0, 3),
                    "error": f"人脸特征缺失或长度异常（{len(bad)} 条），跳过聚类"}
        raw = b"".join(r[1] for r in faces)
        descriptors = np.frombuffer(raw, dtype=np.float32).reshape(n, dim)

        scoped = n > MAX_GLOBAL
        assign: list[int] = [None] * n  # noqa: RUF012
        if scoped:
            scope_map: dict[int, list[int]] = {}
            for i, f in enumerate(faces):
                scope_map.setdefault(f[2] or -1, []).append(i)
            for scope, idxs in scope_map.items():
                sub = descriptors[idxs]
                reps = cluster_matrix(sub, self.threshold)
                root_rep: dict[int, int] = {}
                for local_i, rep in enumerate(reps):
                    global_i = idxs[local_i]
                    if rep not in root_rep:
                        root_rep[rep] = global_i
                    assign[global_i] = root_rep[rep]
        else:
            assign = cluster_matrix(descriptors, self.threshold, progress_cb)

        rep_to_person: dict[int, int] = {}
        person_rows = []
        conn = self.db.conn
        # 聚类会清空 persons 重建。若不保留，用户已命名的人物（如"王老师"）会被
        # 全部抹掉 —— 先记下每张脸当前的人物名，聚类后按簇内多数票继承回来。
        old_name: dict[int, str] = {}
        try:
            for fid, nm in conn.execute(
                    "SELECT f.id, p.name FROM faces f"
                    " JOIN persons p ON p.id = f.person_id"
                    " WHERE p.name IS NOT NULL AND p.name != ''"):
                old_name[fid] = nm
        except Exception as e:  # noqa: BLE001
            log.warning("读取既有命名字段失败（忽略，按全新聚类处理）：%s", e)
        conn.execute("DELETE FROM persons")
        from collections import Counter

        rep_counts = Counter(assign)
        for rep in rep_counts:
            person_rows.append(rep)
        person_map: dict[int, int] = {}
        for rep in person_rows:
            cur = conn.execute("INSERT INTO persons(name) VALUES (NULL)").lastrowid
            person_map[rep] = cur
        # 名字继承：簇内出现最多的原名 → 新人物名（persons.name 有唯一索引，
        # 重名时让先到者占用，其余留空，避免 IntegrityError 让整次聚类失败）
        used_names: set[str] = set()
        by_rep: dict[int, list[int]] = {}
        for i in range(n):
            by_rep.setdefault(assign[i], []).append(i)
        for rep, pid in person_map.items():
            names = [old_name[faces[i][0]] for i in by_rep.get(rep, [])
                     if faces[i][0] in old_name]
            if not names:
                continue
            best = Counter(names).most_common(1)[0][0]
            if best in used_names:
                continue
            try:
                conn.execute("UPDATE persons SET name=? WHERE id=?", (best, pid))
                used_names.add(best)
            except Exception as e:  # noqa: BLE001  # 唯一索引冲突等，留空即可
                log.warning("继承人物名失败 %s：%s", best, e)
        conn.executemany(
            "UPDATE faces SET person_id=?, cluster_id=? WHERE id=?",
            [(person_map[assign[i]], person_map[assign[i]], faces[i][0]) for i in range(n)],
        )
        for rep, pid in person_map.items():
            conn.execute("UPDATE persons SET face_count=? WHERE id=?", (rep_counts[rep], pid))
        conn.commit()
        return {
            "faces": n,
            "persons": len(person_map),
            "scoped": scoped,
            "sec": round(time.perf_counter() - t0, 3),
        }
