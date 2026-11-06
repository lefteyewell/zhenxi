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

/* 上传人脸搜图——人脸选择器（0.6.21）：上传图含多张脸时让用户挑一张
   再搜（此前固定取置信度最高的一张，合影里的其他人搜不到）。
   用法：openWith(payload)，payload={path, faces:[{index,score,thumb}]}；
   点选后 emit facePicked(path, index) 由调用方发起搜索。 */
Popup {
    id: root

    objectName: "facePickerDialog"

    signal facePicked(string path, int index)

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: Math.min(parent.width - 60, Math.max(420, 132 * Math.min(_faces.length, 5) + 48))
    height: Math.min(parent.height - 40, 96 + Math.ceil(_faces.length / Math.max(1, Math.floor((width - 48) / 132))) * 152 + 110)
    padding: 0

    property string _path: ""
    property var _faces: []

    function openWith(payload) {
        _path = payload.path || ""
        _faces = payload.faces || []
        faceGrid.model = _faces
        open()
    }

    function _thumbUrl(p) {
        /* Windows 临时目录带反斜杠 → file URL */
        return "file:///" + encodeURI(("" + p).split("\\").join("/"))
    }

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
                    text: I18n.tr("选择要搜索的人脸")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("图中检测到多张人脸，点选其中一张进行搜索")
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

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

        GridView {
            id: faceGrid
            objectName: "facePickerGrid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Theme.spacingMedium
            clip: true
            cellWidth: 132
            cellHeight: 152
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Item {
                width: faceGrid.cellWidth
                height: faceGrid.cellHeight

                Rectangle {
                    id: faceCard
                    anchors.fill: parent
                    anchors.margins: 6
                    radius: Theme.radiusSmall
                    color: Theme.bg
                    border.width: 2
                    border.color: faceMouse.containsMouse ? Theme.primary : Theme.divider

                    Image {
                        id: thumb
                        anchors.fill: parent
                        anchors.margins: 8
                        anchors.bottomMargin: 24
                        source: root._thumbUrl(modelData.thumb)
                        fillMode: Image.PreserveAspectCrop
                        cache: false
                        asynchronous: true
                    }

                    Text {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 5
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: I18n.tr("脸 ") + (index + 1)
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                    }

                    MouseArea {
                        id: faceMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.close()
                            root.facePicked(root._path, modelData.index)
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingLarge
            Layout.bottomMargin: Theme.spacingSmall
            text: I18n.tr("提示：搜索只用您选中的这一张脸；想搜图中其他人，请再点一次选择")
            font.family: Theme.fontFamily
            font.pixelSize: 10
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
    }
}
