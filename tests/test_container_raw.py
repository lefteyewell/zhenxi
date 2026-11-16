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
"""TIFF 容器型相机 RAW（0.6.32）回归测试。

背景：转换工具把 NEF 等传感器数据原样转存为 .tiff，扩展名不在 RAW_EXTS，
cv2/Pillow 只能解出百像素级内嵌缩略图甚至完全解不出，而 LibRaw 按内容
识别与扩展名无关。守护的不变量：
1. 嗅探只对 .tif/.tiff 生效且宁可漏判不误判（普通 TIFF 不被送去 demosaic）；
2. 容器型 RAW 经 read_bgr / 缩略图 / 预览 / 元数据获得真实分辨率与正立方向；
3. 普通图片（含真 TIFF）行为完全不变；
4. OCR 管线对容器型 RAW 先解码再识别；
5. 老库 .tif/.tiff 照片升级后被一次性重新排队重建（meta 标记幂等）。
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager import models_dir
from photo_manager.core import extractor, ocr as ocr_mod, rawio
from photo_manager.core.db import Database

_ROOT = Path(__file__).resolve().parents[1]
_SAMPLES = _ROOT / "SampleRAW"
_TIFF_P7100 = _SAMPLES / "TIFF_Nikon__CoolpixP7100_container.tiff"
_TIFF_D3X = _SAMPLES / "TIFF_Nikon__D3X_container.tiff"


def _make_tiff(path, size=(600, 800)):
    """生成一张普通照片 TIFF。"""
    from PIL import Image

    h, w = size
    arr = np.linspace(0, 255, w, dtype=np.uint8)
    img = Image.fromarray(np.tile(arr, (h, 1)).repeat(3).reshape(h, w, 3))
    img.save(path)
    return path


class SniffGateTests(unittest.TestCase):
    """嗅探门禁：只在 .tif/.tiff 上启用，绝不误伤普通图片。"""

    def test_non_tiff_ext_never_sniffed(self):
        for name in ("a.jpg", "a.png", "a.heic", "a.tifX", "atiff", "no_ext"):
            self.assertFalse(rawio.is_container_raw(name), name)

    def test_missing_file_returns_false(self):
        self.assertFalse(rawio.is_container_raw("definitely_missing_06230.tif"))

    def test_plain_tiff_not_sniffed(self):
        # LibRaw 打不开普通照片 TIFF（或尺寸与 Pillow 相同）→ 不命中
        with tempfile.TemporaryDirectory() as td:
            p = _make_tiff(os.path.join(td, "中文 普通.tif"))
            self.assertFalse(rawio.is_container_raw(p))
            img = rawio.read_bgr(p)
            self.assertEqual(img.shape[:2], (600, 800))

    def test_sniff_result_cached_per_file_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            p = _make_tiff(os.path.join(td, "c.tif"))
            self.assertFalse(rawio.is_container_raw(p))
            # 第二次走缓存，结果一致
            self.assertFalse(rawio.is_container_raw(p))


class NormalImageUnchangedTests(unittest.TestCase):
    """普通图片行为不变（0.6.31 及之前的语义）。"""

    def test_small_jpeg_not_sniffed(self):
        import cv2

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "小图.jpg"
            arr = np.full((80, 120, 3), 123, dtype=np.uint8)
            ok, buf = cv2.imencode(".jpg", arr)
            self.assertTrue(ok)
            buf.tofile(str(p))
            # <1024px 会尝试嗅探，但 .jpg 不在门禁内 → 行为不变
            img = rawio.read_bgr(str(p))
            self.assertEqual(int(img[0, 0, 0]), 123)

    def test_orientation_of_plain_tiff(self):
        with tempfile.TemporaryDirectory() as td:
            p = _make_tiff(os.path.join(td, "o.tif"))
            self.assertEqual(rawio.orientation(p), 1)


@unittest.skipUnless(_TIFF_P7100.exists(), "SampleRAW 容器 RAW 样本不存在")
class ContainerRawReadTests(unittest.TestCase):
    """容器型 RAW 读图 / 方向 / 人脸 / OCR 接线（真实样片）。"""

    def test_sniff_detects_container(self):
        self.assertTrue(rawio.is_container_raw(str(_TIFF_P7100)))
        self.assertTrue(rawio.is_container_raw(str(_TIFF_D3X)))

    def test_read_bgr_usable_resolution(self):
        # P7100 此前 cv2/PIL 完全解不出（cannot identify image file）
        img = rawio.read_bgr(str(_TIFF_P7100))
        self.assertEqual(img.ndim, 3)
        self.assertGreaterEqual(max(img.shape[:2]), 1024)

    def test_orientation_is_1_and_image_upright(self):
        # D3X 外层 TIFF Orientation tag=8，但像素流（内嵌预览）已正立：
        # read_bgr 返回正立竖构图，orientation() 恒 1（调用方不再按 tag 双转）。
        img = rawio.read_bgr(str(_TIFF_D3X))
        h, w = img.shape[:2]
        self.assertGreater(h, w)  # 竖构图
        self.assertEqual(rawio.orientation(str(_TIFF_D3X)), 1)

    def test_faces_detect_on_container(self):
        from photo_manager.core.faces import FaceService

        svc = FaceService(models_dir())
        dets = svc.process_image(str(_TIFF_P7100))
        self.assertGreaterEqual(len(dets), 1)

    def test_ocr_pipeline_decodes_container_before_rapidocr(self):
        # 接线测试：容器型 RAW 必须先 read_bgr 成 ndarray 再交给 RapidOCR，
        # 而不是把路径丢给 RapidOCR 自行解码（此前报 cannot identify image file）。
        seen = {}

        def fake_worker(img):
            seen["img"] = img
            return None, 0

        fake = np.zeros((4, 4, 3), dtype=np.uint8)
        with patch.object(rawio, "read_bgr", return_value=fake) as rd, \
             patch.object(rawio, "is_container_raw", return_value=True), \
             patch.object(ocr_mod, "_worker", side_effect=fake_worker):
            ocr_mod._work(str(_TIFF_P7100))
        rd.assert_called_once_with(str(_TIFF_P7100))
        self.assertIsInstance(seen["img"], np.ndarray)


@unittest.skipUnless(_TIFF_D3X.exists(), "SampleRAW 容器 RAW 样本不存在")
class ContainerExtractorTests(unittest.TestCase):
    """元数据 / 缩略图 / 预览对容器型 RAW 的输出。"""

    def test_metadata_uses_libraw_dimensions(self):
        meta = extractor.extract_metadata(str(_TIFF_D3X))
        # 此前记成内嵌缩略图的 120×160
        self.assertGreaterEqual(meta["width"], 3000)
        self.assertGreaterEqual(meta["height"], 2000)
        self.assertEqual(meta["camera_model"], "NIKON D3X")

    def test_thumbnail_upright_and_usable(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "t.jpg")
            size = extractor.make_thumbnail(str(_TIFF_D3X), out)
            self.assertIsNotNone(size)
            w, h = size
            self.assertLess(w, h)  # 竖构图（此前横躺 120×160）

    def test_preview_usable_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "p.jpg")
            r = extractor.make_preview_ex(str(_TIFF_D3X), out)
            self.assertIsNotNone(r)
            w, h, state = r
            self.assertGreaterEqual(max(w, h), 1024)
            self.assertIn(state, ("ok", "unverified"))


class ContainerReindexMigrationTest(unittest.TestCase):
    """老库 .tif/.tiff 照片升级后一次性重新排队（status → pending）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "lib.db")
        self.db = Database(self.path).connect()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _seed(self, file_path, status="indexed", error=None):
        c = self.db.conn
        name = os.path.basename(file_path)
        ext = os.path.splitext(name)[1].lower()
        c.execute(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
            " file_mtime, taken_at, sort_key, status, media_type, error)"
            " VALUES (?,?,?,?,?,?,?, ?, ?, 'photo', ?)",
            (file_path, name, "/fake", ext, 1000, 100.0,
             "2025-03-02T10:00:00", "2025-03-02T10:00:00", status, error),
        )
        c.commit()
        return c.execute(
            "SELECT id FROM photos WHERE file_path=?", (file_path,)).fetchone()[0]

    def _status(self, pid):
        return self.db.conn.execute(
            "SELECT status, error FROM photos WHERE id=?", (pid,)).fetchone()

    def test_tiff_photos_requeued_once(self):
        p1 = self._seed("/fake/a.tiff", status="indexed")
        p2 = self._seed("/fake/b.TIFF", status="failed", error="extract error")
        p3 = self._seed("/fake/c.tif", status="error", error="ocr: boom")
        pj = self._seed("/fake/d.jpg", status="indexed")
        self.db.conn.execute(
            "DELETE FROM meta WHERE key='container_raw_reindex'")
        self.db.conn.commit()
        self.db.close()
        self.db = Database(self.path).connect()

        self.assertEqual(self._status(p1), ("pending", None))
        self.assertEqual(self._status(p2), ("pending", None))
        self.assertEqual(self._status(p3), ("pending", None))
        self.assertEqual(self._status(pj)[0], "indexed")  # 普通照片不动

        # 幂等：标记已打，用户扫描入库完成后（pending→indexed）不会被再次打回
        self.db.conn.execute(
            "UPDATE photos SET status='indexed' WHERE id=?", (p1,))
        self.db.conn.commit()
        self.db.close()
        self.db = Database(self.path).connect()
        self.assertEqual(self._status(p1)[0], "indexed")

    def test_missing_and_pending_delete_untouched(self):
        pm = self._seed("/fake/m.tiff", status="missing")
        pd = self._seed("/fake/p.tiff", status="pending_delete")
        self.db.conn.execute(
            "DELETE FROM meta WHERE key='container_raw_reindex'")
        self.db.conn.commit()
        self.db.close()
        self.db = Database(self.path).connect()
        self.assertEqual(self._status(pm)[0], "missing")
        self.assertEqual(self._status(pd)[0], "pending_delete")

    def test_fresh_library_gets_marker_without_requeue(self):
        # 全新库（无 TIFF 行）直接打标记，此后新导入分析完的 TIFF 不受影响
        row = self.db.conn.execute(
            "SELECT value FROM meta WHERE key='container_raw_reindex'").fetchone()
        self.assertEqual(row, ("1",))


