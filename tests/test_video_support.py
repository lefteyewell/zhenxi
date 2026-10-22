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
"""0.5.44 视频管理 V1：扫描识别 / cv2 缩略图+元数据 / 入库字段 / 分析门禁 / bridge 透传。

V1 编目级：视频有缩略图+时长+分辨率，但不做人脸/OCR/语义（分析链 media_type 门禁）。
"""
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from photo_manager.core import extractor, scanner
from photo_manager.core.db import Database
from photo_manager.core.pipeline import IngestPipeline


def _make_mp4(path: str, frames: int = 40, fps: float = 20.0,
              size=(320, 240)) -> bool:
    """生成一个可被 cv2 解码的测试 mp4；失败返回 False。"""
    try:
        import cv2
    except Exception:
        return False
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not w.isOpened():
        w.release()
        return False
    for i in range(frames):
        fr = np.random.default_rng(i).integers(20, 230, (size[1], size[0], 3)).astype("uint8")
        fr[80:160, 100:220] = 20  # 一块暗区制造边缘
        w.write(fr)
    w.release()
    return os.path.getsize(path) > 1000


class _VideoBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "lib.db")
        self.data_dir = os.path.join(self.tmp, "data")
        self.src = os.path.join(self.tmp, "src")
        os.makedirs(self.src)
        self.mp4 = os.path.join(self.src, "movie.mp4")
        self.have_mp4 = _make_mp4(self.mp4)
        self.db = Database(self.db_path).connect()
        IngestPipeline(self.db, self.data_dir).ingest([self.src], register_roots=False)
        row = self.db.conn.execute(
            "SELECT id FROM photos WHERE file_name='movie.mp4'").fetchone()
        self.vid = row[0] if row else None


class TestVideoWhitelist(unittest.TestCase):
    def test_video_exts_present(self):
        for e in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            self.assertIn(e, scanner.VIDEO_EXTS)
            self.assertIn(e, scanner.ALL_EXTS)

    def test_is_video(self):
        self.assertTrue(extractor.is_video("a.mp4"))
        self.assertTrue(extractor.is_video("A.MOV"))
        self.assertFalse(extractor.is_video("a.jpg"))
        self.assertFalse(extractor.is_video("a.cr2"))


class TestVideoExtract(_VideoBase):
    def test_metadata(self):
        if not self.have_mp4:
            self.skipTest("cv2 无法生成 mp4")
        m = extractor.extract_metadata(self.mp4)
        self.assertEqual(m["media_type"], "video")
        self.assertEqual((m["width"], m["height"]), (320, 240))
        self.assertAlmostEqual(m["duration"], 2.0, places=1)  # 40 帧 / 20fps
        self.assertTrue(m["video_codec"])

    def test_thumbnail(self):
        if not self.have_mp4:
            self.skipTest("cv2 无法生成 mp4")
        out = os.path.join(self.tmp, "vt.jpg")
        size = extractor.make_video_thumbnail(self.mp4, out)
        self.assertIsNotNone(size)
        self.assertTrue(os.path.exists(out) and os.path.getsize(out) > 500)


class TestVideoPipeline(_VideoBase):
    def test_row_fields(self):
        if not self.have_mp4:
            self.skipTest("cv2 无法生成 mp4")
        r = self.db.conn.execute(
            "SELECT media_type, duration, width, height, thumbnail_path,"
            " face_done, ocr_done, status FROM photos WHERE id=?", (self.vid,)
        ).fetchone()
        self.assertEqual(r[0], "video")
        self.assertAlmostEqual(r[1], 2.0, places=1)
        self.assertEqual((r[2], r[3]), (320, 240))
        self.assertTrue(r[4])                 # 有缩略图
        self.assertEqual((r[5], r[6]), (1, 1))  # 视频不做人脸/OCR
        self.assertEqual(r[7], "indexed")

    def test_analysis_selectors_skip_video(self):
        # faces/ocr/clip 的选择查询都带 media_type='photo'，视频不会被选中
        f = self.db.conn.execute(
            "SELECT COUNT(*) FROM photos WHERE face_done=0"
            " AND status='indexed' AND media_type='photo'").fetchone()[0]
        self.assertEqual(f, 0)  # 库里只有视频，无可分析照片


class TestVideoBridge(_VideoBase):
    def test_photos_and_detail_carry_video_fields(self):
        from photo_manager.ui.library_bridge import LibraryBridge

        g = LibraryBridge(self.db.path)
        items = g.photos(0, 10)
        vids = [it for it in items if it.get("mediaType") == "video"]
        self.assertEqual(len(vids), 1)
        self.assertTrue(vids[0].get("duration"))
        d = g.photoDetail(self.vid)
        self.assertEqual(d["mediaType"], "video")
        self.assertTrue(d["duration"])
        self.assertTrue(d["videoCodec"])
        self.assertTrue(d["path"].lower().endswith(".mp4"))


if __name__ == "__main__":
    unittest.main()
