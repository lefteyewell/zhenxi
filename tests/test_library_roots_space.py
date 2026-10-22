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
"""0.5.49：多根目录空间挑选 + 自动语义索引触发/挂起（修复“开了不出向量”）。"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QSettings

GB = 1024 ** 3


def _fake_usage(free_bytes):
    class _Du:
        total = 500 * GB

        def __init__(self):
            self.free = free_bytes

    return _Du()


class TestPickCopyRoot(unittest.TestCase):
    """pick_copy_root：空间足够优先、全不够选最大、空列表 None。"""

    def test_picks_root_with_enough_space(self):
        from photo_manager.core.library import pick_copy_root

        with mock.patch("photo_manager.core.library.shutil.disk_usage",
                        side_effect=[_fake_usage(100 * 1024 * 1024),  # 不足预留
                                     _fake_usage(50 * GB)]):
            got = pick_copy_root(10 * 1024 * 1024, ["/mnt/full", "/mnt/roomy"])
        self.assertEqual(got, "/mnt/roomy")

    def test_all_tight_picks_max_free(self):
        from photo_manager.core.library import pick_copy_root

        # 文件 5GB，两个根分别只剩 2G/3G，都不足 → 选剩余最大的
        with mock.patch("photo_manager.core.library.shutil.disk_usage",
                        side_effect=[_fake_usage(2 * GB), _fake_usage(3 * GB)]):
            got = pick_copy_root(5 * GB, ["/a", "/b"])
        self.assertEqual(got, "/b")

    def test_empty_roots_returns_none(self):
        from photo_manager.core.library import pick_copy_root

        self.assertIsNone(pick_copy_root(1024, []))
        self.assertIsNone(pick_copy_root(1024, None))

    def test_skips_unprobeable_root(self):
        from photo_manager.core.library import pick_copy_root

        def boom(path):
            if str(path).startswith("/bad"):
                raise OSError("no such")
            return _fake_usage(99 * GB)

        with mock.patch("photo_manager.core.library.shutil.disk_usage",
                        side_effect=boom):
            got = pick_copy_root(1024, ["/bad/x", "/good"])
        self.assertEqual(got, "/good")


class TestRelocateMultiRoot(unittest.TestCase):
    """relocate_file：多根时落到有空间的根并保持相对结构；单根 str 向后兼容。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src_dir = self.tmp / "src" / "2025旅行"
        (self.src_dir / "海边").mkdir(parents=True)
        self.src = self.src_dir / "海边" / "a.jpg"
        self.src.write_bytes(b"x" * 2048)
        self.root_a = self.tmp / "libA"   # 将模拟为“满”
        self.root_b = self.tmp / "libB"   # 将模拟为“有空”
        self.root_a.mkdir()
        self.root_b.mkdir()

    def test_lands_in_roomy_root(self):
        from photo_manager.core.library import relocate_file

        with mock.patch("photo_manager.core.library.shutil.disk_usage",
                        side_effect=[_fake_usage(100 * 1024 * 1024),  # libA 不足预留
                                     _fake_usage(50 * GB)]):          # libB 有空
            final = relocate_file(str(self.src), str(self.src_dir),
                                  [str(self.root_a), str(self.root_b)])
        self.assertTrue(final.replace("\\", "/").startswith(str(self.root_b).replace("\\", "/")))
        self.assertTrue(final.replace("\\", "/").endswith("libB/2025旅行/海边/a.jpg"))
        self.assertTrue(Path(final).is_file())

    def test_single_str_root_backward_compat(self):
        from photo_manager.core.library import relocate_file

        with mock.patch("photo_manager.core.library.shutil.disk_usage",
                        return_value=_fake_usage(50 * GB)):
            final = relocate_file(str(self.src), str(self.src_dir),
                                  str(self.root_b))
        self.assertTrue(final.replace("\\", "/").startswith(str(self.root_b).replace("\\", "/")))
        self.assertTrue(final.replace("\\", "/").endswith("2025旅行/海边/a.jpg"))


