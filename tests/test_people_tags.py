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

    def test_person_photos_hidden_excluded_and_no_correlated_exists(self):
        """0.6.20 personPhotos 改 IN 物化：真机规模下 EXISTS 版查询计划是
        「每张照片按 idx_faces_person 扫该人物全部脸」（脸越多越慢，分钟级），
        IN 版 50~145ms。此测试锁两件事：①hidden=1 的脸不带入照片；
        ②WHERE 形状必须是 IN (SELECT … FROM faces …) 而非 EXISTS 关联子查询。"""
        pid = self.bridge.newPerson("张三")
        self._add_face(self.pids[0], pid)
        self._add_face(self.pids[1], pid)
        self._add_face(self.pids[2], pid)          # 正常脸
        c = self.db.conn
        fid = c.execute("SELECT id FROM faces WHERE photo_id=?",
                        (self.pids[2],)).fetchone()[0]
        c.execute("UPDATE faces SET hidden=1 WHERE id=?", (fid,))
        c.commit()
        got = {p["id"] for p in self.bridge.personPhotos(pid, 0, 100)}
        self.assertEqual(got, {self.pids[0], self.pids[1]})
        # 形状守卫：防止回退成 EXISTS 关联子查询（查询计划灾难）
        import inspect
        src = inspect.getsource(type(self.bridge).personPhotos)
        self.assertIn("IN (SELECT", src)
        self.assertNotIn("EXISTS (SELECT", src)

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

    def test_people_paged_pagination(self):
        """0.6.15 人物列表分页 + 0.6.17 代表脸行含 face_id。

        回归：0.6.17 头像缓存改签名 (row)→(pid, row) 后 peoplePaged 两处
        调用/查询未同步（槽内 TypeError 被 Qt 吞掉 → 人物页空白），
        people() 的旧测试覆盖不到此路径，故单独直调 peoplePaged。"""
        pids = [self.bridge.newPerson("") for _ in range(5)]
        for i, p in enumerate(pids):
            self._add_face(self.pids[i % len(self.pids)], p)
        r = self.bridge.peoplePaged(0, 2, "")
        self.assertEqual(r["total"], 5)
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["items"][0]["id"], pids[0])
        self.assertEqual(r["items"][0]["photoCount"], 1)
        self.assertEqual(len(self.bridge.peoplePaged(2, 2, "")["items"]), 2)
        self.assertEqual(len(self.bridge.peoplePaged(4, 2, "")["items"]), 1)
        # 服务器端按名搜索（自动编号名）
        r = self.bridge.peoplePaged(0, 300, "人物 3")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["items"][0]["id"], pids[2])

    def test_person_name_single_lookup(self):
        """0.6.18 单点查 personName(pid)：编号/人名/查无此人，与
        people() 显示名同口径。回归背景：管理头像弹窗 openFor 原为取
        标题而全量构建 people()，7.8 万人物库上卡顿数秒。"""
        a = self.bridge.newPerson("")   # name=NULL
        b = self.bridge.newPerson("")   # name=NULL
        self.assertEqual(self.bridge.personName(a), "人物 1")
        self.assertEqual(self.bridge.personName(b), "人物 2")
        self.assertTrue(self.bridge.renamePerson(a, "张三"))
        self.assertEqual(self.bridge.personName(a), "张三")
        self.assertEqual(self.bridge.personName(b), "人物 1")
        self.assertEqual(self.bridge.personName(0), "")      # 未命名簇
        self.assertEqual(self.bridge.personName(999999), "")  # 查无此人

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


