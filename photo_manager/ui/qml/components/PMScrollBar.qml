/* PhotoManager - 照片管理系统
 * Copyright (C) 2026 蒙汗药
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
import QtQuick
import QtQuick.Controls

/* 统一滚动条视觉宽度（0.5.41）。
   历史问题：各处显式写 width:6 / width:8 / height:6，部分滚动条太细几乎看不见。
   本组件统一厚度 12px：
   - 竖向滚动条的厚度是 width，横向滚动条的厚度是 height；
   - 只设置「厚度」维度，长度维度由 flickable 自动决定，绝不破坏布局。
   用法：
       ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
       ScrollBar.horizontal: PMScrollBar { policy: ScrollBar.AlwaysOn } */
ScrollBar {
    id: bar

    Binding {
        target: bar
        property: bar.orientation === Qt.Horizontal ? "height" : "width"
        value: 12
    }
}
