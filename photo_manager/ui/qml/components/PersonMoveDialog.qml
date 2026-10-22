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

/* 拆分照片：把选中照片从当前人物移出到 另一人物 / 新建人物。
   确定后发 picked(personId)；personId=-1 表示I18n.tr("移出为新建人物")。 */
Popup {
    id: root
    objectName: "personMoveDialog"
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    width: 440
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2

    property var targetPhotos: []
    property int currentPersonId: 0
    property bool faceMode: false
    property int faceId: 0

    signal picked(int personId)

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
                text: root.faceMode ? I18n.tr("把这张人脸指派到…") : I18n.tr("把所选照片移出到…")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
        }
        Text {
            text: root.faceMode ? I18n.tr("（只移动这一张人脸，不影响照片里的其他人脸）")
                               : I18n.tr("（整张照片的所有人脸都会一起移动）")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 240
            color: Theme.surfaceAlt
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider
            ListView {
                id: listView
                objectName: "personMoveList"
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
                    text: root.faceMode ? I18n.tr("没有其他人物，可直接指为新建人物") : I18n.tr("没有其他人物，可直接移出为新建人物")
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
                objectName: "personMoveNewBtn"
                tooltip: I18n.tr("把这张脸拆分为一个新人物")
                text: root.faceMode ? I18n.tr("指为新建人物") : I18n.tr("移出为新建人物")
                width: 130
                height: 30
                onClicked: {
                    root.picked(-1)
                    root.close()
                }
            }
            PMButton {
                objectName: "personMoveCancel"
                tooltip: I18n.tr("取消并关闭弹窗")
                text: I18n.tr("取消")
                width: 72
                height: 30
                onClicked: root.close()
            }
            PMButton {
                objectName: "personMoveOk"
                tooltip: I18n.tr("把这张脸移到所选人物")
                text: I18n.tr("确定")
                emphasized: true
                width: 72
                height: 30
                onClicked: {
                    if (listView.currentIndex >= 0) {
                        root.picked(itemsModel.get(listView.currentIndex).id)
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
        for (var i = 0; i < arr.length; ++i) {
            var it = arr[i]
            if (it.id === root.currentPersonId) continue
            itemsModel.append({ name: it.name, id: it.id, photoCount: it.photoCount })
        }
        listView.currentIndex = itemsModel.count > 0 ? 0 : -1
    }
}