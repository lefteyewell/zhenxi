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
"""照片库根目录（复制入库）与定时任务判定回归测试。

对照实现：
- core/library.py: under_any / relocate_file / schedule_due
- core/pipeline.py: ingest(copy_root=...) 复制入库集成（见 test_recursive_scan.py）
"""
import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_manager.core.library import _norm, schedule_due, under_any


def _mkjpg(path: Path, color="red", size=8) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (size, size), color).save(path, "JPEG")


class TestUnderAny(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lib_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_under_and_outside(self):
        root = self.tmp / "lib"
        inside = root / "sub" / "a.jpg"
        outside = self.tmp / "other" / "b.jpg"
        self.assertTrue(under_any(inside, [str(root)]))
        self.assertTrue(under_any(root, [str(root)]))  # 等于根自身也算在内
        self.assertFalse(under_any(outside, [str(root)]))

    def test_case_and_slash_insensitive(self):
        root = self.tmp / "Lib"
        inside = str(self.tmp / "LIB" / "SUB" / "a.jpg").replace("/", "\\")
        self.assertTrue(under_any(inside, [str(root)]))


class TestRelocateFile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="reloc_"))
        self.lib = self.tmp / "lib"
        self.src_dir = self.tmp / "src photos" / "2025旅行"
        _mkjpg(self.src_dir / "海边" / "a.jpg")
        (self.src_dir / "海边" / "note.txt").write_text("x", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_copies_preserving_structure(self):
        from photo_manager.core.library import relocate_file

        src = self.src_dir / "海边" / "a.jpg"
        final = relocate_file(str(src), str(self.src_dir), str(self.lib))
        expected = self.lib / "2025旅行" / "海边" / "a.jpg"
        self.assertEqual(Path(final).resolve(), expected.resolve())
        self.assertTrue(expected.is_file())
        # 源文件保持原样
        self.assertTrue(src.is_file())

    def test_idempotent_same_size(self):
        from photo_manager.core.library import relocate_file

        src = self.src_dir / "海边" / "a.jpg"
        first = relocate_file(str(src), str(self.src_dir), str(self.lib))
        second = relocate_file(str(src), str(self.src_dir), str(self.lib))
        self.assertEqual(Path(first).resolve(), Path(second).resolve())

    def test_collision_gets_unique_name(self):
        from photo_manager.core.library import relocate_file

        # 两个不同父目录下的同名文件夹 → 目标路径相同 → 第二个加 _1 后缀
        #（用不同尺寸确保两文件大小不同，避开"同大小视为已复制"的幂等分支）
        src_a = self.tmp / "one" / "2025旅行" / "海边" / "a.jpg"
        src_b = self.tmp / "two" / "2025旅行" / "海边" / "a.jpg"
        _mkjpg(src_a, "red", size=8)
        _mkjpg(src_b, "blue", size=32)
        first = Path(relocate_file(str(src_a), str(src_a.parent.parent), str(self.lib)))
        second = Path(relocate_file(str(src_b), str(src_b.parent.parent), str(self.lib)))
        self.assertEqual(first.name, "a.jpg")
        self.assertEqual(second.name, "a_1.jpg")
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file() and second.is_file())

    def test_already_in_library_stays(self):
        from photo_manager.core.library import relocate_file

        inside = self.lib / "x" / "a.jpg"
        _mkjpg(inside)
        final = relocate_file(str(inside), str(self.tmp), str(self.lib))
        self.assertEqual(Path(final).resolve(), inside.resolve())

    def test_copy_failure_falls_back_to_src(self):
        # dest_root 指向一个文件的路径 → mkdir 失败 → 回退就地登记
        from photo_manager.core.library import relocate_file

        blocker = self.tmp / "blocker"
        blocker.write_text("not a dir", encoding="utf-8")
        src = self.src_dir / "海边" / "a.jpg"
        final = relocate_file(str(src), str(self.src_dir), str(blocker))
        self.assertEqual(Path(final).resolve(), src.resolve())

    def test_wrong_anchor_falls_back_to_src(self):
        """回归：anchor 与 src 不在同一路径树下（多扫描根锚点回退选错根）时，
        relative_to 抛 ValueError，必须回退就地登记而非让整次导入崩溃。"""
        from photo_manager.core.library import relocate_file

        other = self.tmp / "elsewhere" / "2025旅行"
        _mkjpg(other / "a.jpg")
        final = relocate_file(str(other / "a.jpg"), str(self.src_dir), str(self.lib))
        self.assertEqual(Path(final).resolve(), (other / "a.jpg").resolve())
        self.assertFalse((self.lib / "2025旅行").exists(), "不应误复制到错误位置")


class TestScheduleDue(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 10, 5, 9, 30)

    def test_daily_due_when_past_time(self):
        self.assertTrue(schedule_due("daily", "09:00", "2026-10-04", "", self.now))

    def test_daily_not_due_same_day(self):
        self.assertFalse(schedule_due("daily", "09:00", "2026-10-05", "", self.now))

    def test_daily_not_due_before_time(self):
        now = datetime.datetime(2026, 10, 5, 8, 59)
        self.assertFalse(schedule_due("daily", "09:00", "2026-10-04", "", now))

    def test_daily_invalid_time(self):
        self.assertFalse(schedule_due("daily", "25:00", "2026-10-04", "", self.now))
        self.assertFalse(schedule_due("daily", "abc", "2026-10-04", "", self.now))

    def test_once_due_and_not_before(self):
        self.assertTrue(schedule_due(
            "once", "", "", "2026-10-05 09:00", self.now))
        now = datetime.datetime(2026, 10, 5, 8, 0)
        self.assertFalse(schedule_due("once", "", "", "2026-10-05 09:00", now))

    def test_once_invalid(self):
        self.assertFalse(schedule_due("once", "", "", "not-a-date", self.now))

    def test_off_mode(self):
        self.assertFalse(schedule_due("off", "09:00", "", "", self.now))


if __name__ == "__main__":
    unittest.main()
