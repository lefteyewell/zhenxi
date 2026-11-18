"""P2 回归：read_bgr 的兜底链（cv2 → Pillow → ImageMagick CLI）。

cv2 解不出或只解出 <1024px 小图时，按 Pillow → ImageMagick 顺序兜底，
仅在结果更大（或 cv2 完全失败）时采纳。用 mock 注入 cv2/IM 行为，
不依赖任何可选解码插件；Pillow 路径用真实 PNG 验证。
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from photo_manager.core import rawio  # noqa: E402


def _make_png(path: str, size=(2000, 1500), color=(255, 0, 0)):
    Image.new("RGB", size, color).save(path)
    return path


class FallbackChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fb_")
        self.png = _make_png(os.path.join(self.tmp, "a.png"))

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.unlink(os.path.join(self.tmp, f))
        os.rmdir(self.tmp)

    def test_cv2_fail_pillow_rescue(self):
        """cv2 完全失败 → Pillow 兜底成功，颜色语义正确（RGB→BGR）。"""
        with mock.patch("cv2.imdecode", return_value=None):
            img = rawio.read_bgr(self.png)
        self.assertEqual(img.shape[:2], (1500, 2000))
        # 纯红 (255,0,0) → BGR [0,0,255]
        self.assertEqual(int(img[10, 10, 0]), 0)
        self.assertEqual(int(img[10, 10, 2]), 255)

    def test_cv2_small_img_fallback_upgrades(self):
        """cv2 只解出小图 → 兜底更大图被采纳。"""
        tiny = np.zeros((100, 80, 3), dtype=np.uint8)
        with mock.patch("cv2.imdecode", return_value=tiny):
            img = rawio.read_bgr(self.png)
        self.assertEqual(max(img.shape[:2]), 2000)

    def test_cv2_ok_no_fallback(self):
        """cv2 正常解出大图 → 不进兜底（保既有行为零开销）。"""
        ok = np.zeros((2000, 1500, 3), dtype=np.uint8)
        with mock.patch("cv2.imdecode", return_value=ok), \
             mock.patch.object(rawio, "_read_fallback_bgr",
                               side_effect=AssertionError("不应触发兜底")):
            img = rawio.read_bgr(self.png)
        self.assertEqual(max(img.shape[:2]), 2000)

    def test_pillow_fail_im_rescue(self):
        """Pillow 也解不出（伪 FITS 字节）→ ImageMagick CLI 兜底。"""
        p = os.path.join(self.tmp, "b.fits")
        with open(p, "wb") as f:
            f.write(b"SIMPLE  =                    T" + b"\x00" * 100)
        jpg = os.path.join(self.tmp, "im_out.jpg")
        Image.new("RGB", (1200, 900), (0, 0, 255)).save(jpg)

        def fake_im(src, dst, max_edge=1920):
            Image.open(jpg).save(dst)
            return True

        with mock.patch("photo_manager.core.extractor.imagemagick_to_jpeg",
                        side_effect=fake_im):
            img = rawio.read_bgr(p)
        self.assertEqual(img.shape[:2], (900, 1200))
        # 纯蓝 (0,0,255) → BGR [255,0,0]（JPEG 有损，允许 ±5）
        self.assertGreater(int(img[10, 10, 0]), 250)
        self.assertLess(int(img[10, 10, 2]), 5)

    def test_all_fail_raises_valueerror(self):
        """三级全失败 → 抛 ValueError（与旧语义一致，管线记错可重试）。"""
        p = os.path.join(self.tmp, "c.bin")
        with open(p, "wb") as f:
            f.write(os.urandom(256))
        with mock.patch("cv2.imdecode", return_value=None), \
             mock.patch("photo_manager.core.extractor.imagemagick_to_jpeg",
                        return_value=False):
            with self.assertRaises(ValueError):
                rawio.read_bgr(p)

    def test_fallback_smaller_not_adopted(self):
        """cv2 已解出大图但被 mock 缩小、兜底更小时 → 保留 cv2 结果。"""
        small = np.zeros((300, 200, 3), dtype=np.uint8)
        with mock.patch("cv2.imdecode", return_value=small), \
             mock.patch.object(rawio, "_read_fallback_bgr",
                               return_value=np.zeros((50, 40, 3), np.uint8)):
            img = rawio.read_bgr(self.png)
        self.assertEqual(max(img.shape[:2]), 300)


if __name__ == "__main__":
    unittest.main()
