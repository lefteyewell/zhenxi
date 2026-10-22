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
"""0.5.43：现代手机/图像编解码格式支持回归。

守护两类不变量：
1. 白名单只收录「当前环境真正能解码」的格式——现代编解码按解码库可用性纳入、
   ImageMagick 兜底格式按 IM 可用性纳入，杜绝 HEIC 那种「加了白名单却打不开」
   的静默坏图。
2. pillow-heif 在位时，HEIC 能真正走通 缩略图 + 元数据（端到端，而非仅白名单）。
"""
import os
import tempfile
import unittest

from photo_manager.core import extractor, scanner


def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


class TestModernFormatWhitelist(unittest.TestCase):
    """白名单与「实际可解码能力」严格一致。"""

    def test_pillow_native_exts_always_on(self):
        for e in (".jpg", ".png", ".psd", ".tga", ".pcx", ".pnm", ".mpo"):
            self.assertIn(e, scanner.IMAGE_EXTS)

    def test_codec_exts_gated_on_decoder(self):
        # 有 pillow-heif → heic/heif/avif 纳入；没有则不纳入（不假支持）
        have = _have("pillow_heif")
        for e in (".heic", ".heif", ".avif"):
            self.assertEqual(e in scanner.IMAGE_EXTS, have, e)

    def test_jxl_gated(self):
        self.assertEqual(".jxl" in scanner.IMAGE_EXTS, _have("pillow_jxl_plugin"))

    def test_imagemagick_exts_gated(self):
        im = extractor.imagemagick_available()
        for e in (".fits", ".hdr", ".exr", ".flif", ".bpg", ".pcd"):
            self.assertEqual(e in scanner.IMAGE_EXTS, im, e)


class TestHeicDecode(unittest.TestCase):
    """pillow-heif 在位时，HEIC 端到端可解码（缩略图 + 元数据 + 尺寸）。"""

    def test_heic_thumbnail_and_metadata(self):
        if not _have("pillow_heif"):
            self.skipTest("pillow-heif 未安装")
        import numpy as np
        from PIL import Image
        import pillow_heif

        rng = np.random.default_rng(11)
        arr = rng.integers(40, 210, size=(240, 320, 3)).astype("uint8")
        arr[60:160, 80:240] = 25  # 一块暗区制造边缘细节
        img = Image.fromarray(arr, "RGB")
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "phone.heic")
        pillow_heif.from_pillow(img).save(p)
        self.assertGreater(os.path.getsize(p), 500)

        out = os.path.join(tmp, "tn.jpg")
        size = extractor.make_thumbnail(p, out)
        self.assertIsNotNone(size)          # 之前只加白名单时这里是 None（静默坏图）
        self.assertTrue(os.path.exists(out))

        meta = extractor.extract_metadata(p)
        self.assertEqual((meta["width"], meta["height"]), (320, 240))


if __name__ == "__main__":
    unittest.main()
