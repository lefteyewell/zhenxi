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
import QtQuick.Layouts
import theme 1.0

/* 左侧导航项 */
Item {
    id: root

    property string label: ""
    property bool active: false
    property string badge: ""

    signal clicked()

    implicitHeight: 40
    implicitWidth: 200
    Layout.fillWidth: true
    Layout.preferredWidth: 200

    Rectangle {
        id: indicator
        width: 4
        height: 20
        radius: 2
        anchors.left: parent.left
        anchors.leftMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        color: root.active ? Theme.primary : "transparent"
    }

    Rectangle {
        id: bg
        anchors.fill: parent
        anchors.leftMargin: 6
        anchors.rightMargin: 6
        radius: Theme.radiusMedium
        color: root.active ? Theme.primary : (root.hovered ? Theme.hover : "transparent")
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Text {
        id: labelText
        anchors.left: parent.left
        anchors.leftMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        font.family: Theme.fontFamily
        font.pixelSize: 14
        font.weight: root.active ? Font.DemiBold : Font.Normal
        color: root.active ? Theme.textOnPrimary : Theme.text
        elide: Text.ElideRight
        width: Math.max(0, root.width - 24 - 60)
    }

    Text {
        id: badgeText
        visible: root.badge.length > 0
        anchors.right: parent.right
        anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        text: root.badge
        font.family: Theme.fontFamily
        font.pixelSize: 11
        color: root.active ? Theme.textOnPrimary : Theme.textDim
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