class TestDupPersons(_TempDB):
    """0.6.20 疑似重复人物（阶段一 Top-N 代表脸余弦）。"""

    def setUp(self):
        super().setUp()
        import numpy as np

        self.np = np
        self.bridge._face_threshold = 0.6  # 固定阈值，摆脱本机 QSettings

    def _v(self, cos_target, ref=0):
        """构造与第 ref 个单位向量余弦为 cos_target 的 128 维描述子。"""
        np = self.np
        v = np.zeros(128, dtype=np.float32)
        v[ref] = 1.0
        w = np.zeros(128, dtype=np.float32)
        w[ref] = np.cos(np.arccos(min(1.0, cos_target)))
        w[ref + 1] = np.sin(np.arccos(min(1.0, cos_target)))
        return w

    def _add_person_with_faces(self, descriptor, photo_ids):
        import json

        c = self.db.conn
        c.execute("INSERT INTO persons(name) VALUES (NULL)")
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for photo_id in photo_ids:
            c.execute(
                "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
                " VALUES (?,?,?,?,?)",
                (photo_id, json.dumps([0, 0, 10, 10]),
                 descriptor.tobytes(), 0.9, pid))
        c.commit()
        return pid

    def test_scan_finds_band_pair_only(self):
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        pc = self._add_person_with_faces(self._v(0.10), self.pids[:2])
        n = self.bridge._dup_scan_now()
        self.assertEqual(n, 1, "只有 0.42（带内）成为候选")
        cands = self.bridge.dupCandidates()
        self.assertEqual(len(cands), 1)
        pair = cands[0]
        self.assertEqual({pair["a"], pair["b"]}, {pa, pb})
        self.assertEqual(pair["sim"], 42)
        self.assertGreaterEqual(pair["aCount"], pair["bCount"])
        self.assertTrue(pair["aName"] and pair["bName"])
        # 已命名人物不参与
        self.assertTrue(self.bridge.renamePerson(pc, "有名字的人"))
        self.bridge.dupIgnore(pa, pb)
        self.db.conn.execute("UPDATE person_dup_candidates SET ignored=0")
        self.db.conn.commit()
        self.bridge._dup_scan_now()
        # pc 已命名：即便解除忽略也不应出现在候选里
        for r in self.bridge.dupCandidates():
            self.assertNotIn(pc, (r["a"], r["b"]))

    def test_ignore_persists_across_rescan(self):
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        self.assertEqual(self.bridge._dup_scan_now(), 1)
        self.bridge.dupIgnore(pa, pb)
        self.assertEqual(self.bridge.dupCandidates(), [])
        self.assertEqual(self.bridge._dup_scan_now(), 0, "重扫应跳过已忽略对")
        self.assertEqual(self.bridge.dupCandidates(), [])

    def test_merge_cleans_candidates(self):
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        self.assertEqual(self.bridge._dup_scan_now(), 1)
        # 合并（src=照片少的一方按 UI 语义；此处直接并 pa→pb）
        self.assertEqual(self.bridge.mergePersons(pa, pb), 1)
        self.assertEqual(self.bridge.dupCandidates(), [],
                         "引用已删除 src 的候选应被清掉")

    def test_anchor_scan_per_person(self):
        """0.6.21 两步式：以单个人物为锚点扫疑似重复。"""
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        pc = self._add_person_with_faces(self._v(0.10), self.pids[:2])
        # 锚点=pa：只与 pa 比较，仅 pb 落带内
        self.assertEqual(self.bridge._dup_scan_anchor(pa), 1)
        cands = self.bridge.dupCandidates()
        self.assertEqual(len(cands), 1)
        self.assertEqual({cands[0]["a"], cands[0]["b"]}, {pa, pb})
        # 锚点扫描不清其他候选（与全库扫 DELETE-then-INSERT 不同）
        self.assertEqual(self.bridge._dup_scan_anchor(pc), 0)
        self.assertEqual(len(self.bridge.dupCandidates()), 1)
        # 锚点无可用代表脸 → -1
        self.assertEqual(self.bridge._dup_scan_anchor(999999), -1)

    def test_merge_people_cleans_candidates(self):
        """0.6.25 补24：人物页「合并选中」（mergePeople）同样清理候选对。"""
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        self.assertEqual(self.bridge._dup_scan_now(), 1)
        # 批量合并：pa 并入 pb（与弹窗方向一致）
        self.assertEqual(self.bridge.mergePeople([pa, pb]), 1)
        self.assertEqual(self.bridge.dupCandidates(), [],
                         "批量合并后引用已删除人物的候选应被清掉")

    def test_candidates_anchor_filter(self):
        """0.6.25 补24：锚点过滤——只返回与锚点人物相关的候选对。"""
        pa = self._add_person_with_faces(self._v(1.0), self.pids[:2])
        pb = self._add_person_with_faces(self._v(0.42), self.pids[:2])
        pd = self._add_person_with_faces(self._v(0.45), self.pids[:2])
        pc = self._add_person_with_faces(self._v(0.10), self.pids[:2])
        # 锚点 pa：pb(0.42)/pd(0.45) 均落带内 → 2 对
        self.assertEqual(self.bridge._dup_scan_anchor(pa), 2)
        # 锚点 pb：只与 pa 落带内（pb-pd 余弦≈0.999 超聚类上限）
        self.assertEqual(self.bridge._dup_scan_anchor(pb), 1)
        # 无过滤：2 对
        self.assertEqual(len(self.bridge.dupCandidates()), 2)
        # 锚点过滤：pa → 2 对且都含 pa；pb → 1 对
        import sqlite3
        conn = sqlite3.connect(self.db.path)
        try:
            only_pa = self.bridge._dup_candidates_impl(conn, pa)
            only_pb = self.bridge._dup_candidates_impl(conn, pb)
        finally:
            conn.close()
        self.assertEqual(len(only_pa), 2)
        for r in only_pa:
            self.assertIn(pa, (r["a"], r["b"]))
        self.assertEqual(len(only_pb), 1)
        self.assertIn(pb, (only_pb[0]["a"], only_pb[0]["b"]))


