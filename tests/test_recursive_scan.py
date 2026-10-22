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
"""递归/非递归扫描 + 复制入库（照片库根目录）集成回归测试。

对照实现：
- core/scanner.py: scan(recursive=True/False)
- core/pipeline.py: ingest(recursive=..., copy_root=...)
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.db import Database
from photo_manager.core.pipeline import IngestPipeline
from photo_manager.core.scanner import Scanner


def _mkjpg(path: Path, color="red") -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color).save(path, "JPEG")


class TestRecursiveScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rec_"))
        self.src = self.tmp / "photos"
        _mkjpg(self.src / "top.jpg")
        _mkjpg(self.src / "sub" / "b.jpg")
        (self.src / "sub" / "note.txt").write_text("x", encoding="utf-8")
        (self.src / "readme.md").write_text("x", encoding="utf-8")
        self.db = Database(self.tmp / "lib.db").connect()
        self.pipe = IngestPipeline(self.db, self.tmp / "data")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _paths(self):
        return {
            r[0].replace("\\", "/")
            for r in self.db.conn.execute("SELECT file_path FROM photos").fetchall()
        }

    def test_scan_recursive_true(self):
        res = Scanner(self.db).scan([str(self.src)])
        files = {f.file_path.replace("\\", "/") for f in res.new_files}
        self.assertEqual(files,
                         {f"{self.src.as_posix()}/top.jpg",
                          f"{self.src.as_posix()}/sub/b.jpg"})
        self.assertEqual(res.total_seen, 2)  # txt/md 被白名单过滤

    def test_scan_recursive_false_top_only(self):
        res = Scanner(self.db).scan([str(self.src)], recursive=False)
        files = {f.file_path.replace("\\", "/") for f in res.new_files}
        self.assertEqual(files, {f"{self.src.as_posix()}/top.jpg"})

    def test_ingest_recursive_false(self):
        self.pipe.ingest(str(self.src), recursive=False)
        self.assertEqual(self._paths(), {f"{self.src.as_posix()}/top.jpg"})

    def test_ingest_recursive_true_excludes_non_images(self):
        self.pipe.ingest(str(self.src), recursive=True)
        paths = self._paths()
        self.assertEqual(len(paths), 2)
        self.assertFalse(any(p.endswith(".txt") or p.endswith(".md") for p in paths))


class TestCopyIntoLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="copy_"))
        self.src = self.tmp / "src photos" / "2025旅行"
        _mkjpg(self.src / "海边" / "a.jpg", "red")
        _mkjpg(self.src / "top.jpg", "blue")
        (self.src / "海边" / "note.txt").write_text("x", encoding="utf-8")
        self.lib = self.tmp / "lib"
        self.db = Database(self.tmp / "lib.db").connect()
        self.pipe = IngestPipeline(self.db, self.tmp / "data")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_copy_preserves_structure_and_skips_non_images(self):
        self.pipe.ingest(str(self.src), copy_root=str(self.lib))
        # 库内出现「被导入文件夹名/子路径」结构（文件夹整个复制入库根）
        self.assertTrue((self.lib / "2025旅行" / "海边" / "a.jpg").is_file())
        self.assertTrue((self.lib / "2025旅行" / "top.jpg").is_file())
        # 非照片文件不被复制
        self.assertFalse((self.lib / "2025旅行" / "海边" / "note.txt").exists())
        # DB 登记的是库内路径（保持正斜杠）
        paths = {
            r[0].replace("\\", "/")
            for r in self.db.conn.execute("SELECT file_path FROM photos").fetchall()
        }
        self.assertTrue(all(p.startswith(self.lib.as_posix() + "/") for p in paths))
        self.assertEqual(len(paths), 2)
        # 源文件原样保留
        self.assertTrue((self.src / "海边" / "a.jpg").is_file())
        self.assertTrue((self.src / "海边" / "note.txt").is_file())

    def test_in_place_when_source_inside_library(self):
        # 源本来就在库内 → 就地登记，不复制
        inside_root = self.lib / "already"
        _mkjpg(inside_root / "b.jpg")
        self.pipe.ingest(str(inside_root), copy_root=str(self.lib))
        paths = {
            r[0].replace("\\", "/")
            for r in self.db.conn.execute("SELECT file_path FROM photos").fetchall()
        }
        self.assertEqual(paths, {f"{inside_root.as_posix()}/b.jpg"})
        self.assertFalse((self.lib / "already" / "already" / "b.jpg").exists())

    def test_reingest_idempotent(self):
        self.pipe.ingest(str(self.src), copy_root=str(self.lib))
        stats = self.pipe.ingest(str(self.src), copy_root=str(self.lib))
        # 第二次扫描：源路径已有导入映射（mtime/size 未变）→ 不重复处理
        self.assertEqual(stats.get("indexed", 0), 0)
        n = self.db.conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        self.assertEqual(n, 2)

    def test_no_copy_root_indexes_in_place(self):
        self.pipe.ingest(str(self.src))
        paths = {
            r[0].replace("\\", "/")
            for r in self.db.conn.execute("SELECT file_path FROM photos").fetchall()
        }
        self.assertIn(f"{self.src.as_posix()}/top.jpg", paths)
        self.assertFalse(self.lib.exists())


if __name__ == "__main__":
    unittest.main()
