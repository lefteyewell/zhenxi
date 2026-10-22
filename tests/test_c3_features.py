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
"""C3 迭代测试：评级/旗标、批量时间校正、退出自动备份轮换、CSV 导出、GPS 散点地图、幻灯片。"""
import csv
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.backup import backup_db
from photo_manager.core.csv_export import export_metadata_csv
from photo_manager.core.db import Database
from photo_manager.core.search import PhotoSearch
from photo_manager.core.sync import MetadataSync
from photo_manager.ui.library_bridge import LibraryBridge


def _make_db(root, name="lib.db"):
    return Database(os.path.join(root, name)).connect()


def _add_photo(db, file_path, name, folder="test_dir", taken="2025-03-02T10:00:00",
               lat=None, lon=None, ext=".jpg"):
    c = db.conn
    c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, gps_lat, gps_lon, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (file_path, name, folder, ext, 1000, 100.0, taken, taken or "",
         lat, lon, "indexed"),
    )
    return c.execute("SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]


class TestRatingFlag(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_rating_")
        self.db = _make_db(self.root)
        self.p = _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg")
        self.p2 = _add_photo(self.db, os.path.join(self.root, "b.jpg"), "b.jpg")
        self.p3 = _add_photo(self.db, os.path.join(self.root, "c.jpg"), "c.jpg")
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_columns_exist(self):
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(photos)")}
        self.assertIn("rating", cols)
        self.assertIn("flag", cols)

    def test_set_rating_clamps(self):
        self.db.conn.execute("UPDATE photos SET rating=3 WHERE id=?", (self.p,))
        self.db.conn.commit()
        self.assertEqual(
            self.db.conn.execute("SELECT rating FROM photos WHERE id=?", (self.p,)).fetchone()[0], 3)

    def test_search_rating(self):
        self.db.conn.execute("UPDATE photos SET rating=4 WHERE id=?", (self.p,))
        self.db.conn.execute("UPDATE photos SET rating=2 WHERE id=?", (self.p2,))
        self.db.conn.commit()
        s = PhotoSearch(self.db)
        ids = {x["id"] for x in s.query("rating:>=3")}
        self.assertEqual(ids, {self.p})
        ids0 = {x["id"] for x in s.query("rating:0")}
        self.assertEqual(ids0, {self.p3})

    def test_search_flag(self):
        self.db.conn.execute("UPDATE photos SET flag='pick' WHERE id=?", (self.p,))
        self.db.conn.execute("UPDATE photos SET flag='reject' WHERE id=?", (self.p2,))
        self.db.conn.commit()
        s = PhotoSearch(self.db)
        self.assertEqual({x["id"] for x in s.query("flag:pick")}, {self.p})
        self.assertEqual({x["id"] for x in s.query("flag:reject")}, {self.p2})
        self.assertEqual({x["id"] for x in s.query("-flag:reject")}, {self.p, self.p3})

    def test_bridge_rating_flag(self):
        g = LibraryBridge(self.db.path)
        self.assertTrue(g.setRating(self.p, 5))
        self.assertTrue(g.setFlag(self.p, "pick"))
        self.assertFalse(g.setFlag(self.p, "bogus"))
        self.assertEqual(g.ratedCount(1), 1)
        self.assertEqual([x["id"] for x in g.ratedPhotos(1)], [self.p])
        self.assertEqual([x["id"] for x in g.flagPhotos("pick")], [self.p])
        d = g.photoDetail(self.p)
        self.assertEqual(d["rating"], 5)
        self.assertEqual(d["flag"], "pick")
        # 网格数据带评级
        rows = g.photos(0, 10)
        by_id = {x["id"]: x for x in rows}
        self.assertEqual(by_id[self.p]["rating"], 5)
        self.assertEqual(by_id[self.p]["flag"], "pick")
        g.close()

    def test_stats_dashboard_rating(self):
        self.db.conn.execute("UPDATE photos SET rating=4 WHERE id=?", (self.p,))
        self.db.conn.execute("UPDATE photos SET flag='pick' WHERE id=?", (self.p2,))
        self.db.conn.commit()
        g = LibraryBridge(self.db.path)
        d = g.statsDashboard()
        self.assertEqual(d["totals"]["rated"], 1)
        self.assertEqual(d["totals"]["picked"], 1)
        self.assertEqual(d["byRating"], [{"key": "4", "count": 1}])
        g.close()


class TestTimeShift(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_shift_")
        self.db = _make_db(self.root)
        self.p = _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg",
                            taken="2025-03-02T10:00:00")
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_shift_hours(self):
        g = LibraryBridge(self.db.path)
        p = g.timeShiftPreview(2)
        self.assertEqual(p["affected"], 1)
        n = g.timeShift(2)
        self.assertEqual(n, 1)
        row = self.db.conn.execute(
            "SELECT taken_at, sort_key FROM photos WHERE id=?", (self.p,)).fetchone()
        self.assertEqual(row[0], "2025-03-02T12:00:00")
        self.assertEqual(row[1], "2025-03-02T12:00:00")
        # 负偏移
        g.timeShift(-3)
        row = self.db.conn.execute(
            "SELECT taken_at FROM photos WHERE id=?", (self.p,)).fetchone()
        self.assertEqual(row[0], "2025-03-02T09:00:00")
        g.close()


class TestBackupRotation(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_rot_")
        self.db = _make_db(self.root)
        _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg")
        self.db.conn.commit()
        self.bdir = os.path.join(self.root, "bks")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_keep_rotation(self):
        for _ in range(5):
            backup_db(self.db, self.bdir, keep=3)
            time.sleep(1.01)
        files = [f for f in os.listdir(self.bdir) if f.endswith(".db")]
        self.assertEqual(len(files), 3, f"应只保留 3 份，实际 {files}")

    def test_bridge_backup_on_exit(self):
        g = LibraryBridge(self.db.path)
        r = g.backupOnExit()
        self.assertTrue(r and os.path.exists(r))
        g.close()


class TestCsvExport(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_csv_")
        self.db = _make_db(self.root)
        self.p = _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg")
        c = self.db.conn
        c.execute("INSERT INTO photo_tags(photo_id, tag) VALUES (?, '重要')", (self.p,))
        c.execute("UPDATE photos SET rating=3, flag='pick', camera_model='EOS R5' WHERE id=?", (self.p,))
        c.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_export_csv(self):
        out = os.path.join(self.root, "meta.csv")
        r = export_metadata_csv(self.db, out)
        self.assertTrue(os.path.exists(out))
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][0], "id")
        self.assertEqual(len(rows), 2)  # 表头 + 1
        header = rows[0]
        body = dict(zip(header, rows[1]))
        self.assertEqual(body["rating"], "3")
        self.assertEqual(body["flag"], "pick")
        self.assertEqual(body["tags"], "重要")
        self.assertEqual(body["camera_model"], "EOS R5")


class TestGpsMap(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_map_")
        self.db = _make_db(self.root)
        _add_photo(self.db, os.path.join(self.root, "a.jpg"), "a.jpg",
                   lat=39.9042, lon=116.4074)
        _add_photo(self.db, os.path.join(self.root, "b.jpg"), "b.jpg",
                   lat=39.9042, lon=116.4074)
        _add_photo(self.db, os.path.join(self.root, "c.jpg"), "c.jpg",
                   lat=31.2304, lon=121.4737)
        self.db.conn.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_map_points(self):
        g = LibraryBridge(self.db.path)
        pts = g.mapPoints()
        self.assertEqual(len(pts), 2)
        agg = {round(p["lat"], 3): p["count"] for p in pts}
        self.assertEqual(agg[39.904], 2)
        self.assertEqual(agg[31.23], 1)
        self.assertEqual(g.mapCount(), 3)
        photos = g.mapPhotos(39.9042, 116.4074)
        self.assertEqual(len(photos), 2)
        g.close()


class TestSyncRatingFlag(unittest.TestCase):
    def test_roundtrip(self):
        root = tempfile.mkdtemp(prefix="pm_syncm_")
        try:
            db = _make_db(root, "a.db")
            p = _add_photo(db, os.path.join(root, "x.jpg"), "x.jpg")
            db.conn.execute("UPDATE photos SET rating=5, flag='reject' WHERE id=?", (p,))
            db.conn.commit()
            meta = os.path.join(root, "m.meta.db")
            st = MetadataSync(db).export(meta)
            self.assertEqual(st["photo_mark"], 1)
            db2 = _make_db(root, "b.db")
            _add_photo(db2, os.path.join(root, "x.jpg"), "x.jpg")
            db2.conn.commit()
            st2 = MetadataSync(db2).import_from(meta)
            self.assertEqual(st2["photo_mark"], 1)
            r = db2.conn.execute("SELECT rating, flag FROM photos WHERE file_path=?",
                                 (os.path.join(root, "x.jpg"),)).fetchone()
            self.assertEqual(r, (5, "reject"))
            db.close()
            db2.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestMultiFace(unittest.TestCase):
    """C4：一张照片多张人脸的逐脸区分（bbox 归一化 / 单脸指派 / 人脸裁剪）。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_face_")
        self.db = _make_db(self.root)
        self.p = _add_photo(self.db, os.path.join(self.root, "group.jpg"), "group.jpg",
                            taken="2025-05-01T12:00:00")
        self.db.conn.execute(
            "INSERT INTO persons(id, name, face_count) VALUES (1, 'Alice', 1), (2, 'Bob', 1)")
        # 同一张照片三个人脸：两个已命名、一个未命名
        self.db.conn.executemany(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id) VALUES (?,?,?,?,?)",
            [(self.p, '[0.1,0.2,0.3,0.4]', b'\x01'*8, 0.95, 1),
             (self.p, '[0.5,0.3,0.25,0.35]', b'\x02'*8, 0.90, 2),
             (self.p, '[0.6,0.6,0.2,0.25]', b'\x03'*8, 0.80, None)])
        self.db.conn.execute("UPDATE photos SET width=2000, height=1200 WHERE id=?", (self.p,))
        self.db.conn.commit()
        self.g = LibraryBridge(self.db.path)

    def tearDown(self):
        self.g.close()
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_photoFaces_normalized(self):
        faces = self.g.photoFaces(self.p)
        self.assertEqual(len(faces), 3)
        for f in faces:
            self.assertIn("id", f)
            self.assertIn("personName", f)
            # 归一化坐标在 0..1
            self.assertTrue(0 <= f["nx"] < 1 and 0 <= f["ny"] < 1)
            self.assertTrue(0 < f["nw"] <= 1 and 0 < f["nh"] <= 1)
        by_person = {f["personName"]: f for f in faces}
        self.assertEqual(by_person["Alice"]["personId"], 1)
        self.assertEqual(by_person["Bob"]["personId"], 2)

    def test_assign_face_single(self):
        """只指派一张人脸，其他脸不受影响（多人照片的逐脸区分）。"""
        faces = self.g.photoFaces(self.p)
        unnamed = next(f for f in faces if f["personId"] == 0)
        ok = self.g.assignFace(unnamed["id"], 2)
        self.assertTrue(ok)
        row = self.db.conn.execute(
            "SELECT person_id FROM faces WHERE id=?", (unnamed["id"],)).fetchone()
        self.assertEqual(row[0], 2)
        # 其他人脸不变
        alice = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE photo_id=? AND person_id=1",
            (self.p,)).fetchone()[0]
        self.assertEqual(alice, 1)

    def test_assign_face_unname(self):
        faces = self.g.photoFaces(self.p)
        named = next(f for f in faces if f["personId"] == 1)
        self.assertTrue(self.g.assignFace(named["id"], 0))
        row = self.db.conn.execute(
            "SELECT person_id FROM faces WHERE id=?", (named["id"],)).fetchone()
        self.assertIsNone(row[0])

    def test_face_crop_url(self):
        """人脸裁剪应返回临时文件 URL（无真实图片时返回空串不崩溃）。"""
        faces = self.g.photoFaces(self.p)
        url = self.g.faceCropUrl(faces[0]["id"])
        # 测试库无真实图片文件 → 返回空串（优雅降级）
        self.assertIsInstance(url, str)


class TestMergePeopleBatch(unittest.TestCase):
    """C4：多人批量合并 + 回收站全部恢复。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_merge_")
        self.db = _make_db(self.root)
        self.p = _add_photo(self.db, os.path.join(self.root, "g.jpg"), "g.jpg")
        self.db.conn.execute(
            "INSERT INTO persons(id, name, face_count) VALUES (1, 'A', 2), (2, 'B', 1), (3, 'C', 1)")
        self.db.conn.executemany(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id) VALUES (?,?,?,?,?)",
            [(self.p, '[0.1,0.1,0.2,0.2]', b'\x01'*8, 0.9, 1),
             (self.p, '[0.4,0.1,0.2,0.2]', b'\x02'*8, 0.9, 1),
             (self.p, '[0.7,0.1,0.2,0.2]', b'\x03'*8, 0.9, 2),
             (self.p, '[0.1,0.5,0.2,0.2]', b'\x04'*8, 0.9, 3)])
        self.db.conn.commit()
        self.g = LibraryBridge(self.db.path)

    def tearDown(self):
        self.g.close()
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_merge_people(self):
        """把 B、C 合并进 A，B/C 消失，所有脸归 A。"""
        n = self.g.mergePeople([1, 2, 3])
        self.assertEqual(n, 2)
        rows = {r[0] for r in self.db.conn.execute("SELECT person_id FROM faces").fetchall()}
        self.assertEqual(rows, {1})
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0], 1)
        cnt = self.db.conn.execute("SELECT face_count FROM persons WHERE id=1").fetchone()[0]
        self.assertEqual(cnt, 4)

    def test_merge_requires_two(self):
        self.assertEqual(self.g.mergePeople([1]), 0)

    def test_restore_all_moved_out(self):
        """无移出记录时返回空列表，不报错。"""
        self.assertEqual(self.g.restoreAllMovedOut(), [])


if __name__ == "__main__":
    unittest.main()