# -*- coding: utf-8 -*-
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
"""阶段 3 测试：元数据同步回路 / 重复检测 / 高级搜索 / 备份恢复。"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from photo_manager.core.backup import backup_db, restore_db
from photo_manager.core.db import Database
from photo_manager.core.duplicates import DuplicateScanner
from photo_manager.core.search import PhotoSearch
from photo_manager.core.sync import MetadataSync


def _make_db(root, name="lib.db"):
    db = Database(os.path.join(root, name)).connect()
    return db


def _add_photo(db, file_path, name, folder="test_dir", taken="2025-03-02T10:00:00",
               camera="Canon EOS R5", make="Canon", width=4000, height=3000,
               lat=None, lon=None, face_count=0, thumb=None, ext=".jpg"):
    c = db.conn
    c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, camera_make, camera_model, width, height,"
        " gps_lat, gps_lon, face_count, status, thumbnail_path)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (file_path, name, folder, ext, 1000, 100.0, taken, taken or "",
         make, camera, width, height, lat, lon, face_count, "indexed", thumb),
    )
    return c.execute("SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]


def _make_thumb(path, seed, size=(200, 150)):
    import random

    os.makedirs(os.path.dirname(path), exist_ok=True)
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            px[x, y] = (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
    img.save(path, "JPEG")


class TestMetadataSync(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_sync_")
        self.db = _make_db(self.root)
        self.p1 = _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg")
        self.p2 = _add_photo(self.db, os.path.join(self.root, "b.jpg"), "b.jpg")
        c = self.db.conn
        c.execute("INSERT INTO persons(name, face_count) VALUES ('张三', 2)")
        pid = c.execute("SELECT id FROM persons WHERE name='张三'").fetchone()[0]
        c.execute("INSERT INTO faces(photo_id, bbox, descriptor, person_id) VALUES (?,?,?,?)",
                  (self.p1, "10,10,50,50", b"\x00" * 128, pid))
        c.execute("INSERT INTO events(start_at, end_at, title, center_lat, center_lon)"
                  " VALUES ('2025-03-02T10:00:00','2025-03-02T12:00:00','会议',39.9,116.3)")
        c.execute("INSERT INTO photo_tags(photo_id, tag) VALUES (?, '重要')", (self.p1,))
        c.commit()
        self.meta = os.path.join(self.root, "meta.meta.db")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_export_import_roundtrip(self):
        stats = MetadataSync(self.db).export(self.meta)
        self.assertEqual(stats["persons"], 1)
        self.assertEqual(stats["face_assign"], 1)
        self.assertEqual(stats["events"], 1)
        self.assertEqual(stats["photo_tags"], 1)

        # 模拟第二台机器：独立库（同一批照片，事件聚类结果已在本地生成）
        db2 = _make_db(self.root, "lib2.db")
        p1b = _add_photo(db2, os.path.join(self.root, "a.jpg"), "a.jpg")
        c2 = db2.conn
        c2.execute("INSERT INTO faces(photo_id, bbox, descriptor) VALUES (?,?,?)",
                   (p1b, "10,10,50,50", b"\x00" * 128))
        c2.execute("INSERT INTO events(start_at, end_at, title)"
                   " VALUES ('2025-03-02T10:00:00','2025-03-02T12:00:00','未命名')")
        # 本机已有不同整理：错误人物名
        c2.execute("INSERT INTO persons(name, face_count) VALUES ('张三（误）', 1)")
        wrong = c2.execute("SELECT id FROM persons").fetchone()[0]
        c2.execute("UPDATE faces SET person_id=? WHERE photo_id=?", (wrong, p1b))
        c2.commit()

        stats2 = MetadataSync(db2).import_from(self.meta)
        self.assertEqual(stats2["matched_faces"], 1)
        self.assertEqual(stats2["unmatched_photos"], 0)
        # 人脸挂到正确人物（按名字新建）
        row = c2.execute(
            "SELECT pe.name FROM faces f JOIN persons pe ON pe.id=f.person_id"
            " WHERE f.photo_id=?", (p1b,)
        ).fetchone()
        self.assertEqual(row[0], "张三")
        # 事件标题覆盖
        self.assertEqual(
            c2.execute("SELECT title FROM events WHERE start_at='2025-03-02T10:00:00'")
            .fetchone()[0], "会议")
        # 标签传播
        self.assertEqual(
            c2.execute("SELECT COUNT(*) FROM photo_tags").fetchone()[0], 1)
        # 导入前自动备份了
        self.assertTrue(os.path.exists(os.path.join(self.root, "backups")))
        db2.close()

    def test_import_backup_created(self):
        MetadataSync(self.db).export(self.meta)
        self.assertFalse(os.path.exists(os.path.join(self.root, "backups")))
        MetadataSync(self.db).import_from(self.meta)
        backups = os.listdir(os.path.join(self.root, "backups"))
        self.assertEqual(len(backups), 1)


class TestDuplicates(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_dup_")
        self.db = _make_db(self.root)
        self.thumbs = os.path.join(self.root, "thumbs")
        os.makedirs(self.thumbs)
        # 三张相同内容 + 两张不同内容
        t1 = os.path.join(self.thumbs, "t1.jpg")
        t2 = os.path.join(self.thumbs, "t2.jpg")
        t3 = os.path.join(self.thumbs, "t3.jpg")
        t4 = os.path.join(self.thumbs, "t4.jpg")
        t5 = os.path.join(self.thumbs, "t5.jpg")
        _make_thumb(t1, 1)
        _make_thumb(t2, 1)
        _make_thumb(t3, 1)
        _make_thumb(t4, 2)
        _make_thumb(t5, 3)
        self.id1 = _add_photo(self.db, os.path.join(self.root, "1.jpg"), "1.jpg", thumb=t1,
                              taken="2025-01-01T10:00:00")
        self.id2 = _add_photo(self.db, os.path.join(self.root, "2.jpg"), "2.jpg", thumb=t2,
                              taken="2025-01-02T10:00:00")
        self.id3 = _add_photo(self.db, os.path.join(self.root, "3.jpg"), "3.jpg", thumb=t3,
                              taken="2025-01-03T10:00:00")
        _add_photo(self.db, os.path.join(self.root, "4.jpg"), "4.jpg", thumb=t4)
        _add_photo(self.db, os.path.join(self.root, "5.jpg"), "5.jpg", thumb=t5)
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_hashes_and_groups(self):
        s = DuplicateScanner(self.db)
        st = s.compute_hashes()
        self.assertEqual(st["ok"], 5)
        self.assertEqual(st["fail"], 0)
        groups = s.find_duplicates(dist=6)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["duplicates"], 2)
        # 主照片 = 分辨率/时间最优（此处相同，取首张）
        self.assertTrue(groups[0]["members"][0]["primary"])
        self.assertEqual(len([m for m in groups[0]["members"] if not m["primary"]]), 2)


class TestAdvancedSearch(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_search_")
        self.db = _make_db(self.root)
        self.p1 = _add_photo(self.db, os.path.join(self.root, "camera", "IMG_0001.JPG"),
                             "IMG_0001.JPG", folder="camera", taken="2025-03-02T10:00:00",
                             camera="Canon EOS R5", lat=39.9, lon=116.3, face_count=2)
        self.p2 = _add_photo(self.db, os.path.join(self.root, "beach", "IMG_0002.JPG"),
                             "IMG_0002.JPG", folder="beach", taken="2025-06-15T08:00:00",
                             camera="A7RM5", make="Sony", lat=31.2, lon=121.5, face_count=0)
        self.p3 = _add_photo(self.db, os.path.join(self.root, "camera", "RAW_0003.CR3"),
                             "RAW_0003.CR3", folder="camera", taken="2025-03-02T18:00:00",
                             camera="Canon EOS R5", lat=39.9, lon=116.31, face_count=1,
                             ext=".CR3")
        c = self.db.conn
        c.execute("INSERT INTO photo_tags(photo_id, tag) VALUES (?, '重要')", (self.p1,))
        c.execute("INSERT INTO photo_tags(photo_id, tag) VALUES (?, '风景')", (self.p2,))
        c.execute("INSERT INTO persons(name, face_count) VALUES ('张三', 1)")
        pid = c.execute("SELECT id FROM persons WHERE name='张三'").fetchone()[0]
        c.execute("INSERT INTO faces(photo_id, bbox, descriptor, person_id) VALUES (?,?,?,?)",
                  (self.p3, "1,1,20,20", b"\x01" * 128, pid))
        c.execute("INSERT INTO events(start_at, end_at, title)"
                  " VALUES ('2025-03-02T10:00:00','2025-03-02T20:00:00','会议')")
        c.commit()
        self.s = PhotoSearch(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def _ids(self, q):
        return {h["id"] for h in self.s.query(q)}

    def test_field_filters(self):
        self.assertEqual(self._ids("tag:重要"), {self.p1})
        self.assertEqual(self._ids("person:张三"), {self.p3})
        self.assertEqual(self._ids("camera:canon"), {self.p1, self.p3})
        self.assertEqual(self._ids("folder:beach"), {self.p2})
        self.assertEqual(self._ids("ext:cr3"), {self.p3})
        self.assertEqual(self._ids("date:2025-03-02"), {self.p1, self.p3})
        self.assertEqual(self._ids("faces:2"), {self.p1})
        self.assertEqual(self._ids("faces:0"), {self.p2})

    def test_date_range_and_gps(self):
        self.assertEqual(self._ids("dates:2025-06-01..2025-06-30"), {self.p2})
        # 距 (39.9, 116.3) 1km 内：p1 与 p3（约 0.9km），p2 远隔千公里
        self.assertEqual(self._ids("gps:39.9,116.3,1"), {self.p1, self.p3})

    def test_or_and_not(self):
        self.assertEqual(self._ids("tag:重要 OR tag:风景"), {self.p1, self.p2})
        self.assertEqual(self._ids("-tag:重要"), {self.p2, self.p3})
        self.assertEqual(self._ids("folder:camera -faces:0"), {self.p1, self.p3})
        self.assertEqual(self._ids("IMG OR RAW"), {self.p1, self.p2, self.p3})

    def test_plain_word(self):
        self.assertEqual(self._ids("canon"), {self.p1, self.p3})
        self.assertEqual(self._ids("年会"), set())


class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_bak_")
        self.db = _make_db(self.root)
        self.p1 = _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg")
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_backup_and_restore(self):
        target = backup_db(self.db, os.path.join(self.root, "bk"))
        self.assertTrue(target.exists())
        self.db.close()
        # 破坏当前库，然后恢复
        db2 = _make_db(self.root, "lib.db")
        db2.conn.execute("DELETE FROM photos")
        db2.conn.commit()
        db2.close()
        restore_db(os.path.join(self.root, "lib.db"), target)
        db3 = Database(os.path.join(self.root, "lib.db")).connect()
        n = db3.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        self.assertEqual(n, 1)
        db3.close()


if __name__ == "__main__":
    unittest.main()
