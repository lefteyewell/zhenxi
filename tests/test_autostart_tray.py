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
"""0.5.48：开机自启条目写入/移除 + 托盘/自启开关（默认值、单一真值、信号、失败回滚）。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QSettings


class TestAutostartEntries(unittest.TestCase):
    """_autostart_apply 系统条目读写（测试后可恢复，不遗留自启项）。"""

    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()

    def test_linux_desktop_write_and_remove(self):
        """Linux/麒麟分支：写 XDG autostart .desktop，取消即删（HOME 重定向）。"""
        from photo_manager.ui import library_bridge as lb

        home = Path(self.tmp) / "home"
        (home / ".config").mkdir(parents=True)
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(Path, "home", classmethod(lambda cls: home)):
            self.assertTrue(lb._autostart_apply(True))
            p = home / ".config" / "autostart" / "PhotoManager.desktop"
            self.assertTrue(p.exists())
            text = p.read_text(encoding="utf-8")
            self.assertIn("[Desktop Entry]", text)
            self.assertIn("Type=Application", text)
            self.assertIn("Exec=", text)
            self.assertIn("X-GNOME-Autostart-enabled=true", text)
            self.assertTrue(lb._autostart_apply(False))
            self.assertFalse(p.exists())

    @unittest.skipUnless(sys.platform.startswith("win"), "Windows only")
    def test_windows_registry_roundtrip(self):
        """Windows 分支：HKCU Run 写入/删除，并还原测试前的原值。"""
        import winreg

        from photo_manager.ui import library_bridge as lb

        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        prev = None
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                               winreg.KEY_QUERY_VALUE)
            try:
                prev = winreg.QueryValueEx(k, "PhotoManager")[0]
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(k)
        except OSError:
            self.skipTest("无法打开 Run 键")
        try:
            self.assertTrue(lb._autostart_apply(True))
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                               winreg.KEY_QUERY_VALUE)
            try:
                v = winreg.QueryValueEx(k, "PhotoManager")[0]
            finally:
                winreg.CloseKey(k)
            # 开发模式 applicationFilePath() 是 python.exe，冻结后是 PhotoManager.exe；
            # 两者都应以引号包裹、以 .exe 结尾
            self.assertTrue(v.startswith('"') and v.endswith('.exe"'),
                            f"自启值异常: {v!r}")
            self.assertTrue(lb._autostart_apply(False))
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                               winreg.KEY_QUERY_VALUE)
            try:
                with self.assertRaises(FileNotFoundError):
                    winreg.QueryValueEx(k, "PhotoManager")
            finally:
                winreg.CloseKey(k)
        finally:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                               winreg.KEY_SET_VALUE)
            try:
                if prev is None:
                    try:
                        winreg.DeleteValue(k, "PhotoManager")
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(k, "PhotoManager", 0, winreg.REG_SZ, prev)
            finally:
                winreg.CloseKey(k)


class TestTrayAndAutoStartBridge(unittest.TestCase):
    """bridge 槽：托盘默认开 / 自启默认关；setter 单值真值 + 信号（不碰真实系统）。"""

    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.tmp = tempfile.mkdtemp()
        self.s = QSettings("PhotoManager", "PhotoManager")
        self.prev = {k: self.s.value(k, None)
                     for k in ("trayEnabled", "autoStart")}
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

    def test_defaults(self):
        self.assertTrue(self.bridge.trayEnabled())       # 托盘默认开
        self.assertFalse(self.bridge.autoStartEnabled())  # 自启默认关

    def test_tray_setter_signal_and_truth(self):
        got = []
        self.bridge.trayEnabledChanged.connect(got.append)
        self.bridge.setTrayEnabled(False)
        self.assertFalse(self.bridge.trayEnabled())
        self.assertEqual(got, [False])
        self.bridge.setTrayEnabled(True)
        self.assertTrue(self.bridge.trayEnabled())
        self.assertEqual(got, [False, True])

    def test_autostart_setter_mocked(self):
        got = []
        self.bridge.autoStartChanged.connect(got.append)
        with mock.patch("photo_manager.ui.library_bridge._autostart_apply",
                        return_value=True) as m:
            self.bridge.setAutoStartEnabled(True)
            m.assert_called_once_with(True)
        self.assertTrue(self.bridge.autoStartEnabled())
        self.assertEqual(got, [True])

    def test_autostart_setter_failure_reverts(self):
        got = []
        self.bridge.autoStartChanged.connect(got.append)
        with mock.patch("photo_manager.ui.library_bridge._autostart_apply",
                        return_value=False):
            self.bridge.setAutoStartEnabled(True)
        # 写系统失败 → 真值保持 False，信号回填 False（设置勾选自动回滚）
        self.assertFalse(self.bridge.autoStartEnabled())
        self.assertEqual(got, [False])


if __name__ == "__main__":
    unittest.main()
