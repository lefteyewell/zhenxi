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

/* 自绘文件选择器：open（选择已有文件）/ save（指定文件名）两种模式 */
Popup {
    id: root

    objectName: "filePicker"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 620
    height: 540
    padding: 0

    property string dialogTitle: I18n.tr("选择文件")
    property string mode: "open"
    property string defaultSuffix: ""
    property string currentPath: ""
    property string selectedFile: ""
    signal fileChosen(string path)

    function refresh() {
        fileList.model = LibraryBridge.fsChildren(root.currentPath)
        fileList.currentIndex = -1
        root.selectedFile = ""
        emptyText.visible = fileList.count === 0
    }

    function openDialog(initialPath) {
        root.currentPath = initialPath || LibraryBridge.fsLastRoot() || LibraryBridge.fsHome()
        fileNameField.text = ""
        refresh()
        root.open()
        fileNameField.forceActiveFocus()
    }

    function joinPath(dir, name) {
        if (dir === "" || dir === "/") return dir + name
        return dir + "/" + name
    }

    function okEnabled() {
        if (root.mode === "save")
            return fileNameField.text.trim() !== ""
        return root.selectedFile !== ""
    }

    function chosen() {
        var p = ""
        if (root.mode === "save") {
            var nm = fileNameField.text.trim()
            if (nm === "") return
            if (root.defaultSuffix !== "" && nm.indexOf(".") < 0)
                nm += "." + root.defaultSuffix
            p = joinPath(root.currentPath, nm)
        } else {
            if (root.selectedFile === "") return
            p = root.selectedFile
        }
        root.fileChosen(p)
        root.close()
    }

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        width: root.availableWidth
        height: root.availableHeight
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 52 }

            Text {
                text: root.dialogTitle
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: "✕"
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.divider
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: Theme.spacingSmall
            Layout.bottomMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            PMButton {
                objectName: "pickerUp"
                tooltip: I18n.tr("返回上一级目录")
                text: I18n.tr("上级")
                onClicked: {
                    root.currentPath = LibraryBridge.fsParent(root.currentPath)
                    root.refresh()
                }
            }
            PMButton {
                objectName: "pickerHome"
                tooltip: I18n.tr("跳到用户主目录")
                text: I18n.tr("主页")
                onClicked: {
                    root.currentPath = LibraryBridge.fsHome()
                    root.refresh()
                }
            }
            PMButton {
                objectName: "pickerRoot"
                tooltip: I18n.tr("返回此电脑的盘符列表")
                text: I18n.tr("我的电脑")
                onClicked: {
                    root.currentPath = ""
                    root.refresh()
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                radius: 6
                color: Theme.bg
                border.width: 1
                border.color: Theme.divider
                Text {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideMiddle
                    text: root.currentPath === "" ? I18n.tr("（磁盘列表）") : root.currentPath
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.text
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            radius: Theme.radiusMedium
            color: Theme.bg
            border.width: 1
            border.color: Theme.divider

            ListView {
                id: fileList
                objectName: "fileList"
                anchors.fill: parent
                anchors.margins: 4
                clip: true
                spacing: 2
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Item {
                    width: fileList.width
                    height: 34
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: fileList.currentIndex === index ? Theme.hover : "transparent"
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 24
                        elide: Text.ElideRight
                        text: (modelData.isDir ? I18n.tr("[目录] ") : "") + modelData.name
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.weight: modelData.isDir ? Font.DemiBold : Font.Normal
                        color: fileList.currentIndex === index ? Theme.primary : Theme.text
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            fileList.currentIndex = index
                            if (modelData.isDir) {
                                root.currentPath = modelData.path
                                root.refresh()
                            } else if (root.mode === "open") {
                                root.selectedFile = modelData.path
                            } else {
                                fileNameField.text = modelData.name
                            }
                        }
                    }
                }
            }

            Text {
                id: emptyText
                anchors.centerIn: parent
                visible: false
                text: I18n.tr("（此文件夹没有内容）")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                text: I18n.tr("文件名")
                visible: root.mode === "save"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            TextField {
                id: fileNameField
                objectName: "fileNameField"
                visible: root.mode === "save"
                Layout.fillWidth: true
                Layout.preferredWidth: 220
                placeholderText: I18n.tr("输入文件名（无扩展名自动补 .") + root.defaultSuffix + "）"
                color: Theme.text
                placeholderTextColor: Theme.textDim
                background: Rectangle {
                    color: Theme.surface
                    radius: 6
                    border.width: 1
                    border.color: Theme.divider
                }
                font.pixelSize: 12
                font.family: Theme.fontFamily
                onTextChanged: {
                    okBtn.enabled = root.okEnabled()
                    if (root.mode === "save")
                        root.selectedFile = ""
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                objectName: "pickerCancel"
                tooltip: I18n.tr("取消选择并关闭")
                text: I18n.tr("取消")
                onClicked: root.close()
            }
            PMButton {
                id: okBtn
                objectName: "pickerOk"
                text: root.mode === "save" ? I18n.tr("保存") : I18n.tr("打开")
                enabled: root.okEnabled()
                onClicked: root.chosen()
            }
        }
    }
}
