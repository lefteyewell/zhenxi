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
"""色标（color label）功能回归测试。

色标语义：photos.color_label ∈ {red,yellow,green,blue,purple} 或 NULL/''（无）。
仅元数据，不动原图；搜索语法 color:red / color:红 / color:none，支持 - 否定。

对照实现：
- core/db.py: photos 表新增 color_label 列（迁移）
- core/search.py: color: 语法 + COLOR_LABELS/_COLOR_ALIAS + RESULT_COLS 带 color_label
- ui/library_bridge.py: setColorLabel 批量槽 + _pack 返回 colorLabel
"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.search import COLOR_LABELS, PhotoSearch


def _add(db: Database, fname: str, taken: str, rating: int = 5) -> int:
    cur = db.conn.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, rating, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (fname, fname, "/trip", "jpg", 1, 1.0, taken, taken, 1000, 800, rating, "indexed"),
    )
    return cur.lastrowid


class TestColorLabel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "color.db").connect()
        self.a = _add(self.db, "a.jpg", "2020-01-01T10:00:00")
        self.b = _add(self.db, "b.jpg", "2020-02-01T10:00:00")
        self.c = _add(self.db, "c.jpg", "2020-03-01T10:00:00")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    # ---- 迁移 / 默认值 ----
    def test_color_label_column_exists(self):
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(photos)")}
        self.assertIn("color_label", cols)

    def test_default_is_null(self):
        n = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE color_label IS NOT NULL"
            " AND color_label != ''").fetchone()[0]
        self.assertEqual(n, 0)

    # ---- 合法值集合 ----
    def test_color_labels_defined(self):
        self.assertEqual(set(COLOR_LABELS),
                         {"red", "yellow", "green", "blue", "purple"})

    # ---- 搜索：英文键 ----
    def test_search_color_english(self):
        self.db.conn.execute("UPDATE photos SET color_label='red' WHERE id=?", (self.a,))
        self.db.conn.commit()
        ids = {r["id"] for r in PhotoSearch(self.db).query("color:red", limit=100)}
        self.assertEqual(ids, {self.a})

    # ---- 搜索：中文别名（红→red）----
    def test_search_color_chinese_alias(self):
        self.db.conn.execute("UPDATE photos SET color_label='blue' WHERE id=?", (self.b,))
        self.db.conn.commit()
        ids = {r["id"] for r in PhotoSearch(self.db).query("color:蓝", limit=100)}
        self.assertEqual(ids, {self.b})

    # ---- 搜索：none = 未打色标 ----
    def test_search_color_none(self):
        self.db.conn.execute("UPDATE photos SET color_label='green' WHERE id=?", (self.a,))
        self.db.conn.commit()
        ids = {r["id"] for r in PhotoSearch(self.db).query("color:none", limit=100)}
        self.assertEqual(ids, {self.b, self.c})

    # ---- 搜索：否定 ----
    def test_search_color_negate(self):
        self.db.conn.execute("UPDATE photos SET color_label='purple' WHERE id=?", (self.a,))
        self.db.conn.commit()
        ids = {r["id"] for r in PhotoSearch(self.db).query("-color:purple", limit=100)}
        self.assertEqual(ids, {self.b, self.c})

    # ---- 搜索：非法值返回空 ----
    def test_search_color_invalid(self):
        res = PhotoSearch(self.db).query("color:notacolor", limit=100)
        self.assertEqual(res, [])

    # ---- 与其他条件组合 ----
    def test_search_color_combined(self):
        self.db.conn.execute("UPDATE photos SET color_label='red' WHERE id=?", (self.a,))
        self.db.conn.execute("UPDATE photos SET color_label='red' WHERE id=?", (self.b,))
        self.db.conn.commit()
        ids = {r["id"] for r in
               PhotoSearch(self.db).query("color:red date:2020-01", limit=100)}
        self.assertEqual(ids, {self.a})


if __name__ == "__main__":
    unittest.main()
