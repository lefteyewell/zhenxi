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

/* 层级标签选择器：从已有标签树里挑一个节点，或在某个节点下新建子标签。
   产出的是完整路径（如「旅行/国内/北京」），交给调用方打标签。
   用法：openPicker() → 选/填 → 确定 → tagPicked(path) */
Dialog {
    id: root
    objectName: "tagPickerDialog"
    title: root.pickOnly ? I18n.tr("选择目标父节点") : I18n.tr("选择标签")
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    /* 0.5.41：自定义可拖动标题栏 */
    header: RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Theme.spacingMedium
        Layout.rightMargin: Theme.spacingMedium
        Layout.preferredHeight: 40
        PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 40 }
        Text {
            text: root.pickOnly ? I18n.tr("选择目标父节点") : I18n.tr("选择标签")
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Item { Layout.fillWidth: true }
    }
    width: 470
    height: 540

    property string currentPath: ""   // 选中的节点路径（"" = 顶层）
    // pickOnly=true：只选节点、不新建（供标签树「归入…」选目标父节点用）
    property bool pickOnly: false
    property var pendingPaths: []     // 调用方暂存的待处理路径（批量移动时用）
    signal tagPicked(string path)

    function finalPath() {
        var n = root.pickOnly ? "" : newField.text.trim()
        if (n.length > 0)
            return root.currentPath.length > 0 ? root.currentPath + "/" + n : n
        return root.currentPath
    }

    function openPicker() {
        root.currentPath = ""
        newField.text = ""
        root.refreshTree()
        root.open()
    }

    function refreshTree() {
        treeModel.clear()
        treeModel.append({ path: "", name: I18n.tr("（顶层：作为一级标签）"),
                           depth: 0, photoCount: 0 })
        var arr = LibraryBridge.tagTree()
        for (var i = 0; i < arr.length; ++i)
            treeModel.append(arr[i])
    }

    onAccepted: {
        var p = root.finalPath()
        if (p.length > 0) root.tagPicked(p)
    }

    ListModel { id: treeModel }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingMedium
        spacing: Theme.spacingSmall

        Text {
            text: I18n.tr("从标签树里选择，或选中一个节点后在下框输入新子标签名")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.surface
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider

            ListView {
                id: treeView
                objectName: "tagPickerList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                spacing: Theme.spacingTiny
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: treeModel
                delegate: Rectangle {
                    width: treeView.width
                    height: 36
                    radius: Theme.radiusSmall
                    color: root.currentPath === model.path ? Theme.hover : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingSmall + (model.depth || 0) * 18
                        anchors.rightMargin: Theme.spacingSmall
                        spacing: Theme.spacingSmall
                        Text {
                            text: model.name
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            visible: (model.photoCount || 0) > 0
                            text: model.photoCount + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.currentPath = model.path
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: !root.pickOnly
            Text {
                text: I18n.tr("在所选节点下新建：")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
            }
            TextField {
                id: newField
                objectName: "tagPickerNewField"
                Layout.fillWidth: true
                placeholderText: I18n.tr("留空则直接用所选标签")
                font.family: Theme.fontFamily
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            radius: Theme.radiusSmall
            color: Theme.surfaceAlt
            Text {
                anchors.centerIn: parent
                text: I18n.tr("将打标签为：") + (root.finalPath() || I18n.tr("（未选择）"))
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideRight
            }
        }
    }
}
