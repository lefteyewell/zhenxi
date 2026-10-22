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
import theme 1.0

/* 通用按钮：主色渐变 + 悬停反馈。
   0.5.38：内置 tooltip 属性——鼠标悬停显示功能说明气泡（空串则不显示） */
Button {
    id: root

    property bool emphasized: false
    property string tooltip: ""

    implicitHeight: 36
    implicitWidth: Math.max(96, implicitContentWidth + leftPadding + rightPadding)

    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.delay: 550
    ToolTip.timeout: 4000
    ToolTip.text: tooltip

    contentItem: Text {
        text: root.text
        font.family: Theme.fontFamily
        font.pixelSize: 14
        font.weight: Font.Medium
        color: root.enabled ? (root.emphasized ? Theme.textOnPrimary : Theme.text) : Theme.textDim
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.radiusSmall
        color: {
            if (!root.enabled) return Theme.surfaceAlt
            if (root.pressed) return Theme.primaryDark
            if (root.emphasized) return root.hovered ? Theme.primaryDark : Theme.primary
            return root.hovered ? Theme.hover : Theme.surface
        }
        border.width: root.emphasized ? 0 : 1
        border.color: Theme.divider
    }
}
