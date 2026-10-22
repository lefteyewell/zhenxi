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

/* 管理路径：列出当前索引依赖的根文件夹 + 防误删归集提醒 */
Popup {
    id: root

    objectName: "pathsDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 580
    height: 500
    padding: 0

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 52 }

            Column {
                spacing: 2
                Text {
                    text: I18n.tr("管理路径")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("照片索引所依赖的文件夹（树状展示全部层级，可点击展开/收起）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("关闭")
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        /* 防误删提醒 */
        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingLarge
            Layout.topMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            radius: 8
            color: Theme.accent
            opacity: 0.12
            border.width: 1
            border.color: Theme.accent

            Text {
                anchors.fill: parent
                anchors.margins: 10
                text: I18n.tr("提醒：本软件按文件路径索引照片，原图始终留在原文件夹，软件不会复制或移动它们。")
                      + I18n.tr("请勿在软件之外直接删除或移动以下文件夹中的照片，否则索引将失效、照片丢失且无法恢复。")
                      + I18n.tr("建议将照片统一归集到少数几个文件夹（尽量只保留 1~3 个根目录），")
                      + I18n.tr("集中管理更便于备份，也能避免误删。")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
                wrapMode: Text.Wrap
                lineHeight: 1.4
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        ListView {
            id: pathsList
            objectName: "pathsList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: Theme.spacingSmall
            Layout.bottomMargin: Theme.spacingSmall
            clip: true
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
            model: ListModel { id: pathsModel }

            function refresh() {
                pathsModel.clear()
                var arr = LibraryBridge.folderTreeAll()
                for (var i = 0; i < arr.length; ++i)
                    pathsModel.append(arr[i])
            }

            onCountChanged: {
                if (count === 0)
                    emptyHint.visible = true
                else
                    emptyHint.visible = false
            }
            Component.onCompleted: refresh()
            onVisibleChanged: if (visible) refresh()

            delegate: Rectangle {
                width: pathsList.width
                height: 38
                color: index % 2 === 0 ? Theme.surface : Theme.surfaceAlt

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingMedium + model.depth * 18
                    anchors.rightMargin: Theme.spacingMedium
                    spacing: Theme.spacingTiny

                    Text {
                        text: model.hasChildren
                              ? (model.expanded ? "▾" : "▸")
                              : "•"
                        font.pixelSize: 11
                        width: 16
                        color: Theme.textDim
                    }
                    Text {
                        Layout.fillWidth: true
                        text: model.name
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                        elide: Text.ElideRight
                    }
                    Text {
                        text: model.photoCount + I18n.tr(" 张")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: model.hasChildren ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (model.hasChildren) {
                            LibraryBridge.folderToggle(model.path, !model.expanded)
                            pathsList.refresh()
                        }
                    }
                }
            }
        }

        Text {
            id: emptyHint
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingLarge
            Layout.bottomMargin: Theme.spacingMedium
            visible: false
            text: I18n.tr("尚未添加照片路径。点击菜单「文件 → 添加照片文件夹…」，选择照片所在文件夹即可开始管理。")
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
    }
}
