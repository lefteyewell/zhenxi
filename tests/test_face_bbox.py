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
"""0.6.31：相机 RAW / 竖拍人脸框坐标基准回归测试。

守护的不变量：
1. faces.bbox 存 6 元素并自带检测图尺寸；历史 4 元素仍按老口径读取；
2. 预览弹窗人脸框（photoFaces）、信息栏人脸小图（faceCropUrl）、
   人物头像（_face_avatar）全部按检测图尺寸归一化，不再被
   photos.width/height（RAW 传感器尺寸）带偏；
3. 首启一次性作废历史 RAW 的人脸框，OCR / 普通照片 / 语义向量不动；
4. 新旧版导出的元数据包仍能按 bbox 前 4 个数值匹配人脸归属。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from photo_manager.core import rawio
from photo_manager.core.db import FACE_BBOX_VERSION, Database
from photo_manager.core.faces import (MAX_DIM, FacePipeline, FaceService,
                                      parse_face_bbox)
from photo_manager.core.sync import MetadataSync
from photo_manager.ui.library_bridge import LibraryBridge


def _make_db(root, name="lib.db"):
    return Database(os.path.join(root, name)).connect()


def _add_photo(db, file_path, name, ext=".jpg", w=6000, h=4000,
               tpath="", tw=0, th=0):
    c = db.conn
    c.execute(
        "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
        " file_mtime, taken_at, sort_key, status, media_type, width, height,"
        " thumbnail_path, thumb_width, thumb_height)"
        " VALUES (?,?,?,?,?,?,?,?,'indexed','photo',?,?,?,?,?)",
        (file_path, name, "/fake", ext, 1000, 100.0,
         "2025-03-02T10:00:00", "2025-03-02T10:00:00",
         w, h, tpath, tw, th),
    )
    return c.execute(
        "SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]


def _add_face(db, photo_id, bbox, person_id=None):
    return db.conn.execute(
        "INSERT INTO faces(photo_id, bbox, descriptor, score, person_id)"
        " VALUES (?,?,?,?,?)",
        (photo_id, json.dumps(bbox), b"\x00" * 128, 0.9, person_id),
    ).lastrowid


class ParseFaceBboxTest(unittest.TestCase):
    def test_six_element_uses_detection_dims(self):
        bx, by, bw, bh, rw, rh = parse_face_bbox(
            "[400,500,100,100,1080,1616]", 6000, 4000)
        self.assertEqual((bx, by, bw, bh), (400, 500, 100, 100))
        self.assertEqual((rw, rh), (1080, 1616))  # 不是库内 6000×4000

    def test_four_element_keeps_legacy_formula(self):
        bx, by, bw, bh, rw, rh = parse_face_bbox("[400,500,100,100]", 6000, 4000)
        scale = min(1.0, MAX_DIM / 6000)
        self.assertEqual((rw, rh),
                         (max(1, round(6000 * scale)), max(1, round(4000 * scale))))

    def test_bad_payload_raises(self):
        with self.assertRaises(Exception):
            parse_face_bbox("[1,2]", 100, 100)

    def test_zero_dims_fall_back_to_legacy(self):
        _, _, _, _, rw, rh = parse_face_bbox("[1,2,3,4,0,0]", 6000, 4000)
        self.assertGreater(rw, 0)
        self.assertGreater(rh, 0)


class FaceDetectionStoresRefDimsTest(unittest.TestCase):
    def test_process_image_appends_detection_image_size(self):
        svc = FaceService("models")
        fake = np.zeros((300, 200, 3), dtype=np.uint8)  # < MAX_DIM，不会缩放
        face = {"bbox": [40.0, 50.0, 20.0, 20.0], "score": 0.9,
                "row": [0.0] * 15}
        with patch.object(rawio, "read_bgr", return_value=fake), \
             patch.object(rawio, "orientation", return_value=1), \
             patch.object(svc, "detect", return_value=[face]), \
             patch.object(svc, "feature",
                          return_value=np.zeros(128, dtype=np.float32)):
            out = svc.process_image("portrait.ARW")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["bbox"], [40.0, 50.0, 20.0, 20.0, 200.0, 300.0])


class FaceDisplayGeometryTest(unittest.TestCase):
    """RAW 传感器尺寸 6000×4000，检测图却是 1080×1616 内嵌预览。"""

    BBOX6 = [400, 500, 100, 100, 1080, 1616]

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm_bbox_")
        self.db = _make_db(self.root)
        self.jpg_path = os.path.join(self.root, "raw_original.jpg")
        # 故意写成非法图片：模拟相机 RAW（PIL 打不开 → 走缩略图裁剪兜底）
        with open(self.jpg_path, "wb") as f:
            f.write(b"not an image")
        self.thumb = os.path.join(self.root, "thumb.jpg")
        self._make_two_tone_thumb(self.thumb)
        self.p = _add_photo(self.db, self.jpg_path, "DSC00018.ARW",
                            ext=".arw", tpath=self.thumb, tw=400, th=400)
        self.fid = _add_face(self.db, self.p, self.BBOX6)
        self.db.conn.commit()
        self.g = LibraryBridge(self.db.path)

    def tearDown(self):
        self.g.close()
        self.db.close()
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def _make_two_tone_thumb(path):
        from PIL import Image

        im = Image.new("RGB", (400, 400), (255, 0, 0))
        for x in range(200, 400):
            for y in range(400):
                im.putpixel((x, y), (0, 0, 255))
        im.save(path, "JPEG")

    def test_photoFaces_uses_detection_dims(self):
        faces = self.g.photoFaces(self.p)
        self.assertEqual(len(faces), 1)
        f = faces[0]
        self.assertAlmostEqual(f["nx"], 400 / 1080)
        self.assertAlmostEqual(f["ny"], 500 / 1616)
        self.assertAlmostEqual(f["nw"], 100 / 1080)
        self.assertAlmostEqual(f["nh"], 100 / 1616)
        # 旧口径（按 6000×4000 缩放）会给出 400/2000=0.2
        self.assertNotAlmostEqual(f["nx"], 400 / 2000)

    def test_legacy_four_element_keeps_old_behavior(self):
        self.db.conn.execute(
            "UPDATE faces SET bbox=? WHERE id=?",
            (json.dumps(self.BBOX6[:4]), self.fid))
        self.db.conn.commit()
        f = self.g.photoFaces(self.p)[0]
        self.assertAlmostEqual(f["nx"], 400 / 2000)

    def test_face_avatar_uses_detection_dims(self):
        row = (self.fid, json.dumps(self.BBOX6), self.jpg_path, self.thumb,
               6000, 4000, 400, 400)
        av = self.g._face_avatar(1, row, cached=False)
        self.assertIsNotNone(av)
        self.assertEqual(av["avatarX"], round(400 / 1080 * 400))

    def test_faceCropUrl_fallback_crops_right_place(self):
        """bbox 覆盖检测图左半 → 归一化后应裁到缩略图左半（红色）。"""
        bbox = [0, 0, 540, 1616, 1080, 1616]
        self.db.conn.execute(
            "UPDATE faces SET bbox=? WHERE id=?", (json.dumps(bbox), self.fid))
        self.db.conn.commit()
        url = self.g.faceCropUrl(self.fid)
        self.assertTrue(url)
        from PIL import Image

        from PySide6.QtCore import QUrl
        crop_path = Path(QUrl(url).toLocalFile())
        with Image.open(crop_path) as im:
            px = np.asarray(im.convert("RGB"))
        self.assertGreater(float(px[:, :, 0].mean()),
                           float(px[:, :, 2].mean()),
                           "裁剪应落在左半红色区域")


class FaceBboxMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "lib.db")
        self.db = Database(self.path).connect()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _seed(self, name, *, error=None):
        c = self.db.conn
        fp = os.path.join(self.tmp.name, name)
        pid = _add_photo(self.db, fp, name, ext=os.path.splitext(name)[1])
        c.execute(
            "UPDATE photos SET face_done=1, face_count=1, ocr_done=1,"
            " ocr_text='keep ocr', has_text=1, error=? WHERE id=?",
            (error, pid))
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score)"
            " VALUES (?, '[0,0,10,10]', X'00', 0.9)", (pid,))
        c.execute(
            "INSERT INTO ocr_texts(photo_id, text, conf)"
            " VALUES (?, 'keep ocr', 0.9)", (pid,))
        c.commit()
        return pid

    def _simulate_0630(self):
        """只删新标记，模拟已经打过 0.6.30 RAW 迁移的库。"""
        self.db.conn.execute(
            "DELETE FROM meta WHERE key='face_bbox_version'")
        self.db.conn.commit()
        self.db.close()
        self.db = Database(self.path).connect()

    def _row(self, pid):
        return self.db.conn.execute(
            "SELECT face_done, face_count, ocr_done, ocr_text, has_text, error"
            " FROM photos WHERE id=?", (pid,)).fetchone()

    def test_fresh_library_marked_immediately(self):
        row = self.db.conn.execute(
            "SELECT value FROM meta WHERE key='face_bbox_version'").fetchone()
        self.assertEqual(row[0], str(FACE_BBOX_VERSION))
        raw = self._seed("new.ARW")
        self.db.close()
        self.db = Database(self.path).connect()
        self.assertEqual(self._row(raw)[0], 1)

    def test_only_raw_faces_are_invalidated(self):
        raw = self._seed("IMG_001.ARW", error="face: 无法读取图片")
        jpg = self._seed("IMG_002.JPG", error="face: keep me")
        self._simulate_0630()
        self.assertEqual(self._row(raw), (0, 0, 1, "keep ocr", 1, None))
        self.assertEqual(self._row(jpg), (1, 1, 1, "keep ocr", 1, "face: keep me"))
        c = self.db.conn
        self.assertEqual(
            c.execute("SELECT count(*) FROM faces WHERE photo_id=?", (raw,))
            .fetchone()[0], 0)
        self.assertEqual(
            c.execute("SELECT count(*) FROM faces WHERE photo_id=?", (jpg,))
            .fetchone()[0], 1)
        self.assertEqual(
            c.execute("SELECT count(*) FROM ocr_texts WHERE photo_id=?", (raw,))
            .fetchone()[0], 1)
        self.assertEqual(
            c.execute("SELECT value FROM meta WHERE key='face_bbox_version'")
            .fetchone()[0], str(FACE_BBOX_VERSION))

    def test_named_person_is_backed_up_and_restored(self):
        raw = self._seed("named.ARW")
        c = self.db.conn
        c.execute("INSERT INTO persons(name, face_count) VALUES ('张老师', 1)")
        person = c.execute(
            "SELECT id FROM persons WHERE name='张老师'").fetchone()[0]
        c.execute("UPDATE faces SET person_id=? WHERE photo_id=?", (person, raw))
        c.commit()
        self._simulate_0630()
        row = self.db.conn.execute(
            "SELECT person_name FROM face_name_backup WHERE photo_id=?",
            (raw,)).fetchone()
        self.assertEqual(row[0], "张老师")
        # 模拟重跑人脸检测后写入新 6 元素 bbox，再还原归属
        c = self.db.conn
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score)"
            " VALUES (?, '[1,2,3,4,1080,1616]', X'00', 0.9)", (raw,))
        c.commit()
        FacePipeline._restore_face_name(c, raw)
        assigned = c.execute(
            "SELECT pe.name FROM faces f JOIN persons pe ON pe.id=f.person_id"
            " WHERE f.photo_id=?", (raw,)).fetchone()
        self.assertEqual(assigned[0], "张老师")
        self.assertIsNone(c.execute(
            "SELECT 1 FROM face_name_backup WHERE photo_id=?", (raw,)).fetchone())

    def test_unnamed_photo_needs_no_backup(self):
        raw = self._seed("unnamed.ARW")
        self._simulate_0630()
        self.assertIsNone(self.db.conn.execute(
            "SELECT 1 FROM face_name_backup WHERE photo_id=?", (raw,)).fetchone())

    def test_second_connect_does_not_reset_reanalyzed_results(self):
        raw = self._seed("IMG_001.NEF")
        self._simulate_0630()
        c = self.db.conn
        c.execute("UPDATE photos SET face_done=1, face_count=2 WHERE id=?", (raw,))
        c.execute(
            "INSERT INTO faces(photo_id, bbox, descriptor, score)"
            " VALUES (?, '[1,2,3,4,1080,1616]', X'00', 0.8)", (raw,))
        c.commit()
        self.db.close()
        self.db = Database(self.path).connect()
        self.assertEqual(self._row(raw)[:2], (1, 2))
        self.assertEqual(
            self.db.conn.execute(
                "SELECT count(*) FROM faces WHERE photo_id=?", (raw,))
            .fetchone()[0], 1)


class SyncCrossVersionBboxTest(unittest.TestCase):
    def test_four_to_six_element_bbox_still_matches(self):
        root = tempfile.mkdtemp(prefix="pm_sync_bbox_")
        try:
            db_a = _make_db(root, "a.db")
            path = os.path.join(root, "p.jpg")
            pid = _add_photo(db_a, path, "p.jpg")
            db_a.conn.execute(
                "INSERT INTO persons(name, face_count) VALUES ('张三', 1)")
            person = db_a.conn.execute(
                "SELECT id FROM persons WHERE name='张三'").fetchone()[0]
            _add_face(db_a, pid, [10, 10, 50, 50], person)
            db_a.conn.commit()
            meta = os.path.join(root, "meta.db")
            MetadataSync(db_a).export(meta)

            db_b = _make_db(root, "b.db")
            pid_b = _add_photo(db_b, path, "p.jpg")
            # 新版：bbox 末尾多了检测图尺寸
            _add_face(db_b, pid_b, [10, 10, 50, 50, 1080, 1616])
            db_b.conn.commit()
            stats = MetadataSync(db_b).import_from(meta)
            self.assertEqual(stats["matched_faces"], 1)
            row = db_b.conn.execute(
                "SELECT pe.name FROM faces f JOIN persons pe"
                " ON pe.id=f.person_id WHERE f.photo_id=?", (pid_b,)).fetchone()
            self.assertEqual(row[0], "张三")
            db_a.close()
            db_b.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