class QtNativeBypassTests(unittest.TestCase):
    """0.6.32b 漏网回归：.tif/.tiff 在 QT_NATIVE_EXTS 里，容器 RAW 不得绕过解码链。

    实机暴露：photoViewUrl 对 .tiff 直接把原文件交给 QML（Qt TIFF 插件
    解不出 → 预览空白；只解出内嵌缩略图 → 预览特小），integrity 的
    深度校验也把 .tif/.tiff 提前 continue，0.6.32 加的容器分支永远不可达。
    """

    def test_container_tiff_not_served_as_qt_native(self):
        # photoViewUrl 直载判定 = ext in QT_NATIVE_EXTS and not is_container_raw
        self.assertIn(".tiff", extractor.QT_NATIVE_EXTS)  # 前提成立才防得住
        self.assertTrue(rawio.is_container_raw(str(_TIFF_D3X)))
        self.assertFalse(
            ".tiff" in extractor.QT_NATIVE_EXTS
            and not rawio.is_container_raw(str(_TIFF_D3X)))

    def test_plain_tiff_still_served_as_qt_native(self):
        with tempfile.TemporaryDirectory() as td:
            p = _make_tiff(os.path.join(td, "plain.tif"))
            self.assertTrue(
                ".tif" in extractor.QT_NATIVE_EXTS
                and not rawio.is_container_raw(p))

    def test_deep_decode_check_covers_container_tiff(self):
        from photo_manager.core import integrity

        with tempfile.TemporaryDirectory() as td:
            dst = os.path.join(td, "container.tiff")
            shutil.copyfile(str(_TIFF_D3X), dst)
            db = Database(os.path.join(td, "lib.db")).connect()
            try:
                c = db.conn
                c.execute(
                    "INSERT INTO photos(file_path, file_name, folder_path, ext,"
                    " file_size, file_mtime, taken_at, sort_key, status,"
                    " media_type, decode_error)"
                    " VALUES (?,?,?,?,?,?,?,?,'indexed','photo',0)",
                    (dst, "container.tiff", td.replace("\\", "/"), ".tiff",
                     1000, 100.0, "2025-03-02T10:00:00", "2025-03-02T10:00:00"))
                c.commit()
                r = integrity.deep_decode_check(c)
                self.assertGreaterEqual(r["scanned"], 1)  # 未被 QT_NATIVE 跳过
                row = c.execute(
                    "SELECT decode_error FROM photos").fetchone()
                self.assertEqual(row, (0,))  # LibRaw 校验通过，未误标损坏
            finally:
                db.close()

    def test_deep_decode_check_still_skips_plain_tiff(self):
        from photo_manager.core import integrity

        with tempfile.TemporaryDirectory() as td:
            dst = os.path.join(td, "plain.tif")
            _make_tiff(dst)
            db = Database(os.path.join(td, "lib.db")).connect()
            try:
                c = db.conn
                c.execute(
                    "INSERT INTO photos(file_path, file_name, folder_path, ext,"
                    " file_size, file_mtime, taken_at, sort_key, status,"
                    " media_type, decode_error)"
                    " VALUES (?,?,?,?,?,?,?,?,'indexed','photo',0)",
                    (dst, "plain.tif", td.replace("\\", "/"), ".tif",
                     1000, 100.0, "2025-03-02T10:00:00", "2025-03-02T10:00:00"))
                c.commit()
                r = integrity.deep_decode_check(c)
                self.assertEqual(r["scanned"], 0)  # 原生格式照旧跳过
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
