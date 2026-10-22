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
"""场景自动标签层级化（C10）。

自动场景标签统一写在「场景/」父节点下（如「场景/海边」），与用户手打的顶层标签区分；
配合层级标签树，搜索 tag:场景 即可一次看全部场景照片。

本测试只覆盖**不依赖 CLIP 模型**的关键词兜底分支（_keyword_tags），
CLIP 零样本分支（auto_tag_clip）需要 727MB 模型，在无模型环境下安全返回 model_missing。
"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.autotag import SCENE_TAG_ROOT, _keyword_tags
from photo_manager.core.db import Database


def _add(db: Database, file_path: str, file_name: str) -> int:
    cur = db.conn.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, rating, archived, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (file_path, file_name, str(Path(file_path).parent), "jpg", 1, 1.0,
         "2020-06-15T10:00:00", "2020-06-15T10:00:00", 1000, 800, 0, 0, "indexed"),
    )
    return cur.lastrowid


class TestSceneTagRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "scene.db").connect()
        # 路径含「旅行」→ 场景/旅行；含「海边」→ 同时命中 旅行(含海边) 与 风景
        self.a = _add(self.db, "D:/photos/旅行/2025/a.jpg", "a.jpg")
        self.b = _add(self.db, "D:/photos/海边/b.jpg", "b.jpg")
        self.c = _add(self.db, "D:/photos/xyz/c.jpg", "c.jpg")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _tags(self, pid):
        return [r[0] for r in self.db.conn.execute(
            "SELECT tag FROM photo_tags WHERE photo_id=? ORDER BY tag", (pid,))]

    def test_keyword_tag_is_nested(self):
        _keyword_tags(self.db)
        self.assertIn(f"{SCENE_TAG_ROOT}/旅行", self._tags(self.a))

    def test_no_flat_duplicate(self):
        """不应再产生扁平的「旅行」标签（自动标签必须带场景根）。"""
        _keyword_tags(self.db)
        self.assertNotIn("旅行", self._tags(self.a))

    def test_other_keyword_nested(self):
        _keyword_tags(self.db)
        tags = self._tags(self.b)
        self.assertIn(f"{SCENE_TAG_ROOT}/风景", tags)
        self.assertIn(f"{SCENE_TAG_ROOT}/旅行", tags)  # 「海边」也是旅行关键词

    def test_unrelated_untagged(self):
        _keyword_tags(self.db)
        self.assertEqual(self._tags(self.c), [])

    def test_idempotent(self):
        n1 = _keyword_tags(self.db)
        n2 = _keyword_tags(self.db)
        self.assertGreater(n1, 0)
        self.assertEqual(n2, 0)

    def test_root_can_be_disabled(self):
        """root 传空串则退化为扁平标签（向后兼容）。"""
        _keyword_tags(self.db, root="")
        self.assertIn("旅行", self._tags(self.a))


if __name__ == "__main__":
    unittest.main()
