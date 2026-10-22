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
"""人脸服务回归测试：验证 YuNet 关键点/分数索引与 alignCrop 完整行传递（修复 f[4]/bbox 误用）。"""
import unittest

import numpy as np

from photo_manager.core.faces import FaceService


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


if __name__ == "__main__":
    unittest.main()
