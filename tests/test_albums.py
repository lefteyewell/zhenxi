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
"""虚拟相册（albums）功能回归测试。

相册语义：只存 photos 表引用（album_photos 关联），不移动/复制/删除任何照片文件；
删除相册仅移除分组与关联记录。浏览口径排除 missing 与已归档。

对照实现：
- core/db.py: albums / album_photos 表（SCHEMA）
- core/albums.py: create/rename/delete/list/add_photos/remove_photos/album_photos/count
"""
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.albums import (add_photos, album_count, album_photos,
                                       create_album, delete_album, list_albums,
                                       remove_photos)
from photo_manager.core.db import Database


def _add(db: Database, fname: str, taken: str, **kw) -> int:
    cur = db.conn.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, width, height, status, archived)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (kw.get("file_path", fname), fname, "/trip", "jpg", 1, 1.0, taken, taken,
         1000, 800, kw.get("status", "indexed"), kw.get("archived", 0)),
    )
    return cur.lastrowid


class TestAlbums(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "albums.db").connect()
        self.p1 = _add(self.db, "p1.jpg", "2020-01-01T10:00:00")
        self.p2 = _add(self.db, "p2.jpg", "2020-02-01T10:00:00")
        self.p3 = _add(self.db, "p3.jpg", "2020-03-01T10:00:00")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _album(self, name="精选") -> int:
        aid = create_album(self.db, name)
        self.assertGreater(aid, 0)
        return aid

    # ---- 创建 ----
    def test_create_and_list(self):
        aid = self._album("旅行精选")
        rows = list_albums(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], aid)
        self.assertEqual(rows[0]["name"], "旅行精选")
        self.assertEqual(rows[0]["photoCount"], 0)

    def test_create_duplicate_name_fails(self):
        self._album("同名")
        self.assertEqual(create_album(self.db, "同名"), 0)
        self.assertEqual(len(list_albums(self.db)), 1)

    def test_create_empty_name_fails(self):
        self.assertEqual(create_album(self.db, "  "), 0)

    # ---- 加照片 / 去重 ----
    def test_add_photos_dedup(self):
        aid = self._album()
        self.assertEqual(add_photos(self.db, aid, [self.p1, self.p2]), 2)
        # 重复加入自动跳过
        self.assertEqual(add_photos(self.db, aid, [self.p2, self.p3]), 1)
        self.assertEqual(album_count(self.db, aid), 3)

    # ---- 浏览：排除 missing / 已归档 ----
    def test_album_photos_excludes_missing_archived(self):
        aid = self._album()
        add_photos(self.db, aid, [self.p1, self.p2, self.p3])
        self.db.conn.execute("UPDATE photos SET archived=1 WHERE id=?", (self.p1,))
        self.db.conn.execute("UPDATE photos SET status='missing' WHERE id=?", (self.p2,))
        self.db.conn.commit()
        rows = album_photos(self.db, aid)
        self.assertEqual([r[0] for r in rows], [self.p3])
        self.assertEqual(album_count(self.db, aid), 1)

    # ---- 移出：只删关联，照片仍在 ----
    def test_remove_photos_keeps_photo_rows(self):
        aid = self._album()
        add_photos(self.db, aid, [self.p1, self.p2])
        self.assertEqual(remove_photos(self.db, aid, [self.p1]), 1)
        self.assertEqual(album_count(self.db, aid), 1)
        # 照片本身仍存在
        n = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE id=?", (self.p1,)).fetchone()[0]
        self.assertEqual(n, 1)

    # ---- 重命名 ----
    def test_rename(self):
        aid = self._album("旧名")
        self.assertTrue(rename_ok(self.db, aid, "新名"))
        rows = list_albums(self.db)
        self.assertEqual(rows[0]["name"], "新名")

    # ---- 删除相册：关联消失，照片保留 ----
    def test_delete_album_keeps_photos(self):
        aid = self._album()
        add_photos(self.db, aid, [self.p1, self.p2])
        self.assertTrue(delete_album(self.db, aid))
        self.assertEqual(list_albums(self.db), [])
        self.assertEqual(album_count(self.db, aid), 0)
        n = self.db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        self.assertEqual(n, 3)  # 照片一张不少


def rename_ok(db, aid, name) -> bool:
    from photo_manager.core.albums import rename_album
    return rename_album(db, aid, name)


if __name__ == "__main__":
    unittest.main()
