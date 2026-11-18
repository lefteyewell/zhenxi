"""P3 回归：.jxl 经随包 djxl CLI（BSD-3）解码——查看/缩略图/预览/分析全链。

真实解码用仓库 bin/djxl.exe + tests/fixtures 样本（cjxl 生成，有损/无损各
一）；djxl 缺席时（如非 x64 环境）跳过真实解码测试，另配 mock 探测纯逻辑测试。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from photo_manager.core import extractor, rawio  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
LOSSY = os.path.join(FIXTURES, "fx_lossy.jxl")
LOSSLESS = os.path.join(FIXTURES, "fx_lossless.jxl")


class DjxlProbeTests(unittest.TestCase):
    def test_probe_finds_bundled_djxl(self):
        p = extractor._find_djxl()
        self.assertIsNotNone(p, "仓库 bin/djxl.exe 应可被探测到")
        self.assertTrue(os.path.isfile(p))

    def test_jxl_in_decodable_extra_exts(self):
        if extractor._find_djxl() is None:
            self.skipTest("djxl 不可用")
        self.assertIn(".jxl", extractor.decodable_extra_exts())


@unittest.skipIf(extractor._find_djxl() is None, "djxl 不可用")
class RealDecodeTests(unittest.TestCase):
    def test_read_bgr_lossless(self):
        img = rawio.read_bgr(LOSSLESS)
        self.assertEqual(img.shape[:2], (240, 320))

    def test_read_bgr_lossy(self):
        img = rawio.read_bgr(LOSSY)
        self.assertEqual(img.shape[:2], (240, 320))

    def test_thumbnail(self):
        import tempfile

        out = os.path.join(tempfile.mkdtemp(prefix="jxl_"), "t.jpg")
        try:
            r = extractor.make_thumbnail(LOSSY, out)
            self.assertIsNotNone(r)
            self.assertTrue(os.path.isfile(out))
        finally:
            if os.path.isfile(out):
                os.unlink(out)

    def test_preview_full_decode(self):
        import tempfile

        out = os.path.join(tempfile.mkdtemp(prefix="jxl_"), "p.jpg")
        try:
            r = extractor.make_preview_ex(LOSSY, out)
            self.assertIsNotNone(r)
            w, h, state = r
            self.assertEqual((w, h), (320, 240))
            self.assertEqual(state, "ok")  # djxl 全图解码 → 可信
        finally:
            if os.path.isfile(out):
                os.unlink(out)

    def test_jxl_to_png_fresh_target(self):
        import tempfile

        d = tempfile.mkdtemp(prefix="jxl_")
        dst = os.path.join(d, "o.png")
        try:
            self.assertTrue(extractor.jxl_to_png(LOSSLESS, dst))
            with Image.open(dst) as im:
                self.assertEqual(im.size, (320, 240))
        finally:
            if os.path.isfile(dst):
                os.unlink(dst)


if __name__ == "__main__":
    unittest.main()
