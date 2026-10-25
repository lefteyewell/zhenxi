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

/* 可拖动标题把手：按住弹窗头部任意位置（含标题文字、空隙）可把 Popup 移到任意位置。
   用法：放进弹窗头部 RowLayout 作为首个子元素：
         PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: <头部高度> }
   注意：不能用 Layout.fillHeight，否则外层 ColumnLayout 会把多余高度全部分给头部。

   ★ 核心坑位（Qt 6.11 实测，qmltypes 铁证）：
   QML MouseEvent 只有 x/y/button/buttons/modifiers/source/accepted 等，
   【没有 globalX/globalY/globalPosition】——访问即 undefined！
   · 0.5.x 原版用 isNaN(mouse.globalX) 守卫 → undefined 被拦 → 每次拖动
     静默放弃 → 用户看到的"所有弹窗都拖不动"。
   · 0.6.3 重写时删掉守卫 → target.x = _ox + (undefined-undefined) = NaN
     → 弹窗瞬移到不可渲染坐标：视觉消失但 opened 仍为 true（open() 变
     空操作、状态栏卡在打开前文案）→ 用户看到的"按下即消失且永不再弹"。
   正解：用 mapToItem(null) 取窗口场景坐标（任何 Qt 6 版本都存在），
   增量拖动，并对结果做 isFinite 双保险。

   0.6.4：命中区横向扩展覆盖整个头部（按 target.contentItem 宽度夹紧，
   不越出弹窗边界——越界的按下会被 CloseOnPressOutside 判为点击外部
   直接关弹窗）。标题 Text 不拦截鼠标，事件落到本区即可拖动；按钮是
   更晚绘制的兄弟控件，优先接收自己的点击。判定用 mouse.buttons，
   preventStealing 防被滚动容器抢占。 */
Item {
    id: root

    property var target: null
    property bool active: target !== null

    property real _gx: 0
    property real _gy: 0
    property real _ox: 0
    property real _oy: 0

    MouseArea {
        id: ma
        anchors.verticalCenter: parent.verticalCenter
        height: Math.max(parent.height, 44)
        cursorShape: Qt.SizeAllCursor
        preventStealing: true
        /* 命中区横向范围 = 弹窗内容区内、把手上/下方一行：左缘贴内容区
           左边，右缘贴内容区右边，永不出界（越界按下会被
           CloseOnPressOutside 判定为点击外部而关掉弹窗）。 */
        x: {
            if (!root.target || !root.target.contentItem)
                return 0
            var p = root.mapToItem(root.target.contentItem, 0, 0)
            return -Math.max(0, p.x)
        }
        width: {
            if (!root.target || !root.target.contentItem)
                return parent.width
            var p = root.mapToItem(root.target.contentItem, 0, 0)
            return Math.max(parent.width,
                            root.target.contentItem.width - p.x)
        }
        onPressed: (mouse) => {
            if (!root.active || !(mouse.buttons & Qt.LeftButton)) return
            var p = ma.mapToItem(null, mouse.x, mouse.y)
            if (!isFinite(p.x) || !isFinite(p.y)) return
            root._gx = p.x
            root._gy = p.y
            root._ox = root.target.x
            root._oy = root.target.y
        }
        onPositionChanged: (mouse) => {
            if (!root.active || !(mouse.buttons & Qt.LeftButton)) return
            var p = ma.mapToItem(null, mouse.x, mouse.y)
            var nx = root._ox + (p.x - root._gx)
            var ny = root._oy + (p.y - root._gy)
            /* 双保险：坐标异常（undefined/NaN）时放弃本次移动，
               绝不把弹窗打到不可渲染位置 */
            if (!isFinite(nx) || !isFinite(ny)) return
            root.target.x = nx
            root.target.y = ny
        }
    }
}
