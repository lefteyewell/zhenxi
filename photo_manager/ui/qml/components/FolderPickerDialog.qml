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

/* 自绘文件夹选择器：不依赖 Qt 系统对话框，打包后弹出行为与源码一致 */
Popup {
    id: root

    objectName: "folderPicker"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 560
    height: 500
    padding: 0

    property string dialogTitle: I18n.tr("选择文件夹")
    property string currentPath: ""
    property bool multiSelect: true       // 为 false 时隐藏多选框（备份/移出/导出等"选目标"场景）
    property bool showRecursiveOption: false  // 扫描入库场景显示"包含子文件夹"选项
    property bool recursiveOption: true       // 当前选择：是否包含子文件夹
    property var _selMap: ({})
    property int _selCount: 0
    signal pathChosen(string path)
    signal pathsChosen(var paths)

    function toggleSelect(path) {
        if (!root.multiSelect) return
        var m = {}
        for (var k in root._selMap) m[k] = true
        if (m[path]) {
            delete m[path]
        } else {
            m[path] = true
        }
        /* 必须整体重新赋值触发 var 属性变更通知：QML 绑定对 JS 对象的内部修改
           无感知，delegate 的 isSelected 只在创建时求值（曾致勾选后无视觉反馈，
           切走再切回 delegate 重建才显示勾选）。 */
        root._selMap = m
        root._selCount = 0
        for (var k in m) root._selCount++
        selHint.text = root._selCount > 0
            ? I18n.tr("已选 ") + root._selCount + I18n.tr(" 个文件夹（确定将一起扫描）")
            : root.hintText()
        clearSelBtn.visible = root._selCount > 0
    }

    function hintText() {
        return root.multiSelect
            ? I18n.tr("勾选文件夹可多选并一起添加；单击名称可进入子文件夹")
            : I18n.tr("单击进入子文件夹，选择目标后点确定")
    }

    function clearSelection() {
        /* 同 toggleSelect：整体重置触发变更通知，立即清掉所有勾选视觉 */
        root._selMap = {}
        root._selCount = 0
        selHint.text = root.hintText()
        clearSelBtn.visible = false
    }

    function selectedPaths() {
        var paths = []
        for (var k in root._selMap) paths.push(k)
        return paths
    }

    function refresh() {
        var kids = LibraryBridge.fsChildren(root.currentPath)
        var dirs = []
        for (var i = 0; i < kids.length; i++)
            if (kids[i].isDir)
                dirs.push(kids[i])
        folderList.model = dirs
        folderList.currentIndex = -1
        emptyText.visible = dirs.length === 0
    }

    function openDialog(initialPath) {
        root.currentPath = initialPath || LibraryBridge.fsLastRoot() || LibraryBridge.fsHome()
        refresh()
        root.open()
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
                id: folderList
                objectName: "folderList"
                anchors.fill: parent
                anchors.margins: 4
                clip: true
                spacing: 2
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Item {
                    width: folderList.width
                    height: 36
                    property bool isSelected: root.multiSelect && root._selMap[modelData.path] === true
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: {
                            if (isSelected) return Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.12)
                            if (folderList.currentIndex === index) return Theme.hover
                            return "transparent"
                        }
                    }
                    Rectangle {
                        visible: root.multiSelect
                        width: 16
                        height: 16
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        radius: 4
                        color: isSelected ? Theme.primary : "transparent"
                        border.width: 1
                        border.color: isSelected ? Theme.primary : Theme.divider
                        Text {
                            anchors.centerIn: parent
                            visible: isSelected
                            text: "✓"
                            font.pixelSize: 11
                            color: "white"
                        }
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: root.multiSelect ? 36 : 12
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        text: modelData.name
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: folderList.currentIndex === index ? Theme.primary : Theme.text
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            folderList.currentIndex = index
                            root.currentPath = modelData.path
                            root.refresh()
                        }
                    }
                    MouseArea {
                        visible: root.multiSelect
                        width: 28
                        height: 28
                        anchors.left: parent.left
                        anchors.leftMargin: 4
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: root.toggleSelect(modelData.path)
                    }
                }
            }

            Text {
                id: emptyText
                anchors.centerIn: parent
                visible: false
                text: I18n.tr("（此文件夹没有子文件夹）")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
        }

        /* 子文件夹选项：独立一行，避免挤占底部按钮行（曾因行宽不足被裁切） */
        CheckBox {
            id: recursiveChk
            objectName: "pickerRecursiveChk"
            visible: root.showRecursiveOption
            text: I18n.tr("包含子文件夹")
            checked: root.recursiveOption
            font.family: Theme.fontFamily
            font.pixelSize: 12
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingSmall
            onToggled: root.recursiveOption = checked
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                id: selHint
                Layout.fillWidth: true
                Layout.maximumWidth: 320
                elide: Text.ElideRight
                text: root.hintText()
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true }
            PMButton {
                id: clearSelBtn
                objectName: "pickerClearSel"
                text: I18n.tr("清空选择")
                visible: false
                onClicked: root.clearSelection()
            }
            PMButton {
                objectName: "pickerCancel"
                tooltip: I18n.tr("取消选择并关闭")
                text: I18n.tr("取消")
                onClicked: root.close()
            }
            PMButton {
                objectName: "pickerOk"
                tooltip: I18n.tr("确定所选目录")
                text: I18n.tr("确定")
                onClicked: {
                    var paths = root.multiSelect ? root.selectedPaths() : []
                    if (paths.length > 0) {
                        root.pathsChosen(paths)
                    } else {
                        root.pathChosen(root.currentPath)
                    }
                    if (root.multiSelect) root.clearSelection()
                    root.close()
                }
            }
        }
    }
}
