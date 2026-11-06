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
"""人脸服务回归测试：验证 YuNet 关键点/分数索引与 alignCrop 完整行传递（修复 f[4]/bbox 误用）；
0.6.21 上传人脸搜图的人脸选择器（face_index 指定人脸 + 全部人脸缩略图导出）。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import photo_manager.core.faces as faces_mod
from photo_manager.core.faces import FaceService, detect_faces_for_search, search_by_face
from photo_manager.core.db import Database


class _FakeDetector:
    def __init__(self, faces):
        self._faces = faces

    def setInputSize(self, size):
        pass

    def detect(self, img):
        return None, self._faces


class _FakeRecognizer:
    def __init__(self):
        self.last_align_input = None

    def alignCrop(self, img, coords):
        self.last_align_input = np.asarray(coords, dtype=np.float32).copy()
        return np.zeros((112, 112, 3), dtype=np.float32)

    def feature(self, aligned):
        return np.zeros((1, 128), dtype=np.float32)


class TestFaceService(unittest.TestCase):
    def setUp(self):
        self.svc = FaceService("models")
        # YuNet 输出：bbox(4) + 右眼(2) + 左眼(2) + 鼻尖(2) + 右嘴角(2) + 左嘴角(2) + score(1) = 15
        row = np.array([[100, 80, 60, 80, 110, 100, 150, 100, 130, 120, 110, 140, 150, 140, 0.93]],
                       dtype=np.float32)
        self.svc._load = lambda: (_FakeDetector(row), _FakeRecognizer())
        self.row = row[0]

    def test_detect_uses_score_index_14(self):
        faces = self.svc.detect(np.zeros((300, 300, 3), dtype=np.uint8))
        self.assertEqual(len(faces), 1)
        f = faces[0]
        self.assertEqual(f["bbox"], [100.0, 80.0, 60.0, 80.0])
        self.assertEqual(len(f["landmarks"]), 10)
        self.assertAlmostEqual(f["score"], 0.93, places=5,
                               msg="score 必须取第 15 列(f[14])，而非右眼坐标 f[4]")
        self.assertEqual(len(f["row"]), 15)
        np.testing.assert_array_equal(f["row"], self.row)

    def test_feature_passes_full_row_to_aligncrop(self):
        rec = _FakeRecognizer()
        self.svc._load = lambda: (_FakeDetector(self.row[None, :]), rec)
        face = {"row": self.row}
        self.svc.feature(np.zeros((300, 300, 3), dtype=np.uint8), face)
        self.assertIsNotNone(rec.last_align_input)
        self.assertEqual(rec.last_align_input.shape, (15,),
                         "alignCrop 必须收到完整 15 元素（bbox+5关键点），否则裁剪错位")
        np.testing.assert_array_equal(rec.last_align_input, self.row)


class _FakeSearchSvc:
    """detect 固定返回 3 张脸（score 0.93/0.75/0.60，bbox x 各不同）；
    feature 用 bbox 的 x 坐标编码 one-hot 身份向量（同人同 x → 相似度 1）。"""

    FACES = [(100, 80, 60, 80, 0.93),   # 置信度最高
             (500, 200, 40, 40, 0.75),  # 次之
             (300, 300, 50, 50, 0.60)]  # 最低

    def __init__(self, models_dir):
        self.rows = []
        for (x, y, w, h, s) in self.FACES:
            r = np.zeros(15, dtype=np.float32)
            r[:4] = (x, y, w, h)
            r[14] = s
            self.rows.append(r)

    def _load(self):
        return None, None

    def detect(self, img):
        return [{"bbox": [float(v) for v in r[:4]], "landmarks": [0.0] * 10,
                 "score": float(r[14]), "row": r} for r in self.rows]

    def feature(self, img, face):
        v = np.zeros(128, dtype=np.float32)
        v[int(face["bbox"][0]) % 128] = 1.0
        return v


def _identity_vec(x: int) -> bytes:
    v = np.zeros(128, dtype=np.float32)
    v[x % 128] = 1.0
    return v.astype(np.float32).tobytes()


class TestFaceSearchPicker(unittest.TestCase):
    """0.6.21 人脸选择器：多张脸时 face_index 指定搜索哪一张。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._patcher = patch.object(faces_mod, "FaceService", _FakeSearchSvc)
        self._patcher.start()
        # 真实小图（_read_image 走 cv2 解码）
        import cv2

        self.img_path = os.path.join(self.tmp.name, "query.jpg")
        ok, buf = cv2.imencode(".jpg", np.full((480, 640, 3), 128, np.uint8))
        assert ok
        buf.tofile(self.img_path)

    def tearDown(self):
        self._patcher.stop()
        self.tmp.cleanup()

    def _make_db_with_faces(self):
        db = Database(os.path.join(self.tmp.name, "lib.db")).connect()
        ids = {}
        for i, x in enumerate((100, 300, 500)):
            db.conn.execute(
                "INSERT INTO photos(file_path, file_name, folder_path, ext,"
                " file_size, file_mtime, taken_at, sort_key, status)"
                " VALUES (?,?,?,?,?,?,?,?, 'indexed')",
                (f"/fake/lib{i}.jpg", f"lib{i}.jpg", "d", ".jpg",
                 1000, 100.0, f"2025-03-0{i + 1}T10:00:00", f"2025-03-0{i + 1}"),
            )
            pid = db.conn.execute(
                "SELECT id FROM photos WHERE file_path=?",
                (f"/fake/lib{i}.jpg",)).fetchone()[0]
            db.conn.execute(
                "INSERT INTO faces(photo_id, bbox, descriptor, score)"
                " VALUES (?,?,?,0.9)",
                (pid, f"[{x},0,10,10]", _identity_vec(x)))
            ids[x] = pid
        db.conn.commit()
        return db, ids

    def test_face_index_selects_requested_face(self):
        """face_index 与 detect_faces_for_search 同序（置信度降序）。"""
        db, ids = self._make_db_with_faces()
        try:
            # -1（默认）= 置信度最高（x=100）
            res = search_by_face(db, self.img_path, "models")
            self.assertEqual([r[0] for r in res], [ids[100]])
            # index 1 = 次高（x=500）
            res = search_by_face(db, self.img_path, "models", face_index=1)
            self.assertEqual([r[0] for r in res], [ids[500]])
            # index 2 = 最低（x=300）
            res = search_by_face(db, self.img_path, "models", face_index=2)
            self.assertEqual([r[0] for r in res], [ids[300]])
            # 越界 → 回退置信度最高
            res = search_by_face(db, self.img_path, "models", face_index=99)
            self.assertEqual([r[0] for r in res], [ids[100]])
        finally:
            db.close()

    def test_detect_faces_for_search_lists_all_with_thumbs(self):
        """全部人脸按置信度降序导出，缩略图真实落盘，index 可回传 search_by_face。"""
        out = detect_faces_for_search(self.img_path, "models")
        self.assertEqual(len(out), 3)
        scores = [f["score"] for f in out]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([f["index"] for f in out], [0, 1, 2])
        for f in out:
            self.assertTrue(os.path.isfile(f["thumb"]) and
                            os.path.getsize(f["thumb"]) > 0,
                            f"缩略图应落盘: {f['thumb']}")
            self.assertTrue(f["thumb"].endswith(".jpg"))

    def test_detect_faces_for_search_no_face_returns_empty(self):
        class _NoFaceSvc(_FakeSearchSvc):
            def detect(self, img):
                return []

        with patch.object(faces_mod, "FaceService", _NoFaceSvc):
            self.assertEqual(detect_faces_for_search(self.img_path, "models"), [])


if __name__ == "__main__":
    unittest.main()
