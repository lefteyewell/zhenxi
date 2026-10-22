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
"""阶段1 集成测试：生成测试图 → 入库 → 搜索（unittest，无需 GPU/AI 模型）。"""
import io
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

import piexif
from PIL import Image

from photo_manager.core.db import Database
from photo_manager.core.extractor import extract_metadata
from photo_manager.core.pipeline import IngestPipeline
from photo_manager.core.search import PhotoSearch


def make_jpeg(path: Path, dt: str, make: str, model: str, gps=True, banner="测试横幅文字"):
    img = Image.new("RGB", (640, 480), (120, 160, 200))
    zeroth = {
        piexif.ImageIFD.Make: make.encode("utf-8"),
        piexif.ImageIFD.Model: model.encode("utf-8"),
    }
    exif = {
        piexif.ExifIFD.DateTimeOriginal: dt.encode(),
        piexif.ExifIFD.DateTimeDigitized: dt.encode(),
    }
    gps_dict = {}
    if gps:
        gps_dict = {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((39, 1), (54, 1), (30, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"E",
            piexif.GPSIFD.GPSLongitude: ((116, 1), (23, 1), (30, 1)),
        }
    img.save(path, "JPEG", quality=90, exif=piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps_dict}))


class TestIngestSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.photo_dir = root / "photos"
        (self.photo_dir / "canon").mkdir(parents=True)
        make_jpeg(self.photo_dir / "canon" / "IMG_0001.JPG",
                  "2024:05:01 10:00:00", "Canon", "Canon EOS R5")
        make_jpeg(self.photo_dir / "canon" / "IMG_0002.JPG",
                  "2024:05:02 11:00:00", "Canon", "Canon EOS R5", gps=False)
        self.db = Database(root / "library.db").connect()
        self.pipe = IngestPipeline(self.db, root / "data")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _thumb_abs(self, stored: str) -> str:
        """thumbnail_path → 绝对路径。

        0.5.51 起缩略图改存**相对 data 目录**的形式（thumbs/hh/hhh.jpg），
        程序目录可整体移动；历史绝对路径同样支持。
        """
        return stored if os.path.isabs(stored) else str(
            Path(self.tmp.name) / "data" / stored)

    def test_extract_metadata(self):
        meta = extract_metadata(self.photo_dir / "canon" / "IMG_0001.JPG")
        self.assertEqual(meta["taken_at"], "2024-05-01T10:00:00")
        self.assertEqual(meta["camera_model"], "Canon EOS R5")
        self.assertAlmostEqual(meta["gps_lat"], 39.9083333, places=5)
        self.assertEqual((meta["width"], meta["height"]), (640, 480))

    def test_reingest_clears_stale_embeddings(self):
        """回归：图片内容变化重入库后，旧 CLIP 语义向量必须被清除。

        _upsert 若不删 photo_embeddings，clip-index（增量跳过已有向量）将永不
        重算，语义搜索/以图搜图会继续用旧图的向量。
        """
        from photo_manager.core.clip import MODEL_ID

        self.pipe.ingest([str(self.photo_dir)])
        c = self.db.conn
        pid = c.execute(
            "SELECT id FROM photos WHERE file_name='IMG_0001.JPG'").fetchone()[0]
        c.execute(
            "INSERT OR REPLACE INTO photo_embeddings(photo_id, embedding, model)"
            " VALUES (?,?,?)", (pid, b"\x00" * 2048, MODEL_ID))
        c.commit()
        # 覆写文件内容 + 推进 mtime → 重扫判为 changed → 重索引
        p = self.photo_dir / "canon" / "IMG_0001.JPG"
        make_jpeg(p, "2024:05:01 10:00:00", "Canon", "Canon EOS R5")
        os.utime(p, (time.time() + 10, time.time() + 10))
        self.pipe.ingest([str(self.photo_dir)])
        left = c.execute(
            "SELECT COUNT(*) FROM photo_embeddings WHERE photo_id=?",
            (pid,)).fetchone()[0]
        self.assertEqual(left, 0, "重索引后旧语义向量应被清除，待 clip-index 重新生成")

    def test_copy_multi_root_anchor(self):
        """回归：多扫描根 + 复制入库时，锚点必须大小写不敏感地匹配正确的根。

        旧代码仅对 anchor 转小写而 key 未转（Windows 盘符大写），匹配恒为
        False、恒回退第一个根；第二个根的文件拿到错误锚点后 relative_to 抛
        ValueError（relocate_file 只捕 OSError），整次导入崩溃。
        """
        base = Path(self.tmp.name)
        root_a = base / "srcA" / "tripA"
        root_b = base / "srcB" / "tripB"
        root_a.mkdir(parents=True)
        root_b.mkdir(parents=True)
        make_jpeg(root_a / "A01.JPG", "2024:06:01 09:00:00", "Canon", "EOS R5", gps=False)
        make_jpeg(root_b / "B01.JPG", "2024:06:02 09:00:00", "Canon", "EOS R5", gps=False)
        lib = base / "libroot"
        pipe2 = IngestPipeline(self.db, base / "data2")
        pipe2.ingest([str(base / "srcA"), str(base / "srcB")], copy_root=str(lib))
        # relocate_file 目标结构 = <库根>/<锚点目录名>/<相对锚点子路径>
        self.assertTrue((lib / "srcA" / "tripA" / "A01.JPG").is_file(),
                        "srcA 的照片应按锚点 srcA 复制到 lib/srcA/tripA/")
        self.assertTrue((lib / "srcB" / "tripB" / "B01.JPG").is_file(),
                        "srcB 的照片应按锚点 srcB 复制（旧代码锚点恒取第一根，此处会崩或漏复制）")

    def test_ingest_and_incremental(self):
        stats = self.pipe.ingest([self.photo_dir])
        self.assertEqual(stats["indexed"], 2)
        self.assertEqual(stats["failed"], 0)
        stats2 = self.pipe.ingest([self.photo_dir])
        self.assertEqual(stats2["indexed"], 0, "增量续扫不应重复入库")
        row = self.db.conn.execute(
            "SELECT file_name, taken_at, camera_model, gps_lat, thumbnail_path, status"
            " FROM photos ORDER BY id LIMIT 1"
        ).fetchone()
        self.assertEqual(row[0], "IMG_0001.JPG")
        self.assertEqual(row[1], "2024-05-01T10:00:00")
        self.assertEqual(row[2], "Canon EOS R5")
        self.assertIsNotNone(row[3])
        self.assertTrue(os.path.exists(self._thumb_abs(row[4])))
        self.assertEqual(row[5], "indexed")

    def test_search(self):
        self.pipe.ingest([self.photo_dir])
        s = PhotoSearch(self.db)
        hits = s.query("IMG_0001")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["file_name"], "IMG_0001.JPG")
        hits = s.query("canon")
        self.assertEqual(len(hits), 2)
        hits = s.query("R5")
        self.assertEqual(len(hits), 2)
        self.assertEqual(len(s.suggest("IMG")), 2)

    def test_scan_recover_missing_photo(self):
        """reindexCheck 标记 missing 后，文件重新出现时扫描应解除 missing。"""
        from photo_manager.core.scanner import Scanner

        self.pipe.ingest([self.photo_dir])
        target = self.photo_dir / "canon" / "IMG_0001.JPG"
        pid = self.db.conn.execute(
            "SELECT id FROM photos WHERE file_path=?", (str(target).replace("\\", "/"),)
        ).fetchone()[0]
        # 模拟 reindexCheck：文件被系统外删除后标记 missing
        os.remove(target)
        self.db.conn.execute("UPDATE photos SET status='missing' WHERE id=?", (pid,))
        self.db.conn.commit()
        # 文件重新出现（mtime/size 相同也需恢复）
        make_jpeg(target, "2024:05:01 10:00:00", "Canon", "Canon EOS R5")
        os.utime(target, (self.db.conn.execute(
            "SELECT file_mtime FROM photos WHERE id=?", (pid,)).fetchone()[0],) * 2)
        res = Scanner(self.db).scan([self.photo_dir])
        status = self.db.conn.execute(
            "SELECT status FROM photos WHERE id=?", (pid,)).fetchone()[0]
        self.assertEqual(status, "pending", "重新出现的照片应解除 missing 恢复入库")
        # 恢复闭环：pipeline 重索引应把 pending 恢复到 indexed，并重新生成缩略图
        st = self.pipe.ingest([self.photo_dir])
        self.assertEqual(st["indexed"], 1, "恢复的照片应被重索引")
        row = self.db.conn.execute(
            "SELECT status, thumbnail_path, face_done FROM photos WHERE id=?",
            (pid,)).fetchone()
        self.assertEqual(row[0], "indexed")
        self.assertTrue(os.path.exists(self._thumb_abs(row[1])),
                        "恢复后应重新生成缩略图")


if __name__ == "__main__":
    unittest.main()
