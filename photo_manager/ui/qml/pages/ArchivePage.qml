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

/* 作废视图（原"归档"）：列出已作废（archived=1）的照片，默认从普通浏览隐藏。
   这里可单张或批量恢复显示。与I18n.tr("程序内不删除")红线一致：
   作废只改数据库标记、绝不删除或改动原图。 */
Item {
    id: root
    objectName: "archivePage"

    signal photoClicked(int photoId)

    property int cellSize: 128
    property var photos: []

    function refresh() {
        var rows = LibraryBridge.archivedPhotos(0, 5000)
        root.photos = rows
        countText.text = rows.length + I18n.tr(" 张已作废")
        emptyText.visible = (rows.length === 0)
    }

    function _restore(id) {
        if (LibraryBridge.setArchived(id, false)) {
            toastLayer.show(I18n.tr("已恢复显示"), "success")
            refresh()
        }
    }

    function restoreAll() {
        if (root.photos.length === 0) return
        var ids = root.photos.map(function (p) { return p.id })
        var n = LibraryBridge.setArchivedBatch(ids, false)
        if (n > 0) {
            toastLayer.show(I18n.tr("已恢复 ") + n + I18n.tr(" 张到主时间轴"), "success")
            refresh()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            leftPadding: Theme.spacingMedium
            rightPadding: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                text: I18n.tr("作废（不删除）")
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                id: countText
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true }
            PMButton {
                objectName: "archiveRestoreAllBtn"
                tooltip: I18n.tr("全部恢复显示（取消作废，照片从未被删除过）")
                text: I18n.tr("恢复全部")
                height: 30
                enabled: root.photos.length > 0
                onClicked: root.restoreAll()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            color: Theme.surface
            radius: Theme.radiusLarge
            border.width: 1
            border.color: Theme.divider

            ScrollView {
                id: sv
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

                Flow {
                    width: sv.availableWidth
                    spacing: Theme.spacingSmall

                    Repeater {
                        model: root.photos
                        delegate: Rectangle {
                            width: root.cellSize
                            height: root.cellSize
                            radius: Theme.radiusMedium
                            color: Theme.bg
                            border.width: 1
                            border.color: Theme.divider
                            clip: true

                            Image {
                                id: thumbImg
                                anchors.fill: parent
                                anchors.margins: 2
                                fillMode: Image.PreserveAspectCrop
                                source: modelData.thumb || ""
                                asynchronous: true
                                cache: true
                                smooth: false
                                visible: status === Image.Ready
                            }
                            Rectangle {
                                anchors.fill: parent
                                color: Theme.surfaceAlt
                                visible: thumbImg.status !== Image.Ready
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.faceCount > 0 ? "👤×" + modelData.faceCount : "?"
                                    font.pixelSize: 18
                                    color: Theme.textDim
                                }
                            }
                            Text {
                                visible: modelData.rating > 0
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.margins: 4
                                text: "★".repeat(modelData.rating)
                                font.pixelSize: 10
                                color: "#f5c842"
                                style: Text.Outline
                                styleColor: "black"
                            }
                            /* 右上角"恢复"按钮：取消归档（回到主时间轴，原图不动） */
                            PMButton {
tooltip: I18n.tr("恢复这张照片在普通浏览中显示（取消作废）")
                                objectName: "archiveRestoreBtn_" + modelData.id
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 3
                                width: 46
                                height: 20
                                text: I18n.tr("恢复")
                                font.pixelSize: 10
                                onClicked: root._restore(modelData.id)
                            }

                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.photoClicked(modelData.id)
                            }
                        }
                    }
                }
            }

            Text {
                id: emptyText
                visible: false
                anchors.centerIn: parent
                width: parent.width - 40
                text: I18n.tr("还没有作废的照片。\n在右侧信息面板点「作废（不删除）」，或右键照片选「作废所选」，即可把不想再看到的照片移出普通浏览（随时可恢复）。")
                horizontalAlignment: Text.AlignHCenter
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
        }
    }
}
