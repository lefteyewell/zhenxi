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
import i18n 1.0

/* 0.6.21：随包文本查看器（帮助菜单「开源许可 / 第三方依赖」入口）。
   按需从安装目录读取 LICENSE / THIRD-PARTY-NOTICES.md 全文展示，
   只读、可滚动、可全选复制。 */
Dialog {
    id: root
    objectName: "textDocDialog"

    modal: true
    width: Math.min(parent ? parent.width - 80 : 860, 820)
    height: Math.min(parent ? parent.height - 80 : 640, 620)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    title: ""

    function openDoc(docTitle, fileName) {
        root.title = docTitle
        docText.text = I18n.tr("加载中…")
        root.open()
        /* open 后下一拍再读，避免阻塞打开动画（文本可达数十 KB） */
        Qt.callLater(function() {
            docText.text = LibraryBridge.readPackagedText(fileName)
        })
    }

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.width: 1
        border.color: Theme.divider
    }

    header: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            Text {
                text: root.title
                Layout.fillWidth: true
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideRight
            }
            PMButton {
                tooltip: I18n.tr("关闭")
                text: "×"
                width: 32
                height: 28
                onClicked: root.close()
            }
        }
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }
    }

    ScrollView {
        anchors.fill: parent
        ScrollBar.horizontal.policy: ScrollBar.AsNeeded

        TextArea {
            id: docText
            readOnly: true
            wrapMode: TextArea.NoWrap
            selectByMouse: true
            persistentSelection: true
            color: Theme.text
            selectionColor: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: 12
            topPadding: 12
            bottomPadding: 12
            leftPadding: 16
            rightPadding: 16
            background: null
        }
    }
}