class TestFaceSearchViews(_TempDB):
    """0.6.21 人脸搜图结果双视图：平铺（照片最高分）/ 按人物分组。"""

    RES = [
        (1, 0.90, 5),   # 照片1 经人物5 的脸命中
        (2, 0.80, 5),
        (3, 0.70, 0),   # 未指派人物
        (1, 0.60, 7),   # 照片1 经人物7 的另一张脸命中（应同时出现在两组合）
        (4, 0.50, 0),
    ]

    def test_flat_takes_best_per_photo(self):
        flat = LibraryBridge._face_search_flat(self.RES)
        self.assertEqual(flat, [(1, 0.90), (2, 0.80), (3, 0.70), (4, 0.50)])

    def test_grouped_order_titles_and_cross_person(self):
        groups = LibraryBridge._face_search_grouped(self.RES, {5: "小明"})
        # 组间按组内最高相似度降序：5(0.9) → 0(0.7) → 7(0.6)
        self.assertEqual([g["personId"] for g in groups], [5, 0, 7])
        self.assertEqual([g["title"] for g in groups],
                         ["小明", "未指派人物", "人物 #7"])
        self.assertEqual([g["count"] for g in groups], [2, 2, 1])
        self.assertEqual([g["best"] for g in groups], [90, 70, 60])
        # 组内按相似度降序
        self.assertEqual(groups[0]["photos"], [(1, 0.90), (2, 0.80)])
        self.assertEqual(groups[1]["photos"], [(3, 0.70), (4, 0.50)])
        # 同一照片经不同人物命中 → 各组各出现一次
        pids5 = [p for p, _ in groups[0]["photos"]]
        pids7 = [p for p, _ in groups[2]["photos"]]
        self.assertIn(1, pids5)
        self.assertIn(1, pids7)

    def test_group_title_fallbacks(self):
        self.assertEqual(
            LibraryBridge._face_group_title(0, {}), "未指派人物")
        self.assertEqual(
            LibraryBridge._face_group_title(9, {}), "人物 #9")
        self.assertEqual(
            LibraryBridge._face_group_title(5, {5: "张三"}), "张三")


