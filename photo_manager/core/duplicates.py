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
"""重复照片检测：dHash 感知哈希 + 汉明距离（基于已有缩略图，快且离线）。

策略：64-bit dHash；按前 16 bit 分桶预筛，桶内两两汉明距离 <= dist 判定为重复。
只报告不删除（程序内无删除功能）。
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ProcessPoolExecutor

from photo_manager.core.db import Database
from photo_manager.core.system import analysis_workers

log = logging.getLogger(__name__)

HASH_BITS = 64
BUCKET_BITS = 16


def _dhash_from_path(payload: tuple[str, str]) -> tuple[str, int, str]:
    """worker 进程内计算单张照片的 dHash（返回 file_path, photo_id, hash）。"""
    photo_id, thumb_path = payload
    if not thumb_path:
        return photo_id, 0, ""
    import cv2
    import numpy as np

    # cv2.imread 无法读取非 ASCII 路径（中文系统），用二进制读 + imdecode
    img = cv2.imdecode(np.fromfile(thumb_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return photo_id, 0, ""
    small = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
    # dHash：比较相邻像素亮度差，64 bit
    bits = (small[:, 1:] > small[:, :8]).flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return photo_id, 64, f"{h:016x}"


class DuplicateScanner:
    def __init__(self, db: Database):
        self.db = db

    def compute_hashes(
        self, limit: int | None = None, workers: int = 0,
        progress_cb=None, cancel=None,
    ) -> dict:
        """为缺 hash 的照片计算 perceptual_hash（基于缩略图）。"""
        # 0.6.8：任务期读写全部走独立连接，不再碰 UI 共享连接（消除
        # 批量分析时 UI 查询在共享连接上排队导致的界面无响应）
        import sqlite3

        conn = sqlite3.connect(self.db.path, timeout=10)
        rows = conn.execute(
            "SELECT id, thumbnail_path FROM photos"
            " WHERE (perceptual_hash IS NULL OR perceptual_hash='')"
            " AND thumbnail_path IS NOT NULL AND thumbnail_path != ''"
            " AND status != 'missing' AND archived = 0"
            + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()
        # 0.5.51：thumbnail_path 可能是相对路径（thumbs/…），worker 进程的
        # CWD 不确定，必须先按 DB 目录解析成绝对路径再分发
        from photo_manager.core.paths import resolve_data_path

        rows = [(i, resolve_data_path(self.db.path, t)) for i, t in rows]
        total = len(rows)
        n_ok = n_fail = 0
        if total == 0:
            conn.close()
            return {"total": 0, "ok": 0, "fail": 0, "sec": 0.0}
        t0 = time.perf_counter()
        nproc = workers or analysis_workers()
        if nproc <= 1:
            results = [_dhash_from_path((str(i), t)) for i, t in rows]
        else:
            with ProcessPoolExecutor(max_workers=nproc) as ex:
                results = list(ex.map(
                    _dhash_from_path, [(str(i), t) for i, t in rows]
                ))
        # Linux 下 fork 的 worker 会继承并关闭共享连接，导致父连接失效
        try:
            for i, (pid, bits, h) in enumerate(results, 1):
                if cancel and cancel():
                    break
                if bits == HASH_BITS:
                    conn.execute(
                        "UPDATE photos SET perceptual_hash=? WHERE id=?",
                        (h, int(pid)),
                    )
                    n_ok += 1
                else:
                    n_fail += 1
                if i % 500 == 0:
                    conn.commit()
                    if progress_cb:
                        progress_cb(i, total)
            conn.commit()
        finally:
            conn.close()
        return {"total": total, "ok": n_ok, "fail": n_fail,
                "sec": round(time.perf_counter() - t0, 2)}

    def find_duplicates(self, dist: int = 6) -> list[dict]:
        """返回重复组：按桶内汉明距离聚类（并查集），每组含 photos 列表。

        每组保留主照片（分辨率最高、拍摄时间最早），其余为重复项。
        """
        rows = self.db.conn.execute(
            "SELECT id, perceptual_hash, width, height, taken_at, file_path,"
            " file_name, thumbnail_path FROM photos"
            " WHERE perceptual_hash IS NOT NULL AND perceptual_hash != ''"
            " AND status != 'missing' AND archived = 0"
        ).fetchall()
        if not rows:
            return []
        buckets: dict[str, list] = {}
        for r in rows:
            buckets.setdefault(r[1][: BUCKET_BITS], []).append(r)

        parent = {r[0]: r[0] for r in rows}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        def hamming(a: str, b: str) -> int:
            return bin(int(a, 16) ^ int(b, 16)).count("1")

        by_id = {r[0]: r for r in rows}
        n_pairs = 0
        for bucket in buckets.values():
            if len(bucket) < 2:
                continue
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    if hamming(bucket[i][1], bucket[j][1]) <= dist:
                        union(bucket[i][0], bucket[j][0])
                        n_pairs += 1

        groups: dict[int, list] = {}
        for r in rows:
            groups.setdefault(find(r[0]), []).append(r)

        out = []
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda m: (-(m[2] or 0) * (m[3] or 0), m[4] or ""))
            out.append({
                "duplicates": len(members) - 1,
                "members": [
                    {
                        "id": m[0], "hash": m[1], "width": m[2], "height": m[3],
                        "takenAt": (m[4] or "").replace("T", " ")[:16],
                        "path": m[5], "name": m[6], "thumb": m[7], "primary": i == 0,
                    }
                    for i, m in enumerate(members)
                ],
            })
        out.sort(key=lambda g: -g["duplicates"])
        return out
