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
from PySide6.QtCore import QObject, QSettings, Property, Signal, Slot


class ThemeController(QObject):
    """管理配色方案与深/浅模式，状态持久化到 QSettings。"""

    darkChanged = Signal(bool)
    schemeIndexChanged = Signal(int)

    SCHEME_NAMES = [
        "海洋蓝", "森林绿", "落日橙", "玫瑰粉",
        "紫罗兰", "石墨灰", "星空紫", "翡翠绿",
        "影棚深灰",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings()
        self._dark = self._settings.value("ui/dark", True, type=bool)
        self._scheme_index = int(self._settings.value("ui/schemeIndex", 0))

    @Property(bool, notify=darkChanged)
    def dark(self):
        return self._dark

    @dark.setter
    def dark(self, value):
        value = bool(value)
        if value != self._dark:
            self._dark = value
            self._settings.setValue("ui/dark", value)
            self.darkChanged.emit(value)

    @Slot()
    def toggleDark(self):
        self.dark = not self._dark

    @Property(int, notify=schemeIndexChanged)
    def schemeIndex(self):
        return self._scheme_index

    @schemeIndex.setter
    def schemeIndex(self, value):
        value = int(value)
        if value != self._scheme_index:
            self._scheme_index = value
            self._settings.setValue("ui/schemeIndex", value)
            self.schemeIndexChanged.emit(value)

    @Slot(int)
    def setScheme(self, index):
        self.schemeIndex = index

    @Property(list, constant=True)
    def schemeNames(self):
        return self.SCHEME_NAMES

    navWidthChanged = Signal()
    infoWidthChanged = Signal()

    def _nav_width(self):
        return float(self._settings.value("ui/navWidth", 216))

    def _set_nav_width(self, value):
        value = max(140.0, min(420.0, float(value)))
        if abs(value - self._nav_width()) > 0.5:
            self._settings.setValue("ui/navWidth", value)
            self.navWidthChanged.emit()

    def _info_width(self):
        return float(self._settings.value("ui/infoWidth", 288))

    def _set_info_width(self, value):
        value = max(220.0, min(540.0, float(value)))
        if abs(value - self._info_width()) > 0.5:
            self._settings.setValue("ui/infoWidth", value)
            self.infoWidthChanged.emit()

    navWidth = Property(float, _nav_width, _set_nav_width, notify=navWidthChanged)
    infoWidth = Property(float, _info_width, _set_info_width, notify=infoWidthChanged)

    # 缩略图网格单元格尺寸（ACDsee 风格的缩略图大小调节，持久化到 QSettings）
    thumbSizeChanged = Signal()

    def _thumb_size(self) -> int:
        return int(self._settings.value("ui/thumbSize", 160))

    def _set_thumb_size(self, value) -> None:
        v = max(110, min(340, int(value)))
        if v != self._thumb_size():
            self._settings.setValue("ui/thumbSize", v)
            self.thumbSizeChanged.emit()

    thumbSize = Property(int, _thumb_size, _set_thumb_size, notify=thumbSizeChanged)
