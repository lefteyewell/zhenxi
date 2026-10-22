# -*- coding: utf-8 -*-
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
"""0.5.46：自动语义索引开关。

守护三点（对应用户要求：默认开 + 菜单/工具显式开关）：
1. 未设置时默认开启；
2. setter 后 getter 在**同一会话内**即刻一致（修 QSettings 跨实例缓存不一致）；
3. 切换时发 clipAutoIndexChanged 信号（供菜单/工具/设置三处联动）。
QSettings 用完即还原，避免污染其它测试/本机设置。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication, QSettings

from photo_manager.ui.library_bridge import LibraryBridge

_APP = QCoreApplication.instance() or QCoreApplication([])


class TestClipAutoIndex(unittest.TestCase):
    def setUp(self):
        self._qs = QSettings("PhotoManager", "PhotoManager")
        self._prev = self._qs.value("clipAutoIndex", None)
        self._qs.remove("clipAutoIndex")
        self._qs.sync()
        self.root = tempfile.mkdtemp(prefix="pm_clipauto_")
        self.b = LibraryBridge(os.path.join(self.root, "lib.db"))

    def tearDown(self):
        if self._prev is None:
            self._qs.remove("clipAutoIndex")
        else:
            self._qs.setValue("clipAutoIndex", self._prev)
        self._qs.sync()

    def test_default_on(self):
        self.assertTrue(self.b.clipAutoIndexEnabled())

    def test_setter_getter_consistent_and_signal(self):
        got = []
        self.b.clipAutoIndexChanged.connect(lambda on: got.append(on))
        self.b.setClipAutoIndexEnabled(False)
        self.assertFalse(self.b.clipAutoIndexEnabled())   # 会话内即刻反映（非过期值）
        self.b.setClipAutoIndexEnabled(True)
        self.assertTrue(self.b.clipAutoIndexEnabled())
        self.assertEqual(got, [False, True])               # 两次切换都发了信号


if __name__ == "__main__":
    unittest.main()
