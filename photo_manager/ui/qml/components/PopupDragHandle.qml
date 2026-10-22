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

/* 可拖动标题把手：按住弹窗标题区可把 Popup 移到任意位置，避免遮挡图片浏览区。
   用法：放进弹窗头部 RowLayout 作为首个子元素（铺满头部宽度、位于标题/按钮之下层）：
         PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: <头部高度> }
   注意：不能用 Layout.fillHeight，否则外层 ColumnLayout 会把多余高度全部分给头部。 */
Item {
    id: root

    property var target: null
    property bool active: target !== null

    property real _gx: 0
    property real _gy: 0
    property real _ox: 0
    property real _oy: 0

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.SizeAllCursor
        onPressed: (mouse) => {
            if (!root.active || isNaN(mouse.globalX) || isNaN(mouse.globalY)) return
            root._gx = mouse.globalX
            root._gy = mouse.globalY
            root._ox = root.target.x
            root._oy = root.target.y
        }
        onPositionChanged: (mouse) => {
            if (!root.active || !pressed) return
            if (isNaN(mouse.globalX) || isNaN(mouse.globalY)) return
            root.target.x = root._ox + (mouse.globalX - root._gx)
            root.target.y = root._oy + (mouse.globalY - root._gy)
        }
    }
}