class TestFaceCaches(_TempDB):
    """0.6.20 头像缓存链路：_fcq 9 参修复 + 管理头像逐脸 HQ 缓存。"""

    def _add_real_photo(self, name, ext=".jpg"):
        from PIL import Image

        path = os.path.join(self.tmp.name, name)
        # 文件内容不影响断言（HQ 跳过只看扩展名），显式 JPEG 格式落盘
        Image.new("RGB", (400, 300), (80, 120, 160)).save(path, "JPEG")
        c = self.db.conn
        c.execute(
            "INSERT INTO photos(file_path, file_name, folder_path, ext,"
            " file_size, file_mtime, taken_at, sort_key, status, width, height)"
            " VALUES (?,?,?,?,?,?,?,?,'indexed',400,300)",
            (path, name, self.tmp.name, ext, os.path.getsize(path),
             100.0, "2025-03-02T10:00:00", "2025-03-02T10:00:00"))
        c.commit()
        return c.execute("SELECT id FROM photos WHERE file_name=?",
                         (name,)).fetchone()[0]

    def _wait_for(self, predicate, timeout=15.0):
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.2)
        return False

    def test_person_avatar_cache_actually_builds(self):
        """0.6.20 回归：_fcq 曾只入队 (pid, face_id) 二元组，worker 9 参
        调用 TypeError 被吞——原图缓存从未构建成功过（含 time 未导入）。"""
        import json

        photo_id = self._add_real_photo("r1.jpg")
        face_id = self.db.conn.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
            " VALUES (?,?,?,?,?)",
            (photo_id, json.dumps([10, 10, 50, 50]), b"\x00" * 128, 0.9, None),
        ).lastrowid
        self.db.conn.commit()
        self.bridge._fc_seen.clear()
        av = self.bridge._face_avatar(
            3, (face_id, json.dumps([10, 10, 50, 50]),
                os.path.join(self.tmp.name, "r1.jpg"), "", 400, 300, 0, 0))
        self.assertIsNotNone(av)
        cache = (os.path.join(self.tmp.name, "face_crops", "p0003",
                              f"p3_f{face_id}.jpg"))
        self.assertTrue(self._wait_for(lambda: os.path.exists(cache)),
                        "人物头像原图缓存应真正落盘")

    def test_face_hq_cache_builds_and_lru_path(self):
        import json

        photo_id = self._add_real_photo("r2.jpg")
        face_id = self.db.conn.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
            " VALUES (?,?,?,?,?)",
            (photo_id, json.dumps([10, 10, 50, 50]), b"\x00" * 128, 0.9, None),
        ).lastrowid
        self.db.conn.commit()
        self.assertIsNone(self.bridge.faceAvatarHq(face_id), "未构建前应返回 None")
        self.bridge._hq_seen.clear()
        self.bridge.requestFaceHq(face_id)
        cache = (os.path.join(self.tmp.name, "face_crops_hq", "f%04d" % (face_id % 256),
                              f"f{face_id}.jpg"))
        self.assertTrue(self._wait_for(lambda: os.path.exists(cache)),
                        "HQ 裁剪应后台落盘")
        hq = self.bridge.faceAvatarHq(face_id)
        self.assertIsNotNone(hq)
        self.assertGreater(hq["w"], 0)
        self.assertGreater(hq["h"], 0)
        self.assertIsNone(self.bridge.faceAvatarHq(face_id + 999))
        # RAW 扩展名不进队列（PIL 解不开，保持缩略图裁剪）
        photo3 = self._add_real_photo("r3.nef", ext=".nef")
        face3 = self.db.conn.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
            " VALUES (?,?,?,?,?)",
            (photo3, json.dumps([0, 0, 10, 10]), b"\x00" * 128, 0.9, None),
        ).lastrowid
        self.db.conn.commit()
        self.bridge._hq_seen.clear()
        self.bridge.requestFaceHq(face3)
        self._wait_for(lambda: False, timeout=1.0)  # 给误建留时间窗
        self.assertIsNone(self.bridge.faceAvatarHq(face3),
                          "RAW 脸不应构建 HQ 缓存")


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