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
"""归档（archive）功能回归测试。

归档语义：archived=1 的照片从主时间轴/搜索默认隐藏，仅归档视图或显式
archived:yes / flag:archive 才可见；绝不删除、不改原图。

对照实现：
- core/db.py: photos 表新增 archived 列（迁移 + 索引）
- core/search.py: 默认排除归档；archived:/flag:archive 语法
- ui/library_bridge.py: _photo_rows 及各浏览查询加 archived=0
"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.search import PhotoSearch


def _add(db: Database, **kw) -> int:
    c = db.conn
    fname = kw["file_name"]
    ext = kw.get("ext") or fname.rsplit(".", 1)[-1].lower()
    cur = c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, rating, archived, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            kw.get("file_path", fname),
            fname,
            kw.get("folder_path", "/trip"),
            ext,
            kw.get("file_size", 1),
            kw.get("file_mtime", 1.0),
            kw.get("taken_at", "2020-06-15T10:00:00"),
            kw.get("sort_key", kw.get("taken_at", "2020-06-15T10:00:00")),
            kw.get("width", 1000),
            kw.get("height", 800),
            kw.get("rating", 0),
            kw.get("archived", 0),
            kw.get("status", "indexed"),
        ),
    )
    return cur.lastrowid


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "archive.db").connect()
        # 三张照片，均评级 5（便于用 rating: 语法做确定性匹配）
        self.a = _add(self.db, file_name="a.jpg", taken_at="2020-01-01T10:00:00", rating=5)
        self.b = _add(self.db, file_name="b.jpg", taken_at="2020-02-01T10:00:00", rating=5)
        self.c = _add(self.db, file_name="c.jpg", taken_at="2020-03-01T10:00:00", rating=5)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    # ---- 迁移 / 列 ----
    def test_archived_column_exists(self):
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(photos)")}
        self.assertIn("archived", cols)

    def test_default_archived_zero(self):
        n = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE archived = 1").fetchone()[0]
        self.assertEqual(n, 0)

    # ---- 主网格查询排除归档（与 bridge.photos 同构）----
    def test_main_grid_excludes_archived(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        ids = {r[0] for r in self.db.conn.execute(
            "SELECT id FROM photos WHERE status != 'missing' AND archived = 0")}
        self.assertNotIn(self.b, ids)
        self.assertIn(self.a, ids)
        self.assertIn(self.c, ids)

    # ---- 归档视图查询 ----
    def test_archived_photos_query(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        rows = self.db.conn.execute(
            "SELECT id FROM photos WHERE status != 'missing' AND archived = 1").fetchall()
        self.assertEqual({r[0] for r in rows}, {self.b})

    # ---- 时间线排除归档（与 bridge.timeline 同构）----
    def test_timeline_excludes_archived(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        n = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE status != 'missing' AND archived = 0"
            " AND taken_at IS NOT NULL AND taken_at != ''").fetchone()[0]
        self.assertEqual(n, 2)

    # ---- 搜索：默认排除，显式语法可见 ----
    def test_search_excludes_archived_by_default(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        res = PhotoSearch(self.db).query("rating:>=1", limit=100)
        ids = {r["id"] for r in res}
        self.assertNotIn(self.b, ids)
        self.assertIn(self.a, ids)
        self.assertIn(self.c, ids)

    def test_search_archived_yes(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        res = PhotoSearch(self.db).query("rating:>=1 archived:yes", limit=100)
        ids = {r["id"] for r in res}
        self.assertEqual(ids, {self.b})

    def test_search_flag_archive_alias(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        res = PhotoSearch(self.db).query("rating:>=1 flag:archive", limit=100)
        ids = {r["id"] for r in res}
        self.assertEqual(ids, {self.b})

    def test_search_archived_no(self):
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.b,))
        self.db.conn.commit()
        res = PhotoSearch(self.db).query("rating:>=1 archived:no", limit=100)
        ids = {r["id"] for r in res}
        self.assertNotIn(self.b, ids)
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
