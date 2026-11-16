# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 (the License), or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""相机 RAW 在人脸 / OCR 分析链上的回归测试。

守护三类不变量：
1. 各品牌 RAW 扩展名一视同仁，且五处扩展名集合不漂移（.raw 有意排除）；
2. rawio 能把 RAW 解成足够分辨率的 BGR 图（含内嵌预览过小 / 全图后处理
   失败的兜底），普通图片行为不变；
3. faces / ocr 两条管线确实走了 RAW 解码分支（此前 cv2 / RapidOCR 直接读
   原路径，RAW 永久分析失败或被误标「已完成但零结果」）。
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from photo_manager import models_dir
from photo_manager.core import clip, extractor, faces as faces_mod, ocr as ocr_mod, rawio, scanner
from photo_manager.core.faces import FaceService

_ROOT = Path(__file__).resolve().parents[1]
_SAMPLES = _ROOT / "SampleRAW"
_ARW = _SAMPLES / "ARW_Sony2__DSC00009.ARW"
_ARW_PORTRAIT = _SAMPLES / "ARW_Sony__DSC00018.ARW"
_CR2 = _SAMPLES / "CR2_Canon__IMG_1107.CR2"
_ORF = _SAMPLES / "ORF_Olympus__RAW_OLYMPUS_C5050Z.ORF"


class RawExtCoverage(unittest.TestCase):
    def test_every_brand_extension_is_recognized(self):
        self.assertGreaterEqual(len(rawio.RAW_EXTS), 40)
        for ext in rawio.RAW_EXTS:
            with self.subTest(ext=ext):
                self.assertTrue(rawio.is_raw("IMG" + ext), ext)
                self.assertTrue(rawio.is_raw("IMG" + ext.upper()), ext.upper())
        for name in ("a.jpg", "a.tif", "a.png", "a.heic", "a.mp4", "no_ext"):
            self.assertFalse(rawio.is_raw(name), name)
        # 通用后缀 .raw 被 scanner 有意排除（易误判的非相机二进制），
        # rawio 必须与之一致，否则会误走 rawpy 分支。
        self.assertFalse(rawio.is_raw("a.raw"))

    def test_all_ext_sets_in_sync(self):
        self.assertEqual(set(rawio.RAW_EXTS), set(scanner.RAW_EXTS))
        self.assertEqual(set(rawio.RAW_EXTS), set(extractor._RAW_EXTS))
        self.assertEqual(set(rawio.RAW_EXTS), set(clip.RAW_EXTS))
        # library_bridge 的集合是类属性，用源码解析避免导入整个 UI 桥接层
        src = (_ROOT / "photo_manager/ui/library_bridge.py").read_text(encoding="utf-8")
        block = re.search(r"_HQ_SKIP_EXTS\s*=\s*\{([^}]*)\}", src)
        self.assertIsNotNone(block)
        hq = set(re.findall(r'"(\.[a-z0-9]+)"', block.group(1)))
        self.assertEqual(hq, set(rawio.RAW_EXTS))


class ReadBgrTests(unittest.TestCase):
    def test_plain_image_unchanged(self):
        import cv2

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "中文 图.jpg"
            arr = np.full((80, 120, 3), 123, dtype=np.uint8)
            ok, buf = cv2.imencode(".jpg", arr)
            self.assertTrue(ok)
            buf.tofile(str(p))  # cv2.imwrite 写不了中文路径
            img = rawio.read_bgr(str(p))
            self.assertEqual(img.shape, (80, 120, 3))
            self.assertEqual(int(img[0, 0, 0]), 123)

    def test_missing_file_raises(self):
        # 保持旧 cv2 路径的原生行为：np.fromfile 抛 FileNotFoundError，
        # 人脸/OCR 管线的 except Exception 会捕获并记为待分析。
        with self.assertRaises((FileNotFoundError, ValueError)):
            rawio.read_bgr("definitely_missing_06230.jpg")

    @unittest.skipUnless(_ARW.exists(), "SampleRAW/ARW 样本不存在")
    def test_arw_decodes_at_usable_resolution(self):
        img = rawio.read_bgr(str(_ARW))
        self.assertEqual(img.ndim, 3)
        # cv2 对该文件返回 None；修复后至少要有检测人脸所需的分辨率
        self.assertGreaterEqual(max(img.shape[:2]), 1024)

    @unittest.skipUnless(_ARW_PORTRAIT.exists(), "竖拍 ARW 样本不存在")
    def test_raw_exif_orientation(self):
        # Sony 竖拍 ARW 的 Orientation=8；Pillow 打不开 RAW，必须走 exifread
        self.assertEqual(rawio.orientation(str(_ARW_PORTRAIT)), 8)

    @unittest.skipUnless(_ORF.exists(), "老款 ORF 样本不存在")
    def test_tiny_thumb_and_failed_postprocess_still_returns_image(self):
        # Olympus C5050Z：内嵌预览仅 120×160，LibRaw 全图后处理抛
        # LibRawIOError；必须退到小预览而不是抛异常让照片永久滞留待分析。
        img = rawio.read_bgr(str(_ORF))
        self.assertEqual(img.ndim, 3)
        self.assertGreater(max(img.shape[:2]), 0)


class PipelineWiringTests(unittest.TestCase):
    def test_face_process_image_reads_via_rawio(self):
        svc = FaceService(models_dir())
        fake = np.zeros((120, 160, 3), dtype=np.uint8)
        with patch.object(rawio, "read_bgr", return_value=fake) as rd, \
             patch.object(rawio, "orientation", return_value=1), \
             patch.object(svc, "detect", return_value=[]):
            self.assertEqual(svc.process_image("photo.ARW"), [])
        rd.assert_called_once_with("photo.ARW")

    def test_face_search_read_image_reads_via_rawio(self):
        fake = np.zeros((120, 160, 3), dtype=np.uint8)
        with patch.object(rawio, "read_bgr", return_value=fake) as rd:
            out = faces_mod._read_image("photo.CR3")
        self.assertEqual(out.shape, (120, 160, 3))
        rd.assert_called_once_with("photo.CR3")

    def test_ocr_raw_passes_ndarray_not_path(self):
        fake = np.zeros((120, 160, 3), dtype=np.uint8)
        with patch.object(rawio, "read_bgr", return_value=fake), \
             patch.object(ocr_mod, "_worker") as worker:
            worker.return_value = (None, 0)
            self.assertEqual(ocr_mod._work("photo.NEF"), [])
        self.assertIsInstance(worker.call_args[0][0], np.ndarray)

    def test_ocr_plain_image_keeps_original_path(self):
        with patch.object(ocr_mod, "_worker") as worker:
            worker.return_value = (None, 0)
            self.assertEqual(ocr_mod._work("photo.jpg"), [])
        self.assertEqual(worker.call_args[0][0], "photo.jpg")


class RawMetadataSizeTests(unittest.TestCase):
    @unittest.skipUnless(_CR2.exists(), "SampleRAW/CR2 样本不存在")
    def test_raw_uses_sensor_size_not_embedded_thumb(self):
        # Pillow 能打开 TIFF 系 RAW，但 im.size 是内嵌缩略图（128×96）。
        meta = extractor.extract_metadata(str(_CR2))
        self.assertGreater(meta["width"], 1000)
        self.assertGreater(meta["height"], 700)


if __name__ == "__main__":
    unittest.main()