class TestBridgeRootsAndClipTrigger(unittest.TestCase):
    """bridge：_copy_roots_for 三态 + 自动索引开启即触发 + 繁忙挂起。"""

    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.s = QSettings("PhotoManager", "PhotoManager")
        self.prev = {k: self.s.value(k, None)
                     for k in ("libraryRoots", "copyToLibrary", "clipAutoIndex")}
        for k in self.prev:
            self.s.remove(k)
        self.s.sync()
        from photo_manager.ui.library_bridge import LibraryBridge

        self.bridge = LibraryBridge(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        try:
            self.bridge.close()
        except Exception:
            pass
        for k, v in self.prev.items():
            if v is None:
                self.s.remove(k)
            else:
                self.s.setValue(k, v)
        self.s.sync()

    def test_copy_roots_for_three_states(self):
        self.bridge.setLibraryRoots("D:/LibA\nE:/LibB")
        self.bridge.setCopyToLibraryEnabled(False)
        self.assertEqual(self.bridge._copy_roots_for("D:/Other/x"), [])
        self.bridge.setCopyToLibraryEnabled(True)
        # anchor 已在某一根下 → 就地登记
        self.assertEqual(self.bridge._copy_roots_for("D:/LibA/sub"), [])
        # 库外 → 返回全部根（pipeline 逐张按空间挑选）
        self.assertEqual(self.bridge._copy_roots_for("D:/Other/x"),
                         ["D:/LibA", "E:/LibB"])
        # 无根 → 空
        self.bridge.setLibraryRoots("")
        self.assertEqual(self.bridge._copy_roots_for("D:/Other/x"), [])

    def test_library_roots_info_shape(self):
        self.bridge.setLibraryRoots("D:/LibA\nE:/NotExist")
        infos = self.bridge.libraryRootsInfo()
        self.assertEqual(len(infos), 2)
        self.assertTrue(infos[0]["primary"])
        self.assertFalse(infos[1]["primary"])
        self.assertIn("freeGB", infos[0])
        self.assertIn("path", infos[0])

    def _seed_photo(self):
        """插一张已索引照片（无向量）→ _clip_pending_count() > 0。"""
        self.bridge.db.conn.execute(
            "INSERT INTO photos(file_path, file_name, folder_path, ext, file_size,"
            " file_mtime, status, media_type) VALUES(?,?,?,?,?,?,?,?)",
            ("/x/a.jpg", "a.jpg", "/x", ".jpg", 10, 1.0, "indexed", "photo"))
        self.bridge.db.conn.commit()

    def test_enabling_setting_kicks_clip(self):
        """开启自动索引 → 立即触发一次 runClip（存量照片补向量）。"""
        called = threading.Event()

        def fake_run_clip():
            called.set()
            return ""

        self._seed_photo()
        with mock.patch.object(self.bridge, "clipAvailable", return_value=True), \
                mock.patch.object(self.bridge, "runClip", fake_run_clip):
            self.bridge.setClipAutoIndexEnabled(True)
            self.assertTrue(called.wait(3), "开启开关后未触发 runClip")

    def test_busy_defers_clip(self):
        """分析链占用 _busy 时挂起 _clip_pending，不抢互斥（0.5.49 核心修复）。"""
        from photo_manager.ui.library_bridge import LibraryBridge

        calls = []

        def fake_run_clip():
            calls.append(1)
            return ""

        self._seed_photo()
        with mock.patch.object(self.bridge, "clipAvailable", return_value=True), \
                mock.patch.object(self.bridge, "runClip", fake_run_clip), \
                mock.patch.object(LibraryBridge, "clipAutoIndexEnabled",
                                  lambda self: True):
            with self.bridge._busy_lock:
                self.bridge._busy = 1  # 模拟分析链正在跑
            self.bridge._maybe_auto_clip()
            time.sleep(0.2)
            self.assertEqual(calls, [], "繁忙时不应直接起 clip 线程")
            self.assertTrue(self.bridge._clip_pending)
            # 链结束释放互斥后接续
            with self.bridge._busy_lock:
                self.bridge._busy = 0
            self.bridge._maybe_auto_clip()
            time.sleep(0.3)
            self.assertEqual(calls, [1])
            self.assertFalse(self.bridge._clip_pending)

    def test_manual_task_drains_pending(self):
        """0.5.50 审计补强：手动任务（_spawn）结束也必须接续挂起的 clip。

        此前只有自动分析链的 finally 接续——启动补跑/开启开关撞上用户手点
        人脸/备份等任务时，_clip_pending 永无接续者，向量再次静默丢失。
        """
        called = threading.Event()

        def fake_run_clip():
            called.set()
            return ""

        self._seed_photo()
        self.bridge._clip_auto = True
        self.bridge._clip_pending = True  # 模拟挂起中
        with mock.patch.object(self.bridge, "clipAvailable", return_value=True), \
                mock.patch.object(self.bridge, "runClip", fake_run_clip):
            self.bridge._spawn("events", "事件聚类", lambda: {"events": 0})
            self.assertTrue(called.wait(5), "手动任务结束后未接续 clip")
            self.assertFalse(self.bridge._clip_pending)

    def test_drain_skipped_when_still_busy(self):
        """互斥仍被占用时不得接续（留给下一个释放者，防止双起 clip）。"""
        self._seed_photo()
        self.bridge._clip_auto = True
        self.bridge._clip_pending = True
        with mock.patch.object(self.bridge, "clipAvailable", return_value=True), \
                mock.patch.object(self.bridge, "runClip", lambda: ""):
            with self.bridge._busy_lock:
                self.bridge._busy = 1
            self.bridge._drain_clip_pending()
            self.assertTrue(self.bridge._clip_pending, "繁忙时不应消费挂起标志")


if __name__ == "__main__":
    unittest.main()
