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
"""0.5.38：导出格式/分辨率单元测试（直接驱动 _export_processed_worker，同步）。"""
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from photo_manager.ui.library_bridge import LibraryBridge


def _make_jpg(path: Path, w: int, h: int, color=(200, 60, 60)) -> None:
    Image.new("RGB", (w, h), color).save(path, "JPEG", quality=90)


class TestExportProcessed(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.src_dir = Path(self.dir.name) / "src"
        self.out = Path(self.dir.name) / "out"
        self.src_dir.mkdir()
        self.out.mkdir()
        self.bridge = LibraryBridge(str(Path(self.dir.name) / "lib.db"))
        self.db = self.bridge.db
        self.pids = []
        for i, (w, h) in enumerate([(4000, 2000), (800, 600)]):
            f = self.src_dir / f"img{i}.jpg"
            _make_jpg(f, w, h)
            cur = self.db.conn.execute(
                "INSERT INTO photos(file_path, file_name, folder_path, ext,"
                " file_size, file_mtime, status) VALUES (?,?,?,?,?,?,?)",
                (str(f), f.name, str(self.src_dir), ".jpg",
                 f.stat().st_size, f.stat().st_mtime, "indexed"),
            )
            self.pids.append(cur.lastrowid)
        self.db.conn.commit()

    def tearDown(self):
        self.db.conn.close()
        self.bridge.db.conn = None  # 防重复关闭
        self.dir.cleanup()

    def test_resize_short_edge(self):
        """4000x2000 → 短边1080 = 2160x1080；800x600 短边600<1080 不放大。"""
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "jpg", 1080)
        f = self.out / "img0.jpg"
        self.assertTrue(f.exists())
        with Image.open(f) as im:
            self.assertEqual(im.size, (2160, 1080))
        # 第二张不放大
        self.bridge._export_processed_worker([self.pids[1]], str(self.out),
                                             "jpg", 1080)
        with Image.open(self.out / "img1.jpg") as im:
            self.assertEqual(im.size, (800, 600))

    def test_format_convert(self):
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "png", 0)
        self.assertTrue((self.out / "img0.png").exists())
        with Image.open(self.out / "img0.png") as im:
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.size, (4000, 2000))

    def test_original_copy(self):
        """original/original = 直接复制，字节一致。"""
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "original", 0)
        src = Path(self.db.conn.execute(
            "SELECT file_path FROM photos WHERE id=?", (self.pids[0],)
        ).fetchone()[0])
        self.assertEqual((src).read_bytes(), (self.out / "img0.jpg").read_bytes())

    def test_dedupe_name(self):
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "original", 0)
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "original", 0)
        self.assertTrue((self.out / f"img0_{self.pids[0]}.jpg").exists())

    def test_webp_tiff(self):
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "webp", 800)
        self.bridge._export_processed_worker([self.pids[0]], str(self.out),
                                             "tiff", 0)
        self.assertTrue((self.out / "img0.webp").exists())
        self.assertTrue((self.out / "img0.tiff").exists())
        with Image.open(self.out / "img0.webp") as im:
            self.assertEqual(min(im.size), 800)


if __name__ == "__main__":
    unittest.main()
