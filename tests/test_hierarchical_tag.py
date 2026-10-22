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
"""层级标签（hierarchical tag）回归测试。

层级标签采用路径式（/ 分隔），与扁平标签完全向后兼容：
- 搜索 tag:X 匹配 X 本身、其子孙 X/...（前缀），并兼容旧式模糊包含（%X%）。
- 浏览 tagPhotos(X) 含子孙（精确 + 前缀）。
- 重命名/合并路径感知：重命名节点 X 会连带其子孙 X/...。

本测试覆盖 search 层（纯逻辑，不需 Qt）。tagTree / tagPhotos / rename 的
集成验证见 tools/gui_check.py（B 层，已有 Qt 运行环境）。
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


def _tag(db: Database, pid: int, tag: str):
    db.conn.execute(
        "INSERT OR IGNORE INTO photo_tags(photo_id, tag) VALUES (?,?)", (pid, tag))


class TestHierarchicalTag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "htag.db").connect()
        self.a = _add(self.db, file_name="a.jpg", taken_at="2020-01-01T10:00:00")
        self.b = _add(self.db, file_name="b.jpg", taken_at="2020-02-01T10:00:00")
        self.c = _add(self.db, file_name="c.jpg", taken_at="2020-03-01T10:00:00")
        self.d = _add(self.db, file_name="d.jpg", taken_at="2020-04-01T10:00:00")
        # 层级结构：
        #   a: 旅行, 旅行/国内, 旅行/国内/北京
        #   b: 旅行, 北京
        #   c: 旅行/国内/上海
        #   d: 美食
        _tag(self.db, self.a, "旅行")
        _tag(self.db, self.a, "旅行/国内")
        _tag(self.db, self.a, "旅行/国内/北京")
        _tag(self.db, self.b, "旅行")
        _tag(self.db, self.b, "北京")
        _tag(self.db, self.c, "旅行/国内/上海")
        _tag(self.db, self.d, "美食")
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _ids(self, q):
        return {r["id"] for r in PhotoSearch(self.db).query(q, limit=100)}

    # ---- 搜索：父节点匹配其所有子孙 ----
    def test_search_parent_matches_descendants(self):
        ids = self._ids("tag:旅行")
        self.assertEqual(ids, {self.a, self.b, self.c})
        self.assertNotIn(self.d, ids)

    def test_search_leaf_node(self):
        # 精确 北京(b) + 模糊 %北京% 命中 旅行/国内/北京(a)
        ids = self._ids("tag:北京")
        self.assertEqual(ids, {self.a, self.b})

    def test_search_intermediate_node(self):
        ids = self._ids("tag:旅行/国内")
        self.assertEqual(ids, {self.a, self.c})

    def test_search_unrelated_exact(self):
        ids = self._ids("tag:美食")
        self.assertEqual(ids, {self.d})

    def test_search_flat_legacy_still_works(self):
        # 旧式扁平标签（无 /）仍可被精确/模糊匹配
        ids = self._ids("tag:美食")
        self.assertIn(self.d, ids)

    def test_search_negate(self):
        ids = self._ids("-tag:旅行")
        self.assertNotIn(self.a, ids)
        self.assertNotIn(self.b, ids)
        self.assertNotIn(self.c, ids)
        self.assertIn(self.d, ids)


if __name__ == "__main__":
    unittest.main()
