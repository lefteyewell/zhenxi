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

/* 虚拟相册：用户自建分组（只存引用，不移动/复制任何照片文件）。
   点击相册进入照片视图；支持新建/重命名/删除相册。
   删除相册仅移除分组与关联记录，照片文件与库内记录完全不受影响。 */
Item {
    id: root
    objectName: "albumsPage"

    signal albumClicked(int albumId, string name)
    signal createRequested()
    signal renameRequested(int albumId, string name)
    signal deleteRequested(int albumId, string name)

    property var albums: []

    /* 0.5.36：排序（0=创建顺序，后端默认序；1=名称；2=照片数多→少） */
    property int sortMode: 0

    function refresh() {
        var rows = LibraryBridge.albums()
        if (root.sortMode === 1)
            rows = rows.slice().sort(function (a, b) {
                return String(a.name || "").localeCompare(String(b.name || ""), "zh")
            })
        else if (root.sortMode === 2)
            rows = rows.slice().sort(function (a, b) { return (b.photoCount || 0) - (a.photoCount || 0) })
        root.albums = rows
        countText.text = rows.length > 0 ? (rows.length + I18n.tr(" 个相册")) : ""
        emptyText.visible = (rows.length === 0)
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
                text: I18n.tr("相册")
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
                objectName: "albumSortBtn"
                tooltip: I18n.tr("选择相册排序方式（创建顺序/名称/照片数）")
                text: I18n.tr("排序 ▾")
                height: 30
                Menu {
                    id: albumSortMenu
                    MenuItem { text: I18n.tr("按创建顺序"); checkable: true; checked: root.sortMode === 0
                               onTriggered: { root.sortMode = 0; root.refresh() } }
                    MenuItem { text: I18n.tr("按名称（A→Z）"); checkable: true; checked: root.sortMode === 1
                               onTriggered: { root.sortMode = 1; root.refresh() } }
                    MenuItem { text: I18n.tr("按照片数（多→少）"); checkable: true; checked: root.sortMode === 2
                               onTriggered: { root.sortMode = 2; root.refresh() } }
                }
                onClicked: albumSortMenu.popup(this, 0, height + 2)
            }
            PMButton {
                objectName: "albumCreateBtn"
                tooltip: I18n.tr("新建一个空相册（只存照片引用，不复制不移动文件）")
                text: I18n.tr("＋ 新建相册")
                height: 30
                onClicked: root.createRequested()
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

                Column {
                    width: sv.availableWidth
                    spacing: Theme.spacingTiny

                    Repeater {
                        model: root.albums
                        delegate: Rectangle {
                            width: parent.width
                            height: 64
                            radius: Theme.radiusMedium
                            color: albumRow.hovered ? Theme.hover : Theme.bg
                            border.width: 1
                            border.color: Theme.divider

                            MouseArea {
                                id: albumRow
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.albumClicked(modelData.id, modelData.name)
                            }

                            Item {
                                id: coverWrap
                                width: 86
                                height: 56
                                anchors.left: parent.left
                                anchors.leftMargin: 6
                                anchors.verticalCenter: parent.verticalCenter
                                clip: true

                                Image {
                                    anchors.fill: parent
                                    fillMode: Image.PreserveAspectCrop
                                    source: modelData.cover || ""
                                    asynchronous: true
                                    cache: true
                                    smooth: false
                                    visible: status === Image.Ready
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    color: Theme.surfaceAlt
                                    visible: !modelData.cover
                                    Text {
                                        anchors.centerIn: parent
                                        text: "🖼"
                                        font.pixelSize: 20
                                        color: Theme.textDim
                                    }
                                }
                            }

                            Column {
                                anchors.left: coverWrap.right
                                anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                width: parent.width - coverWrap.width - 200
                                Text {
                                    text: modelData.name
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    color: Theme.text
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                                Text {
                                    text: modelData.photoCount + I18n.tr(" 张照片")
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    color: Theme.textDim
                                }
                            }

                            Row {
                                anchors.right: parent.right
                                anchors.rightMargin: Theme.spacingMedium
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 6
                                PMButton {
tooltip: I18n.tr("重命名该相册")
                                    objectName: "albumRenameBtn_" + modelData.id
                                    text: I18n.tr("重命名")
                                    width: 64
                                    height: 24
                                    onClicked: root.renameRequested(modelData.id, modelData.name)
                                }
                                PMButton {
tooltip: I18n.tr("删除该相册（只移除分组与引用，照片文件与库内记录完全不受影响）")
                                    objectName: "albumDeleteBtn_" + modelData.id
                                    text: I18n.tr("删除相册")
                                    width: 72
                                    height: 24
                                    onClicked: root.deleteRequested(modelData.id, modelData.name)
                                }
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
                text: I18n.tr("还没有相册。\n点右上角「新建相册」创建，然后选中照片右键选「添加到相册」即可归组。\n相册只是引用分组——不会复制、移动或删除任何照片文件。")
                horizontalAlignment: Text.AlignHCenter
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
        }
    }
}
