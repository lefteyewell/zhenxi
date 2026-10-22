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

/* 批量打标签输入框：确认后发出 tagRequested(tag)（去首尾空格）。 */
Dialog {
    id: root
    objectName: "batchTagDialog"
    title: I18n.tr("批量打标签")
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    /* 0.5.41：自定义可拖动标题栏（替代默认标题栏，支持拖动窗口） */
    header: RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Theme.spacingMedium
        Layout.rightMargin: Theme.spacingMedium
        Layout.preferredHeight: 40
        PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 40 }
        Text {
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Item { Layout.fillWidth: true }
    }
    width: 420
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2

    property string label: ""

    signal tagRequested(string tag)

    onOpened: batchTagField.forceActiveFocus()
    onAccepted: {
        var tag = batchTagField.text.trim()
        if (tag.length > 0)
            root.tagRequested(tag)
        batchTagField.text = ""
    }
    onRejected: batchTagField.text = ""

    contentItem: ColumnLayout {
        spacing: 12
        Text {
            Layout.fillWidth: true
            text: root.label
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.text
            wrapMode: Text.Wrap
        }
        TextField {
            id: batchTagField
            objectName: "batchTagField"
            Layout.fillWidth: true
            placeholderText: I18n.tr("输入标签名，如：出差")
            placeholderTextColor: Theme.textDim
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 13
            onAccepted: root.accept()
        }
    }
}