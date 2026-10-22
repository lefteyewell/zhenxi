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
"""双机元数据同步：导出/导入人工整理结果（人物命名、人脸归属、事件命名、照片标签）。

照片文件本体由外部工具（rsync / robocopy）在两机间同步（路径一致）；
本模块只交换"人工标注"元数据，以 file_path 为关联键，导入时按 bbox 匹配人脸。
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from photo_manager.core.backup import backup_db
from photo_manager.core.db import Database

log = logging.getLogger(__name__)

EXPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    name       TEXT PRIMARY KEY,
    face_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS face_assign (
    photo_path  TEXT NOT NULL,
    bbox        TEXT NOT NULL,
    person_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    start_at   TEXT,
    end_at     TEXT,
    title      TEXT,
    center_lat REAL,
    center_lon REAL
);
CREATE TABLE IF NOT EXISTS photo_tags (
    photo_path TEXT NOT NULL,
    tag        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photo_mark (
    photo_path TEXT PRIMARY KEY,
    rating     INTEGER NOT NULL DEFAULT 0,
    flag       TEXT NOT NULL DEFAULT ''
);
"""


class MetadataSync:
    """导出 / 导入元数据包（SQLite 文件）。"""

    def __init__(self, db: Database):
        self.db = db

    # ---------- 导出 ----------
    def export(self, out_path: str | Path) -> dict:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        c = self.db.conn
        dst = sqlite3.connect(str(out))
        try:
            dst.executescript(EXPORT_SCHEMA)
            dst.executescript(
                "CREATE INDEX IF NOT EXISTS idx_fa_path ON face_assign(photo_path);"
                "CREATE INDEX IF NOT EXISTS idx_pt_path ON photo_tags(photo_path);"
            )
            persons = c.execute(
                "SELECT name, face_count FROM persons"
                " WHERE name IS NOT NULL AND name != ''"
            ).fetchall()
            assigns = c.execute(
                "SELECT p.file_path, f.bbox, pe.name FROM faces f"
                " JOIN photos p ON p.id = f.photo_id"
                " JOIN persons pe ON pe.id = f.person_id"
                " WHERE f.person_id IS NOT NULL AND pe.name IS NOT NULL AND pe.name != ''"
            ).fetchall()
            events = c.execute(
                "SELECT start_at, end_at, title, center_lat, center_lon FROM events"
                " WHERE title IS NOT NULL AND title != ''"
            ).fetchall()
            tags = c.execute(
                "SELECT p.file_path, pt.tag FROM photo_tags pt"
                " JOIN photos p ON p.id = pt.photo_id"
            ).fetchall()
            marks = c.execute(
                "SELECT file_path, rating, flag FROM photos"
                " WHERE status != 'missing' AND (rating > 0 OR flag != '')"
            ).fetchall()
            with dst:
                dst.executemany(
                    "INSERT INTO persons(name, face_count) VALUES (?,?)", persons
                )
                dst.executemany(
                    "INSERT INTO face_assign(photo_path, bbox, person_name)"
                    " VALUES (?,?,?)", assigns
                )
                dst.executemany(
                    "INSERT INTO events(start_at, end_at, title, center_lat, center_lon)"
                    " VALUES (?,?,?,?,?)", events
                )
                dst.executemany(
                    "INSERT INTO photo_tags(photo_path, tag) VALUES (?,?)", tags
                )
                dst.executemany(
                    "INSERT INTO photo_mark(photo_path, rating, flag) VALUES (?,?,?)", marks
                )
            stats = {
                "persons": len(persons),
                "face_assign": len(assigns),
                "events": len(events),
                "photo_tags": len(tags),
                "photo_mark": len(marks),
            }
        finally:
            dst.close()
        stats["file"] = str(out)
        stats["size_kb"] = out.stat().st_size // 1024
        return stats

    # ---------- 导入 ----------
    def import_from(self, src_path: str | Path) -> dict:
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"元数据包不存在: {src}")
        backup_db(self.db)  # 导入前自动备份，失败可回滚
        c = self.db.conn
        s = sqlite3.connect(str(src))
        stats = {"persons": 0, "face_assign": 0, "events": 0, "photo_tags": 0,
                 "photo_mark": 0, "matched_faces": 0, "unmatched_photos": 0}
        try:
            with c:
                # 1) 人物：UPSERT（保留本地已有人物的 face_count 更新）
                for (name, fc) in s.execute("SELECT name, face_count FROM persons"):
                    c.execute(
                        "INSERT INTO persons(name, face_count) VALUES (?,?) "
                        "ON CONFLICT(name) DO UPDATE SET face_count=excluded.face_count",
                        (name, fc),
                    )
                    stats["persons"] += 1

                # 2) 人脸归属：按 file_path + bbox 匹配
                for (path, bbox, pname) in s.execute(
                    "SELECT photo_path, bbox, person_name FROM face_assign"
                ):
                    row = c.execute(
                        "SELECT f.id, pe.id FROM faces f"
                        " JOIN photos p ON p.id = f.photo_id"
                        " LEFT JOIN persons pe ON pe.name = ?"
                        " WHERE p.file_path = ? AND f.bbox = ?",
                        (pname, path, bbox),
                    ).fetchone()
                    if row:
                        c.execute("UPDATE faces SET person_id=? WHERE id=?", (row[1], row[0]))
                        stats["matched_faces"] += 1
                        stats["face_assign"] += 1
                    else:
                        stats["unmatched_photos"] += 1

                # 3) 事件命名：按时间窗口匹配（start_at 相同 + end_at 允许小偏差）
                for (start, end, title, lat, lon) in s.execute(
                    "SELECT start_at, end_at, title, center_lat, center_lon FROM events"
                ):
                    row = c.execute(
                        "SELECT id FROM events WHERE start_at = ?", (start,)
                    ).fetchone()
                    if row:
                        c.execute(
                            "UPDATE events SET title=?, end_at=?, center_lat=?, center_lon=?"
                            " WHERE id=?",
                            (title, end, lat, lon, row[0]),
                        )
                    stats["events"] += 1

                # 4) 照片标签：按 file_path 匹配（仅覆盖已导入的照片）
                for (path, tag) in s.execute("SELECT photo_path, tag FROM photo_tags"):
                    row = c.execute(
                        "SELECT id FROM photos WHERE file_path=?", (path,)
                    ).fetchone()
                    if row:
                        c.execute(
                            "INSERT INTO photo_tags(photo_id, tag) VALUES (?,?) "
                            "ON CONFLICT(photo_id, tag) DO NOTHING",
                            (row[0], tag),
                        )
                        stats["photo_tags"] += 1
                    else:
                        stats["unmatched_photos"] += 1

                # 5) 评级/旗标：按 file_path 匹配（仅覆盖已导入的照片）
                for (path, rating, flag) in s.execute(
                    "SELECT photo_path, rating, flag FROM photo_mark"
                ):
                    row = c.execute(
                        "SELECT id FROM photos WHERE file_path=?", (path,)
                    ).fetchone()
                    if row:
                        c.execute(
                            "UPDATE photos SET rating=?, flag=? WHERE id=?",
                            (rating, flag, row[0]),
                        )
                        stats["photo_mark"] += 1
        finally:
            s.close()
        stats["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return stats
