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
"""照片堆叠检测（Stacks）：连拍 / RAW+JPG 双格式 合并浏览，绝不删除、绝不动原图。

规则（已与用户拍板）：
- 双格式栈：同目录 + 同 basename（去扩展名）的 RAW + JPG（或任意非 RAW）合并为一栈。
- 连拍栈：同目录 + 拍摄时间间隔 < BURST_GAP_SEC 秒 + 内容相似（dHash 汉明距离
  < BURST_HAMMING，区别于近似重复 dup 阈值 6）的连续若干张合并为一栈。
- 与去重严格区分：去重=可删（近似重复）；堆叠=仅合并浏览，本函数不触发任何删除，
  仅写入 photos.stack_id 与 stacks 表（元数据），不触碰文件。

代表帧：优先 JPG（兼容性好）；连拍取面积最大者；双格式取非 RAW 者。
"""

from __future__ import annotations

import logging
from datetime import datetime

from photo_manager.core.db import Database

log = logging.getLogger(__name__)

BURST_GAP_SEC = 5
BURST_HAMMING = 10  # 内容相似但非近似重复（dup 阈值 6）

# 受支持的全部相机 RAW 格式（与 scanner/extractor/clip 保持一致；用于把 RAW 与其
# JPEG 侧车归组）。含通用 .raw 以便把无规范后缀的裸 RAW 也纳入分组。
RAW_EXTS = {
    "3fr", "ari", "arw", "bay", "bmq", "cap", "cin", "cr2", "cr3", "crw",
    "dc2", "dcr", "dcs", "dng", "drf", "eip", "erf", "fff", "gpr", "iiq",
    "k25", "kdc", "mdc", "mef", "mos", "mrw", "nef", "nrw", "obm", "orf",
    "pef", "ptx", "pxn", "qtk", "raf", "raw", "rwl", "rw2", "rwz", "sr2",
    "srf", "srw", "sti", "x3f",
}


def _ext(name: str) -> str:
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def _stem(name: str) -> str:
    if "." not in name:
        return name
    return name.rsplit(".", 1)[0]


def _ts(s) -> float | None:
    if not s:
        return None
    s = str(s)[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    return None


def _hamming(a: str | None, b: str | None) -> int:
    if not a or not b:
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 999


def _area(r: dict) -> int:
    return (r.get("width") or 0) * (r.get("height") or 0)


def detect_stacks(db: Database) -> dict:
    """清空旧栈并重建。返回统计。不改变任何照片文件。"""
    conn = db.conn
    conn.execute("UPDATE photos SET stack_id = NULL WHERE stack_id IS NOT NULL")
    conn.execute("DELETE FROM stacks")

    rows = conn.execute(
        "SELECT id, folder_path, file_name, taken_at, perceptual_hash, width, height "
        "FROM photos WHERE status != 'missing'"
    ).fetchall()
    photos = [
        {
            "id": r[0], "folder": r[1] or "", "name": r[2] or "",
            "ts": _ts(r[3]), "phash": r[4], "width": r[5], "height": r[6],
        }
        for r in rows
    ]

    assigned: set[int] = set()
    stack_count = 0
    photo_count = 0

    def make_stack(member_ids: list[int], rep_id: int):
        nonlocal stack_count, photo_count
        cur = conn.execute(
            "INSERT INTO stacks(representative_photo_id) VALUES(?)", (rep_id,)
        )
        sid = cur.lastrowid
        for mid in member_ids:
            conn.execute("UPDATE photos SET stack_id=? WHERE id=?", (sid, mid))
        stack_count += 1
        photo_count += len(member_ids)

    def _commit_run(r):
        rep = max(r, key=_area)
        make_stack([x["id"] for x in r], rep["id"])
        for x in r:
            assigned.add(x["id"])

    # ---- 1) 双格式栈：同目录 + 同 stem 的 RAW+非RAW ----
    by_stem: dict[tuple[str, str], list[dict]] = {}
    for p in photos:
        key = (p["folder"], _stem(p["name"]))
        by_stem.setdefault(key, []).append(p)
    for key, group in by_stem.items():
        if len(group) < 2:
            continue
        raws = [g for g in group if _ext(g["name"]) in RAW_EXTS]
        others = [g for g in group if _ext(g["name"]) not in RAW_EXTS]
        if not raws or not others:
            continue
        # 代表帧：非 RAW（优先 JPG）；找不到则取面积最大者
        jpg = [g for g in others if _ext(g["name"]) in ("jpg", "jpeg")]
        rep = (jpg or others)[0]
        if jpg:
            rep = max(jpg, key=_area)
        members = [g["id"] for g in group]
        make_stack(members, rep["id"])
        for g in group:
            assigned.add(g["id"])

    # ---- 2) 连拍栈：同目录、时间相邻、内容相似（仅未入栈者） ----
    by_folder: dict[str, list[dict]] = {}
    for p in photos:
        if p["id"] in assigned:
            continue
        if p["ts"] is None or not p["phash"]:
            continue
        by_folder.setdefault(p["folder"], []).append(p)
    for folder, group in by_folder.items():
        group.sort(key=lambda x: x["ts"])
        run: list[dict] = []
        for i, p in enumerate(group):
            if not run:
                run.append(p)
                continue
            prev = run[-1]
            gap = p["ts"] - prev["ts"]
            similar = _hamming(p["phash"], prev["phash"]) <= BURST_HAMMING
            if 0 <= gap < BURST_GAP_SEC and similar:
                run.append(p)
            else:
                if len(run) >= 2:
                    _commit_run(run)
                run = [p]
        if len(run) >= 2:
            _commit_run(run)

    conn.commit()
    return {"stacks": stack_count, "photos": photo_count}


def stack_representatives(db: Database, limit: int, offset: int = 0) -> list[tuple]:
    """返回代表帧行（与 _photo_rows 列序一致），供 bridge 的 galleryStacks 使用。"""
    return db.conn.execute(
        "SELECT p.id, p.thumbnail_path, p.file_name, p.taken_at, p.face_count, "
        "p.has_text, p.camera_model, p.file_path, p.width, p.height, p.rating, p.flag "
        "FROM stacks s JOIN photos p ON p.id = s.representative_photo_id "
        "WHERE p.archived = 0 "
        "ORDER BY p.sort_key LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()


def stack_members(db: Database, stack_id: int) -> list[tuple]:
    return db.conn.execute(
        "SELECT p.id, p.thumbnail_path, p.file_name, p.taken_at, p.face_count, "
        "p.has_text, p.camera_model, p.file_path, p.width, p.height, p.rating, p.flag "
        "FROM photos p WHERE p.stack_id = ? AND p.archived = 0 ORDER BY p.sort_key",
        (stack_id,),
    ).fetchall()


def stack_count(db: Database) -> int:
    return db.conn.execute("SELECT COUNT(*) FROM stacks").fetchone()[0]
