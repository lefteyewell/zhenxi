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
import components 1.0
import i18n 1.0

/* 通用重命名输入框：人物/标签重命名共用。
   context: "person" | "tag"；确认后发 accepted(value)。 */
Popup {
    id: root
    objectName: "renameDialog"
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    width: 380
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2

    property string title: ""
    property string context: "person"
    property int personId: 0
    property string initialValue: ""

    signal accepted(string value)

    padding: Theme.spacingMedium
    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacingMedium
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 32 }
            Text {
                text: root.title
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
        }
        TextField {
            id: renameField
            objectName: "renameField"
            Layout.fillWidth: true
            text: root.initialValue
            placeholderText: I18n.tr("输入新名称")
            placeholderTextColor: Theme.textDim
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            onAccepted: root._confirm()
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSmall
            Item { Layout.fillWidth: true }
            PMButton {
                objectName: "renameCancel"
                tooltip: I18n.tr("放弃修改并关闭")
                text: I18n.tr("取消")
                width: 72
                height: 30
                onClicked: root.close()
            }
            PMButton {
                objectName: "renameOk"
                tooltip: I18n.tr("保存修改并关闭")
                text: I18n.tr("确定")
                emphasized: true
                width: 72
                height: 30
                onClicked: root._confirm()
            }
        }
    }

    onOpened: {
        renameField.text = root.initialValue
        renameField.forceActiveFocus()
        renameField.selectAll()
    }

    function _confirm() {
        var v = renameField.text.trim()
        if (v.length === 0) return
        root.accepted(v)
        root.close()
    }
}