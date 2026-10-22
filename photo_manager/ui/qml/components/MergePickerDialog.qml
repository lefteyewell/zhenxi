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

/* 合并选择框：人物合并 / 标签合并共用。
   mode: "person" | "tag"；sourceId/sourceTag 为被合并方（列表中剔除自己）；
   确定后发 picked(item)，item 含 name、id（标签 id=0）、photoCount。 */
Popup {
    id: root
    objectName: "mergePickerDialog"
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    width: 440
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2

    property string mode: "person"
    property int sourceId: 0
    property string sourceTag: ""
    property string hint: ""
    property string title: ""

    signal picked(var item)

    padding: Theme.spacingMedium
    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    ListModel { id: itemsModel }

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
        Text {
            text: root.hint
            visible: root.hint.length > 0
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 260
            color: Theme.surfaceAlt
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider
            ListView {
                id: listView
                objectName: "mergePickerList"
                anchors.fill: parent
                anchors.margins: Theme.spacingTiny
                spacing: 2
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: itemsModel
                delegate: Rectangle {
                    width: listView.width
                    height: 34
                    radius: Theme.radiusSmall
                    color: listView.currentIndex === index ? Theme.hover : "transparent"
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.rightMargin: Theme.spacingMedium
                        Text {
                            Layout.fillWidth: true
                            text: model.name
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
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
                        onClicked: listView.currentIndex = index
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: itemsModel.count === 0
                    text: I18n.tr("没有可合并的项")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSmall
            Item { Layout.fillWidth: true }
            PMButton {
                objectName: "mergeCancel"
                tooltip: I18n.tr("取消合并")
                text: I18n.tr("取消")
                width: 72
                height: 30
                onClicked: root.close()
            }
            PMButton {
                objectName: "mergeOk"
                tooltip: I18n.tr("执行合并")
                text: I18n.tr("确定")
                emphasized: true
                width: 72
                height: 30
                onClicked: {
                    if (listView.currentIndex >= 0) {
                        root.picked(itemsModel.get(listView.currentIndex))
                        root.close()
                    }
                }
            }
        }
    }

    onOpened: refresh()

    function refresh() {
        itemsModel.clear()
        var arr = LibraryBridge.people()
        if (root.mode === "tag")
            arr = LibraryBridge.tags()
        for (var i = 0; i < arr.length; ++i) {
            var it = arr[i]
            var isSelf = root.mode === "person"
                         ? (it.id === root.sourceId)
                         : (it.name === root.sourceTag)
            if (isSelf) continue
            itemsModel.append({
                name: it.name,
                id: it.id || 0,
                photoCount: it.photoCount
            })
        }
        listView.currentIndex = itemsModel.count > 0 ? 0 : -1
    }
}