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
"""0.5.52：_finish 消息分色守护测试。

修复背景：自动分析链「重复检测（哈希）」阶段在人脸检测之前，其完成消息
固定含「失败 0」字样，_finish 旧启发式「含失败即红色」把它误标为 error——
用户看到人脸检测前有一个红色弹窗一闪而过（实为 0 失败的成功汇总）。
"""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

import tempfile

from photo_manager.ui.library_bridge import LibraryBridge


class TestFinishKind(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QCoreApplication.instance() is None:
            cls.app = QCoreApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.b = LibraryBridge(os.path.join(self._tmp.name, "t.db"))
        self.kinds = []
        self.b.toast.connect(lambda msg, kind: self.kinds.append((msg, kind)))

    def tearDown(self):
        self.b.close()
        self._tmp.cleanup()

    def _kind(self, msg):
        self.b._finish(msg)
        return self.kinds[-1][1]

    def test_zero_fail_summary_is_success(self):
        """「失败 0」的成功汇总不再误标红（本次修复的核心）。"""
        self.assertEqual(
            self._kind("重复检测完成：计算 237 张，失败 0"), "success")
        self.assertEqual(
            self._kind("语义向量完成：生成 237 张，失败 0 张；场景标签新增 5 个"),
            "success")
        self.assertEqual(
            self._kind("扫描完成：新增 237 张，失败 0 张"), "success")

    def test_real_failures_stay_error(self):
        """真失败仍为红色。"""
        self.assertEqual(self._kind("扫描失败：磁盘错误"), "error")
        self.assertEqual(self._finish_err("移出失败：目标文件夹不可用"), "error")
        self.assertEqual(self._finish_err("自动分析失败：xxx"), "error")
        self.assertEqual(
            self._kind("重复检测完成：计算 237 张，失败 3"), "error")
        self.assertEqual(
            self._kind("语义向量完成：生成 200 张，失败 37 张"), "error")

    def _finish_err(self, msg):
        self.b._finish(msg)
        return self.kinds[-1][1]

    def test_success_and_warning_untouched(self):
        self.assertEqual(self._kind("人脸检测完成：检出 12 张含人脸"), "success")
        self.assertEqual(self._kind("分析已中断：可稍后继续"), "warning")
        self.assertEqual(self._kind("导入已取消：有任务正在运行"), "warning")

    def test_hash_stage_message_without_fail_word(self):
        """措辞改进后：0 失败时哈希阶段消息不再含「失败」字样。"""
        ok, fail = 237, 0
        msg = f"重复检测完成：计算 {ok} 张" + (f"，失败 {fail}" if fail else "")
        self.assertNotIn("失败", msg)
        self.assertEqual(self._kind(msg), "success")
        ok, fail = 230, 7
        msg = f"重复检测完成：计算 {ok} 张" + (f"，失败 {fail}" if fail else "")
        self.assertIn("失败", msg)
        self.assertEqual(self._kind(msg), "error")


if __name__ == "__main__":
    unittest.main()
