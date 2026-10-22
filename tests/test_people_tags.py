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
"""C2 单元测试：人物管理（重命名/新建/合并/拆分）与标签管理（重命名/合并）、
时间线/统计/回收站桥接数据契约（直接调用 bridge，不依赖 QML）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.db import Database
from photo_manager.ui.library_bridge import LibraryBridge


def _make_db(root, name="lib.db"):
    return Database(os.path.join(root, name)).connect()


class _TempDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = _make_db(self.tmp.name)
        self.bridge = LibraryBridge(os.path.join(self.tmp.name, "lib.db"))
        self._add_base()

    def tearDown(self):
        self.bridge.close()
        self.db.close()
        self.tmp.cleanup()

    def _add_photo(self, file_path, name, taken="2025-03-02T10:00:00"):
        c = self.db.conn
        c.execute(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
            " file_mtime, taken_at, sort_key, status)"
            " VALUES (?,?,?,?,?,?,?,?,'indexed')",
            (file_path, name, "test_dir", ".jpg", 1000, 100.0, taken, taken),
        )
        c.commit()
        return c.execute("SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]

    def _add_base(self):
        self.pids = [self._add_photo(f"/fake/p{i}.jpg", f"p{i}.jpg",
                                     f"2025-03-0{i + 1}T10:00:00") for i in range(4)]

    def _add_face(self, photo_id, person_id=None):
        c = self.db.conn
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
            " VALUES (?,?,?,?,?)",
            # bbox 与真实管线一致存 JSON（photoFaces 按 json.loads 解析）
            (photo_id, "[0,0,1,1]", b"\x00\x01", 0.9, person_id),
        )
        c.commit()


class TestPeople(_TempDB):
    def test_new_person(self):
        pid = self.bridge.newPerson("")
        self.assertGreater(pid, 0)
        row = self.db.conn.execute("SELECT name FROM persons WHERE id=?", (pid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row[0])

    def test_rename_person(self):
        pid = self.bridge.newPerson("未命名")
        self.assertTrue(self.bridge.renamePerson(pid, "张三"))
        names = [p["name"] for p in self.bridge.people()]
        self.assertIn("张三", names)

    def test_rename_person_duplicate_rejected(self):
        a = self.bridge.newPerson("李四")
        b = self.bridge.newPerson("")
        self.assertTrue(self.bridge.renamePerson(a, "王五"))
        self.assertFalse(self.bridge.renamePerson(b, "王五"), "重名应返回 False")
        cnt = self.db.conn.execute(
            "SELECT COUNT(*) FROM persons WHERE name='王五'").fetchone()[0]
        self.assertEqual(cnt, 1)

    def test_people_auto_numbering(self):
        """未命名人物按 id 顺序自动编号「人物 1/2/…」；命名后显示人名（0.5.23）。"""
        a = self.bridge.newPerson("")   # name=NULL
        b = self.bridge.newPerson("")   # name=NULL
        got = {p["id"]: p["name"] for p in self.bridge.people()}
        self.assertEqual(got[a], "人物 1")
        self.assertEqual(got[b], "人物 2")
        # 命名后显示人名，另一人编号顺延不跳号
        self.assertTrue(self.bridge.renamePerson(a, "张三"))
        got = {p["id"]: p["name"] for p in self.bridge.people()}
        self.assertEqual(got[a], "张三")
        self.assertEqual(got[b], "人物 1")

    def test_photofaces_shows_numbered_name(self):
        """信息面板人脸区的 personName 与人物页编号一致（0.5.23）。"""
        pid_person = self.bridge.newPerson("")
        self._add_face(self.pids[0], pid_person)
        faces = self.bridge.photoFaces(self.pids[0])
        self.assertEqual(len(faces), 1)
        self.assertEqual(faces[0]["personName"], "人物 1")
        self.assertEqual(faces[0]["personId"], pid_person)

    def test_people_avatar_uses_face_crop(self):
        """人物页头像：people() 附带置信度最高脸的缩略图像素裁剪框（0.5.28）。"""
        from photo_manager.core.faces import MAX_DIM

        thumb = os.path.join(self.tmp.name, "t0.jpg")
        with open(thumb, "wb") as f:
            f.write(b"\xff\xd8fakejpeg")
        c = self.db.conn
        c.execute(
            "UPDATE photos SET thumbnail_path=?, thumb_width=400, thumb_height=400,"
            " width=?, height=? WHERE id=?",
            (thumb, MAX_DIM, MAX_DIM, self.pids[0]),
        )
        c.commit()  # 必须先提交：未提交的写事务会占写锁，bridge 连接会撞 SQLITE_BUSY
        pid_person = self.bridge.newPerson("")
        assert pid_person > 0
        self._add_face(self.pids[0], pid_person)
        # bbox 铺满左半检测缩放图 → 归一化(0.5偏移) → 缩略图裁剪框 (200,0,200,400)
        c.execute("UPDATE faces SET bbox=? WHERE photo_id=?",
                  ("[%d,0,%d,%d]" % (MAX_DIM // 2, MAX_DIM // 2, MAX_DIM), self.pids[0]))
        c.commit()
        people = self.bridge.people()
        p = next(x for x in people if x["id"] == pid_person)
        self.assertEqual(os.path.abspath(p["avatarSrc"]), os.path.abspath(thumb))
        self.assertEqual((p["avatarX"], p["avatarY"]), (200, 0))
        self.assertEqual((p["avatarW"], p["avatarH"]), (200, 400))

    def test_people_avatar_absent_without_face(self):
        """无脸数据的人物不带头像字段（QML 回退图标），且不报错。"""
        pid = self.bridge.newPerson("")
        p = next(x for x in self.bridge.people() if x["id"] == pid)
        self.assertNotIn("avatarSrc", p)

    def test_people_avatar_missing_thumb_falls_back(self):
        """缩略图文件不存在时回退原图路径；原图也不存在则不带头像字段。"""
        c = self.db.conn
        c.execute(
            "UPDATE photos SET thumbnail_path='/fake/nope.jpg', thumb_width=400,"
            " thumb_height=400, width=1000, height=1000 WHERE id=?",
            (self.pids[0],),
        )
        c.commit()
        pid_person = self.bridge.newPerson("")
        self._add_face(self.pids[0], pid_person)
        p = next(x for x in self.bridge.people() if x["id"] == pid_person)
        self.assertNotIn("avatarSrc", p, "缩略图与原图都不在磁盘上 → 不给头像")

    def test_merge_persons(self):
        a = self.bridge.newPerson("甲")
        b = self.bridge.newPerson("乙")
        self._add_face(self.pids[0], a)
        self._add_face(self.pids[1], b)
        n = self.bridge.mergePersons(b, a)
        self.assertGreater(n, 0)
        faces_a = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE person_id=?", (a,)).fetchone()[0]
        faces_b = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE person_id=?", (b,)).fetchone()[0]
        gone = self.db.conn.execute(
            "SELECT COUNT(*) FROM persons WHERE id=?", (b,)).fetchone()[0] == 0
        fc = self.db.conn.execute(
            "SELECT face_count FROM persons WHERE id=?", (a,)).fetchone()[0]
        self.assertEqual(faces_a, 2)
        self.assertEqual(faces_b, 0)
        self.assertTrue(gone)
        self.assertEqual(fc, 2)

    def test_merge_unnamed_into_person(self):
        a = self.bridge.newPerson("甲")
        self._add_face(self.pids[0], None)
        n = self.bridge.mergePersons(0, a)
        self.assertGreater(n, 0)
        cnt = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE person_id=?", (a,)).fetchone()[0]
        self.assertEqual(cnt, 1)

    def test_move_photos_to_person(self):
        a = self.bridge.newPerson("甲")
        b = self.bridge.newPerson("乙")
        self._add_face(self.pids[0], a)
        n = self.bridge.movePhotosToPerson([self.pids[0]], b)
        self.assertEqual(n, 1)
        in_b = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE photo_id=? AND person_id=?",
            (self.pids[0], b)).fetchone()[0]
        in_a = self.db.conn.execute(
            "SELECT COUNT(*) FROM faces WHERE photo_id=? AND person_id=?",
            (self.pids[0], a)).fetchone()[0]
        self.assertGreater(in_b, 0)
        self.assertEqual(in_a, 0)


class TestTags(_TempDB):
    def _seed_tag(self, pid, tag):
        self.db.conn.execute(
            "INSERT OR IGNORE INTO photo_tags(photo_id, tag) VALUES (?,?)", (pid, tag))
        self.db.conn.commit()

    def test_rename_tag(self):
        self._seed_tag(self.pids[0], "旧标签")
        n = self.bridge.renameTag("旧标签", "新标签")
        self.assertEqual(n, 1)
        old = self.db.conn.execute(
            "SELECT COUNT(*) FROM photo_tags WHERE tag='旧标签'").fetchone()[0]
        new = self.db.conn.execute(
            "SELECT COUNT(*) FROM photo_tags WHERE tag='新标签'").fetchone()[0]
        self.assertEqual(old, 0)
        self.assertEqual(new, 1)

    def test_merge_tags_dedup(self):
        self._seed_tag(self.pids[0], "a")
        self._seed_tag(self.pids[1], "a")
        self._seed_tag(self.pids[2], "b")
        n = self.bridge.mergeTags("b", "a")
        self.assertEqual(n, 1)
        cnt = self.db.conn.execute(
            "SELECT COUNT(*) FROM photo_tags WHERE tag='a'").fetchone()[0]
        b = self.db.conn.execute(
            "SELECT COUNT(*) FROM photo_tags WHERE tag='b'").fetchone()[0]
        self.assertEqual(cnt, 3)
        self.assertEqual(b, 0)

    def test_merge_tags_to_self(self):
        self._seed_tag(self.pids[0], "a")
        self.assertEqual(self.bridge.mergeTags("a", "a"), 0)

    def test_tags_desc_order(self):
        self._seed_tag(self.pids[0], "a")
        self._seed_tag(self.pids[0], "b")
        self._seed_tag(self.pids[0], "c")
        tags = self.bridge.tags()
        counts = [t["photoCount"] for t in tags]
        self.assertEqual(counts, sorted(counts, reverse=True))


class TestTimeline(_TempDB):
    def test_timeline_nested(self):
        tl = self.bridge.timeline()
        self.assertGreaterEqual(len(tl), 1)
        total = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE taken_at!=''").fetchone()[0]
        month_sum = sum(y["photoCount"] for y in tl)
        self.assertEqual(month_sum, total)
        self.assertGreater(tl[0]["months"][0]["photoCount"], 0)

    def test_month_photos(self):
        tl = self.bridge.timeline()
        ym = tl[0]["months"][0]["key"]
        cnt = self.bridge.dateMonthCount(ym)
        ph = self.bridge.dateMonthPhotos(ym, 0, 10)
        self.assertGreater(cnt, 0)
        self.assertEqual(len(ph), min(10, cnt))

    def test_day_photos(self):
        tl = self.bridge.timeline()
        ym = tl[0]["months"][0]["key"]
        days = self.bridge.timelineDays(ym)
        self.assertGreater(len(days), 0)
        day = days[0]["day"]
        cnt = self.bridge.dateCount(day)
        ph = self.bridge.datePhotos(day, 0, 10)
        self.assertGreater(cnt, 0)
        self.assertEqual(len(ph), min(10, cnt))


class TestStats(_TempDB):
    def test_stats_dashboard_fields(self):
        sd = self.bridge.statsDashboard()
        self.assertIn("totals", sd)
        for k in ("photos", "faces", "persons", "events", "tags", "dupGroups", "movedOut"):
            self.assertIn(k, sd["totals"])
        self.assertEqual(sd["totals"]["photos"], 4)
        for k in ("byYear", "byMonth", "byDevice", "byLocation"):
            self.assertIsInstance(sd.get(k), list)

    def test_stats_distributions(self):
        sd = self.bridge.statsDashboard()
        self.assertGreaterEqual(len(sd["byYear"]), 1)
        self.assertGreaterEqual(len(sd["byMonth"]), 1)


class TestTrash(_TempDB):
    def test_moved_out_list_and_reimport(self):
        self.assertEqual(self.bridge.movedOutList(), [])
        dest = os.path.join(self.tmp.name, "c2_move_out")
        os.makedirs(dest, exist_ok=True)
        import shutil

        src = os.path.join(self.tmp.name, "p0.jpg")
        with open(src, "wb") as f:
            f.write(b"jpg")
        pid = self._add_photo(src, "p0.jpg")
        n = self.bridge.moveOut([pid], dest)
        # moveOut 走后台线程
        import time
        for _ in range(50):
            if self.bridge.busyCount() == 0:
                break
            time.sleep(0.1)
        mol = self.bridge.movedOutList()
        self.assertEqual(n, 1)
        self.assertTrue(any(x["folder"] == dest for x in mol))
        before = self.bridge.totalPhotos()
        self.bridge.reimportMovedOut(dest)
        for _ in range(100):
            if self.bridge.busyCount() == 0:
                break
            time.sleep(0.1)
        after = self.bridge.totalPhotos()
        cleared = all(x["folder"] != dest for x in self.bridge.movedOutList())
        self.assertGreaterEqual(after, before)
        self.assertTrue(cleared)


if __name__ == "__main__":
    unittest.main()