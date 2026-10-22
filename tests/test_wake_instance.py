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
"""0.5.51：单实例唤醒（第二实例发 show → 首实例显示窗口，不再静默退出）。

0.5.53 修复测试：唤醒通道名原本用全局常量 _WAKE_SERVER——若**用户正在
运行 PhotoManager**，测试会连上真程序的监听（test_no_server_returns_false
误返回 True），且测试自己的 listen 抢不到名字。现每个测试用随机独立
通道名（monkeypatch 模块常量），与运行中的真程序互不干扰。
"""
import time
import unittest
import uuid

from PySide6.QtCore import QCoreApplication


class TestWakeInstance(unittest.TestCase):
    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        from photo_manager import main as pm

        self.pm = pm
        # 随机通道名：避免与正在运行的真程序（PhotoManager-Wake）冲突
        self._orig_name = pm._WAKE_SERVER
        pm._WAKE_SERVER = "PM-Wake-Test-" + uuid.uuid4().hex[:12]

    def tearDown(self):
        self.pm.QLocalServer.removeServer(self.pm._WAKE_SERVER)
        self.pm._WAKE_SERVER = self._orig_name

    def test_wake_roundtrip(self):
        """监听中 → _wake_existing_instance 环回发送 show → 回调被调用。"""
        called = []
        server = self.pm._listen_for_wake(lambda: called.append(1))
        self.assertIsNotNone(server, "listen 失败（通道名冲突？）")
        try:
            self.assertTrue(self.pm._wake_existing_instance())
            deadline = time.time() + 2
            while not called and time.time() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertEqual(called, [1], "唤醒回调未被调用")
        finally:
            server.close()

    def test_no_server_returns_false(self):
        """无实例在跑时连接失败 → False（调用方按首实例继续）。"""
        self.pm.QLocalServer.removeServer(self.pm._WAKE_SERVER)
        self.assertFalse(self.pm._wake_existing_instance())


if __name__ == "__main__":
    unittest.main()
