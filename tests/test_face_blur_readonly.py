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
"""0.5.37：人脸模糊指数与只读锁定单元测试（离线、不依赖真实人脸照片）。"""
import os
import stat
import tempfile
import unittest

import cv2
import numpy as np

from photo_manager.core.faces import _blur_index
from photo_manager.core.system import set_files_readonly


def _synth_face(n=128):
    """合成「人脸感」图案：平滑底 + 眼/嘴特征（无真实照片也能测判别力）。"""
    img = np.full((n, n, 3), 180, dtype=np.uint8)
    cv2.circle(img, (int(n*0.35), int(n*0.39)), max(2, n//21), (40, 40, 40), -1)
    cv2.circle(img, (int(n*0.65), int(n*0.39)), max(2, n//21), (40, 40, 40), -1)
    cv2.ellipse(img, (n//2, int(n*0.66)), (int(n*0.11), int(n*0.06)),
                0, 0, 360, (120, 60, 60), -1)
    return img


def _detailed_face(n=128):
    """带发丝/皮肤纹理的合成脸（更贴近真实人脸的细节密度）。

    0.5.42：模糊指数改为「归一化高频能量比」，对低对比度/低细节图会更易读成
    偏糊（因为没有细节可供判别）。真实人脸总有发丝/毛孔纹理，故用带纹理的图作
    「清晰人脸」的公平代理，避免用近乎纯色的 _synth_face 误判算法。
    """
    img = np.full((n, n, 3), 200, dtype=np.uint8)
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    shade = 30 * np.sin(xs / n * 3.0) + 20 * np.cos(ys / n * 2.0)
    img = np.clip(img.astype(np.float32) + shade[..., None], 0, 255).astype(np.uint8)
    rng = np.random.default_rng(7)
    hair = rng.integers(0, 60, size=(n, n), dtype=np.int16)
    img[:int(n*0.45)] = np.clip(
        img[:int(n*0.45)].astype(np.int16) - hair[:int(n*0.45), :, None],
        0, 255).astype(np.uint8)
    cv2.circle(img, (int(n*0.35), int(n*0.42)), max(3, n//18), (30, 30, 30), -1)
    cv2.circle(img, (int(n*0.65), int(n*0.42)), max(3, n//18), (30, 30, 30), -1)
    cv2.rectangle(img, (int(n*0.30), int(n*0.30)), (int(n*0.40), int(n*0.33)), (20, 20, 20), -1)
    cv2.rectangle(img, (int(n*0.60), int(n*0.30)), (int(n*0.70), int(n*0.33)), (20, 20, 20), -1)
    cv2.ellipse(img, (n//2, int(n*0.72)), (int(n*0.13), int(n*0.06)), 0, 0, 360, (110, 50, 50), -1)
    return img


class TestBlurIndex(unittest.TestCase):
    """0.5.42：指数语义 = 可辨认程度（越大越难辨认），且内容/尺寸无关。"""

    def test_flat_image_is_max_blurry(self):
        """纯色图（无从辨认）→ 100。"""
        img = np.full((64, 64, 3), 128, dtype=np.uint8)
        self.assertEqual(_blur_index(img), 100)

    def test_noisy_image_is_sharp(self):
        """强噪声（细节极丰富）→ 指数 0 附近。"""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
        self.assertLessEqual(_blur_index(img), 10)

    def test_sharp_face_scores_low(self):
        """清晰（带纹理）人脸 → 低指数（可辨认）。"""
        self.assertLessEqual(_blur_index(_detailed_face(128)), 15)

    def test_heavy_blur_scores_high(self):
        """重度模糊（11x11 σ4）→ 高指数（难辨认）。"""
        blurred = cv2.GaussianBlur(_synth_face(128), (11, 11), 4)
        self.assertGreaterEqual(_blur_index(blurred), 70)

    def test_small_sharp_face_not_flagged(self):
        """40px 小而清晰的脸不再被误判糊（0.5.37 旧算法的主要误报场景）。"""
        small = cv2.resize(_detailed_face(128), (40, 40),
                           interpolation=cv2.INTER_AREA)
        self.assertLessEqual(_blur_index(small), 30)

    def test_small_heavy_blur_detected(self):
        """40px 重度模糊的脸仍能检出（不因尺寸小而漏报）。"""
        b = cv2.GaussianBlur(_synth_face(128), (11, 11), 4)
        small = cv2.resize(b, (40, 40), interpolation=cv2.INTER_AREA)
        self.assertGreater(_blur_index(small),
                           _blur_index(cv2.resize(_synth_face(128), (40, 40),
                                                  interpolation=cv2.INTER_AREA)))

    def test_size_consistency(self):
        """同一（带纹理）清晰图案 64px 与 256px 得分接近（尺寸无关，容许量化误差）。"""
        c64 = _detailed_face(64)
        c256 = _detailed_face(256)
        self.assertLessEqual(abs(_blur_index(c64) - _blur_index(c256)), 8)

    def test_clear_face_not_flagged_regression(self):
        """0.5.42 回归：清晰人脸绝不被误判为模糊（0.5.40 把清晰脸打到 19~62）。

        清晰（带纹理）脸的指数必须远低于阈值 60，且与同图重度模糊拉开 ≥55 的差距。
        """
        sharp = _blur_index(_detailed_face(128))
        blurred = _blur_index(cv2.GaussianBlur(_detailed_face(128), (11, 11), 4))
        self.assertLess(sharp, 20)
        self.assertGreaterEqual(blurred, 70)
        self.assertGreaterEqual(blurred - sharp, 55)

    def test_index_bounded(self):
        """任意输入都夹在 0-100。"""
        img = np.random.default_rng(1).integers(
            0, 255, size=(16, 16, 3), dtype=np.uint8)
        v = _blur_index(img)
        self.assertTrue(0 <= v <= 100)


class TestSetFilesReadonly(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.dir.name, "a.jpg")
        with open(self.p, "wb") as f:
            f.write(b"x")

    def tearDown(self):
        # 清理前先解锁，避免 Windows 上只读文件无法删除
        set_files_readonly([self.p], False)
        self.dir.cleanup()

    def test_lock_and_unlock(self):
        ok, skip = set_files_readonly([self.p], True)
        self.assertEqual((ok, skip), (1, 0))
        cur = os.stat(self.p).st_mode
        self.assertFalse(cur & stat.S_IWRITE)

        ok, skip = set_files_readonly([self.p], False)
        self.assertEqual((ok, skip), (1, 0))
        self.assertTrue(os.stat(self.p).st_mode & stat.S_IWRITE)

    def test_lock_twice_is_idempotent(self):
        set_files_readonly([self.p], True)
        ok, skip = set_files_readonly([self.p], True)
        self.assertEqual((ok, skip), (1, 0))

    def test_missing_file_skipped(self):
        ok, skip = set_files_readonly([os.path.join(self.dir.name, "nope.jpg")], True)
        self.assertEqual((ok, skip), (0, 1))


if __name__ == "__main__":
    unittest.main()
