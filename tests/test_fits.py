"""P4 回归：内置迷你 FITS 解析器（零依赖）——读图/缩略图/预览/白名单。

测试内自带 FITS 生成器（2880 字节块 + 标准头部卡 + 大端数据），覆盖
BITPIX 8/16(BZERO)/-32、2D 灰度、3D RGB、截断/坏文件容错，及
read_bgr / make_thumbnail / make_preview_ex / decodable_extra_exts 接入。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from photo_manager.core import extractor, fitsread, rawio  # noqa: E402

BLOCK = 2880


def _write_fits(path: str, bitpix: int, data: np.ndarray, *, axes=None,
                bscale=None, bzero=None):
    """写一个最简单 HDU 的 FITS。data 形状按 numpy C 序（h, w[, c]）。"""
    if axes is None:
        axes = list(data.shape[::-1])  # FITS NAXIS1 是最快轴
    cards = [
        ("SIMPLE", True),
        ("BITPIX", bitpix),
        ("NAXIS", len(axes)),
    ]
    for i, a in enumerate(axes, 1):
        cards.append((f"NAXIS{i}", a))
    if bscale is not None:
        cards.append(("BSCALE", bscale))
    if bzero is not None:
        cards.append(("BZERO", bzero))
    cards.append(("EXTEND", True))
    cards.append(("END", None))

    def fmt(k, v):
        if isinstance(v, bool):
            return f"{k:<8}= {'>T' if v else '>F':>20}".ljust(80)
        if isinstance(v, int):
            return f"{k:<8}= {v:>20d}".ljust(80)
        if isinstance(v, float):
            return f"{k:<8}= {v:>20.6E}".ljust(80)
        return f"{k:<8}= {v!r:<20}".ljust(80)

    # 每张卡严格 80 字节（FITS 标准）；END 卡独占一张（无值），其后补空格卡至整块
    header = "".join(fmt(k, v) for k, v in cards if k != "END") + "END".ljust(80)
    header = header.ljust(BLOCK)
    dt = {8: "u1", 16: ">i2", 32: ">i4", 64: ">i8",
          -32: ">f4", -64: ">f8"}[bitpix]
    payload = data.astype(dt).tobytes()
    payload += b"\x00" * ((BLOCK - len(payload) % BLOCK) % BLOCK)
    with open(path, "wb") as f:
        f.write(header.encode("ascii") + payload)


class FitsReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fits_")

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.unlink(os.path.join(self.tmp, f))
        os.rmdir(self.tmp)

    def _p(self, name):
        return os.path.join(self.tmp, name)

    def test_bitpix8_2d(self):
        p = self._p("a.fits")
        _write_fits(p, 8, np.arange(256, dtype=np.uint8).reshape(16, 16))
        arr, err = fitsread.read_fits_array(p)
        self.assertEqual(err, "")
        self.assertEqual(arr.shape, (16, 16))
        self.assertEqual(arr.dtype, np.uint8)
        self.assertEqual(int(arr[0, 0]), 0)
        self.assertEqual(int(arr[15, 15]), 255)

    def test_bitpix16_bzero(self):
        """16 位无符号惯例（BZERO=32768）：天文 16 位 CCD 常见形态。"""
        p = self._p("b.fits")
        data = np.arange(-32768, -32768 + 4096, dtype=">i2").reshape(32, 128)
        _write_fits(p, 16, data, bscale=1.0, bzero=32768.0)
        arr, err = fitsread.read_fits_array(p)
        self.assertEqual(err, "")
        self.assertEqual(arr.dtype, np.uint8)
        # 0..4095 的线性梯度 → 拉伸后应大致单调递增
        self.assertLess(int(arr[0, 0]), int(arr[31, 127]))

    def test_float32(self):
        p = self._p("c.fits")
        data = np.linspace(0, 1e-9, 4096).astype(">f4").reshape(64, 64)
        _write_fits(p, -32, data)
        arr, err = fitsread.read_fits_array(p)
        self.assertEqual(err, "")
        self.assertLess(int(arr[0, 0]), int(arr[63, 63]))

    def test_rgb_3d(self):
        p = self._p("d.fits")
        # FITS 数据立方体按平面存储：data 形状 (平面数, h, w)，z 轴最慢
        data = np.zeros((3, 16, 16), dtype=np.uint8)
        data[0] = 255  # 首平面 = R
        _write_fits(p, 8, data)  # axes = (w, h, 3)
        arr, err = fitsread.read_fits_array(p)
        self.assertEqual(err, "")
        self.assertEqual(arr.shape, (16, 16, 3))
        self.assertEqual(int(arr[0, 0, 0]), 255)  # R 通道

    def test_truncated_and_bad(self):
        p = self._p("e.fits")
        _write_fits(p, 8, np.zeros((16, 16), np.uint8))
        raw = open(p, "rb").read()
        open(self._p("f.fits"), "wb").write(raw[:BLOCK])  # 砍掉数据块
        arr, err = fitsread.read_fits_array(self._p("f.fits"))
        self.assertIsNone(arr)
        self.assertIn("截断", err)
        bad = self._p("g.fits")
        with open(bad, "wb") as f:
            f.write(b"not fits at all" * 8)
        arr2, err2 = fitsread.read_fits_array(bad)
        self.assertIsNone(arr2)

    def test_read_bgr_integration(self):
        p = self._p("h.fits")
        _write_fits(p, 8, np.full((16, 16), 200, np.uint8))
        img = rawio.read_bgr(p)
        self.assertEqual(img.shape, (16, 16, 3))

    def test_thumbnail_and_preview(self):
        p = self._p("i.fits")
        _write_fits(p, 8, np.random.default_rng(7).integers(
            0, 256, (600, 800), dtype=np.uint8))
        out = os.path.join(self.tmp, "t.jpg")
        r = extractor.make_thumbnail(p, out)
        self.assertIsNotNone(r)
        prev = os.path.join(self.tmp, "p.jpg")
        r2 = extractor.make_preview_ex(p, prev)
        self.assertIsNotNone(r2)
        self.assertEqual(r2[2], "ok")

    def test_whitelist_always_includes_fits(self):
        self.assertTrue({".fits", ".fit", ".fts"} <= extractor.decodable_extra_exts())


if __name__ == "__main__":
    unittest.main()
