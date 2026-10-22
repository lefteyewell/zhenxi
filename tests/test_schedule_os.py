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
"""0.5.51 路线 B：OS 级定时调度（引擎切换 + Windows XML + 开发模式守卫）。"""
import os
import sys
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QSettings


class TestScheduleOsEngine(unittest.TestCase):
    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.s = QSettings("PhotoManager", "PhotoManager")
        self.prev = {k: self.s.value(k, None) for k in
                     ("schedule/engine", "schedule/mode", "schedule/folderCheck",
                      "schedule/analyze", "schedule/onceAt", "schedule/time")}
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

    def test_default_engine_internal(self):
        self.assertEqual(self.bridge.scheduleEngine(), "internal")

    def test_switch_internal_ok(self):
        self.bridge.setScheduleEngine("os")  # 开发模式会失败，保持 internal
        r = self.bridge.setScheduleEngine("internal")
        self.assertIn("程序内计时", r)
        self.assertEqual(self.bridge.scheduleEngine(), "internal")

    def test_dev_mode_guard_blocks_os(self):
        """开发模式（未冻结）不允许注册系统任务——返回原因且不改设置。"""
        self.bridge.setScheduleCheckEnabled(True)
        self.bridge.setScheduleMode("daily")
        r = self.bridge.setScheduleEngine("os")
        self.assertIn("打包版", r)
        self.assertEqual(self.bridge.scheduleEngine(), "internal")

    def test_os_requires_task_and_mode(self):
        """未勾选执行项/未选模式时拒绝注册（即便冻结也先挡）。"""
        self.bridge.setScheduleCheckEnabled(False)
        self.bridge.setScheduleMode("daily")
        self.assertIn("执行项", self.bridge.setScheduleEngine("os"))
        self.bridge.setScheduleCheckEnabled(True)
        self.bridge.setScheduleMode("off")
        self.assertIn("执行方式", self.bridge.setScheduleEngine("os"))

    def test_windows_xml_contents(self):
        """Windows 任务 XML：关机不错过 + 每日触发器 + 无头参数 + exe 引用。"""
        from photo_manager.ui.library_bridge import LibraryBridge as LB

        trig = ('<CalendarTrigger><StartBoundary>2026-01-01T09:00:00'
                '</StartBoundary><Enabled>true</Enabled>'
                '<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>'
                '</CalendarTrigger>')
        xml = LB._windows_task_xml("D:/PhotoManager/PhotoManager.exe", trig)
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>", xml)
        self.assertIn("DaysInterval", xml)
        self.assertIn("--scheduled-run", xml)
        self.assertIn("D:/PhotoManager/PhotoManager.exe", xml)
        self.assertIn("UTF-16", xml)

    def test_schedule_os_registered_no_crash(self):
        """查询注册状态不崩（开发机可能无任务 → False）。"""
        self.assertIsInstance(self.bridge.scheduleOsRegistered(), bool)


if __name__ == "__main__":
    unittest.main()
