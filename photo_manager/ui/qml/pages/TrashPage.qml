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

/* 回收站：三个区。
   1) 移出记录：已移出照片的记录（按目标目录分组），可一键重新导入回库。
   2) 缺失照片：被「重建索引」标记为 missing 的照片（文件已在系统外被删除），
      可单选 / 全选 / 按文件夹批量选择后移入待删除区（可恢复）。
   3) 待删除：第二阶段，在此才能彻底删除记录与缩略图（不可恢复）。 */
Item {
    id: root
    objectName: "trashPage"

    signal restoreRequested(string folder)
    signal restoreAllRequested()

    property int tab: 0
    property var selMissing: []      // 缺失照片选中 id 数组
    property var selPending: []      // 待删除选中 id 数组

    ListModel { id: trashModel }
    ListModel { id: missingModel }
    ListModel { id: pendingModel }

    /* 0.5.36：移出目录列表排序 */
    property int trashSortMode: 0

    function toggle(arrProp, id) {
        var arr = root[arrProp]
        var i = arr.indexOf(id)
        if (i >= 0) arr.splice(i, 1); else arr.push(id)
        root[arrProp] = arr.slice()      // 重赋值触发绑定刷新
    }
    function selectAll(arrProp, model, onlyFolder) {
        var arr = []
        for (var i = 0; i < model.count; ++i) {
            var it = model.get(i)
            if (!onlyFolder || onlyFolder === it.folder) arr.push(it.id)
        }
        root[arrProp] = arr
    }
    function clearSel(arrProp) { root[arrProp] = [] }

    function refresh() {
        trashModel.clear()
        var arr = LibraryBridge.movedOutList()
        /* 0.5.36：移出目录列表排序（0=默认序；1=文件夹名；2=照片数多→少） */
        if (root.trashSortMode === 1)
            arr = arr.slice().sort(function (a, b) {
                return String(a.folder || "").localeCompare(String(b.folder || ""))
            })
        else if (root.trashSortMode === 2)
            arr = arr.slice().sort(function (a, b) { return (b.photoCount || 0) - (a.photoCount || 0) })
        for (var i = 0; i < arr.length; ++i) {
            var it = arr[i]
            trashModel.append({ folder: it.folder, photoCount: it.photoCount, movedAt: it.movedAt })
        }
        trashEmptyText.visible = trashModel.count === 0

        missingModel.clear()
        var ms = LibraryBridge.missingList(0, 2000)
        for (i = 0; i < ms.length; ++i) missingModel.append(ms[i])
        missingEmptyText.visible = missingModel.count === 0
        root.selMissing = []

        pendingModel.clear()
        var pd = LibraryBridge.pendingDeleteList(0, 2000)
        for (i = 0; i < pd.length; ++i) pendingModel.append(pd[i])
        pendingEmptyText.visible = pendingModel.count === 0
        root.selPending = []
        folderCombo.model = Array.from(new Set(ms.map(function(x){ return x.folder })))
        purgeConfirm = false
    }

    property bool purgeConfirm: false
    function askPurge() {
        if (!purgeConfirm) {
            purgeConfirm = true
            purgeTimer.restart()
            return
        }
        purgeConfirm = false
        purgeTimer.stop()
        var n = LibraryBridge.purgeDeleted(selPending)
        root.messageRequested(n > 0 ? (I18n.tr("已彻底删除 ") + n + I18n.tr(" 条缺失记录")) : I18n.tr("未选择任何记录"))
        refresh()
    }
    Timer { id: purgeTimer; interval: 4000; onTriggered: root.purgeConfirm = false }

    signal messageRequested(string msg)

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
                text: I18n.tr("回收站")
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { width: 12; height: 10 }

            PMButton {
                objectName: "tabMovedBtn"
                tooltip: I18n.tr("查看已移出到文件夹的照片记录（文件未删除，可重新导入）"); width: 92; height: 30
                text: I18n.tr("移出记录"); highlighted: root.tab === 0
                onClicked: root.tab = 0
            }
            PMButton {
                objectName: "tabMissingBtn"
                tooltip: I18n.tr("查看系统里已被删除的照片记录"); width: 92; height: 30
                text: I18n.tr("缺失照片"); highlighted: root.tab === 1
                onClicked: root.tab = 1
            }
            PMButton {
                objectName: "tabPendingBtn"
                tooltip: I18n.tr("第二阶段：彻底删除记录与缩略图，操作不可恢复"); width: 92; height: 30
                text: I18n.tr("待删除"); highlighted: root.tab === 2
                onClicked: root.tab = 2
            }
            Item { Layout.fillWidth: true; width: 10 }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.tab === 0 ? I18n.tr("移出到文件夹的照片记录（文件不会删除，可一键重新导入回库）")
                     : root.tab === 1 ? I18n.tr("系统外被删除的照片：选择后移入待删除区（可恢复），文件找回会自动恢复")
                     : I18n.tr("第二阶段：只有在这里才会彻底删除记录与缩略图，操作不可恢复")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                elide: Text.ElideRight
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

            // ---------- 区 1：移出记录 ----------
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingSmall
                visible: root.tab === 0

                Row {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSmall
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: trashModel.count > 0 ? (trashModel.count + I18n.tr(" 个移出目录")) : ""
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textDim
                    }
                    Item { Layout.fillWidth: true; width: 10 }
                    PMButton {
                        objectName: "trashSortBtn"
                        tooltip: I18n.tr("切换移出目录列表排序方式")
                        text: I18n.tr("排序 ▾")
                        height: 30
                        visible: root.tab === 0
                        Menu {
                            id: trashSortMenu
                            MenuItem { text: I18n.tr("默认顺序"); checkable: true; checked: root.trashSortMode === 0
                                       onTriggered: { root.trashSortMode = 0; root.refresh() } }
                            MenuItem { text: I18n.tr("按文件夹名（A→Z）"); checkable: true; checked: root.trashSortMode === 1
                                       onTriggered: { root.trashSortMode = 1; root.refresh() } }
                            MenuItem { text: I18n.tr("按照片数（多→少）"); checkable: true; checked: root.trashSortMode === 2
                                       onTriggered: { root.trashSortMode = 2; root.refresh() } }
                        }
                        onClicked: trashSortMenu.popup(this, 0, height + 2)
                    }
                    PMButton {
                        objectName: "trashRestoreAllBtn"
                        tooltip: I18n.tr("把全部移出记录的照片重新导入回库")
                        text: I18n.tr("全部恢复")
                        width: 96
                        height: 30
                        visible: trashModel.count > 0
                        onClicked: root.restoreAllRequested()
                    }
                }
                ListView {
                    id: listView
                    objectName: "trashList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.spacingTiny
                    clip: true
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                    model: trashModel

                    delegate: Rectangle {
                        width: listView.width
                        height: 52
                        radius: Theme.radiusMedium
                        color: Theme.surfaceAlt

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingMedium
                            anchors.rightMargin: Theme.spacingMedium
                            spacing: Theme.spacingMedium
                            Column {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: model.folder
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: Theme.text
                                    elide: Text.ElideMiddle
                                    width: parent.width
                                }
                                Text {
                                    text: model.photoCount + I18n.tr(" 张 · 最近移出 ") + model.movedAt
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11
                                    color: Theme.textDim
                                }
                            }
                            PMButton {
                                objectName: "trashRestoreBtn"
                                tooltip: I18n.tr("把选中的移出记录重新导入回库")
                                text: I18n.tr("重新导入")
                                width: 96
                                height: 30
                                onClicked: root.restoreRequested(model.folder)
                            }
                        }
                    }

                    Text {
                        id: trashEmptyText
                        objectName: "trashEmptyText"
                        anchors.centerIn: parent
                        text: I18n.tr("暂无已移出记录")
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.textDim
                    }
                }
            }

            // ---------- 区 2：缺失照片 ----------
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingSmall
                visible: root.tab === 1

                Row {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSmall
                    CheckBox {
                        objectName: "missingSelectAll"
                        text: I18n.tr("全选")
                        anchors.verticalCenter: parent.verticalCenter
                        checked: missingModel.count > 0 && root.selMissing.length === missingModel.count
                        onClicked: {
                            if (checked) root.clearSel("selMissing")
                            else root.selectAll("selMissing", missingModel, null)
                        }
                    }
                    ComboBox {
                        id: folderCombo
                        objectName: "missingFolderCombo"
                        width: 260; height: 30
                        anchors.verticalCenter: parent.verticalCenter
                        model: []
                        displayText: currentText === "" ? I18n.tr("按文件夹批量选择") : currentText
                        onActivated: {
                            root.selectAll("selMissing", missingModel, currentText)
                        }
                    }
                    Item { Layout.fillWidth: true; width: 10 }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("已选 ") + root.selMissing.length + " / " + missingModel.count
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textDim
                    }
                    PMButton {
                        objectName: "moveToPendingBtn"
                        tooltip: I18n.tr("把选中的缺失记录移入待删除区")
                        text: I18n.tr("移入待删除区")
                        width: 120; height: 30
                        enabled: root.selMissing.length > 0
                        onClicked: {
                            var n = LibraryBridge.moveToPendingDelete(root.selMissing)
                            root.messageRequested(I18n.tr("已移入待删除区 ") + n + I18n.tr(" 条"))
                            root.refresh()
                        }
                    }
                }
                ListView {
                    id: missingListView
                    objectName: "missingList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.spacingTiny
                    clip: true
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                    model: missingModel

                    delegate: Rectangle {
                        width: missingListView.width
                        height: 56
                        radius: Theme.radiusMedium
                        color: root.selMissing.indexOf(model.id) >= 0 ? Theme.surfaceAlt : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingSmall
                            spacing: Theme.spacingSmall
                            CheckBox {
                                anchors.verticalCenter: parent.verticalCenter
                                checked: root.selMissing.indexOf(model.id) >= 0
                                onClicked: root.toggle("selMissing", model.id)
                            }
                            Image {
                                width: 48; height: 48; fillMode: Image.PreserveAspectFit
                                source: model.thumb
                            }
                            Column {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: model.name
                                    font.family: Theme.fontFamily; font.pixelSize: 13
                                    color: Theme.text; elide: Text.ElideMiddle; width: parent.width
                                }
                                Text {
                                    text: model.folder + (model.takenAt !== "" ? " · " + model.takenAt : "")
                                    font.family: Theme.fontFamily; font.pixelSize: 11
                                    color: Theme.textDim; elide: Text.ElideMiddle; width: parent.width
                                }
                            }
                        }
                    }
                }
                Text {
                    id: missingEmptyText
                    objectName: "missingEmptyText"
                    /* 父容器是 ColumnLayout：用 anchors 属于未定义行为（Qt 会告警），
                       改用 Layout.alignment + horizontalAlignment 实现水平居中。 */
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    visible: missingModel.count === 0
                    text: I18n.tr("没有缺失照片 —— 重建索引后发现系统外删除的照片会出现在这里")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }

            // ---------- 区 3：待删除 ----------
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingSmall
                visible: root.tab === 2

                Row {
                    Layout.fillWidth: true
                    spacing: Theme.spacingSmall
                    CheckBox {
                        objectName: "pendingSelectAll"
                        text: I18n.tr("全选")
                        anchors.verticalCenter: parent.verticalCenter
                        checked: pendingModel.count > 0 && root.selPending.length === pendingModel.count
                        onClicked: {
                            if (checked) root.clearSel("selPending")
                            else root.selectAll("selPending", pendingModel, null)
                        }
                    }
                    Item { Layout.fillWidth: true; width: 10 }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("已选 ") + root.selPending.length + " / " + pendingModel.count
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textDim
                    }
                    PMButton {
                        objectName: "restorePendingBtn"
                        tooltip: I18n.tr("把选中的待删除记录恢复（文件找回后可自动恢复）")
                        text: I18n.tr("恢复到缺失")
                        width: 110; height: 30
                        enabled: root.selPending.length > 0
                        onClicked: {
                            var n = LibraryBridge.restorePendingDelete(root.selPending)
                            root.messageRequested(I18n.tr("已恢复 ") + n + I18n.tr(" 条"))
                            root.refresh()
                        }
                    }
                    PMButton {
                        objectName: "purgeBtn"
                        tooltip: I18n.tr("彻底删除选中的记录与缩略图（不可恢复，原照片文件不受影响）")
                        text: root.purgeConfirm
                              ? I18n.tr("确认彻底删除(") + root.selPending.length + ")"
                              : I18n.tr("彻底删除")
                        width: 150; height: 30
                        enabled: root.selPending.length > 0
                        onClicked: root.askPurge()
                    }
                }
                ListView {
                    id: pendingListView
                    objectName: "pendingList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.spacingTiny
                    clip: true
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                    model: pendingModel

                    delegate: Rectangle {
                        width: pendingListView.width
                        height: 56
                        radius: Theme.radiusMedium
                        color: root.selPending.indexOf(model.id) >= 0 ? Theme.surfaceAlt : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingSmall
                            spacing: Theme.spacingSmall
                            CheckBox {
                                anchors.verticalCenter: parent.verticalCenter
                                checked: root.selPending.indexOf(model.id) >= 0
                                onClicked: root.toggle("selPending", model.id)
                            }
                            Image {
                                width: 48; height: 48; fillMode: Image.PreserveAspectFit
                                source: model.thumb
                            }
                            Column {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: model.name
                                    font.family: Theme.fontFamily; font.pixelSize: 13
                                    color: Theme.text; elide: Text.ElideMiddle; width: parent.width
                                }
                                Text {
                                    text: model.folder + (model.takenAt !== "" ? " · " + model.takenAt : "")
                                    font.family: Theme.fontFamily; font.pixelSize: 11
                                    color: Theme.textDim; elide: Text.ElideMiddle; width: parent.width
                                }
                            }
                        }
                    }
                }
                Text {
                    id: pendingEmptyText
                    objectName: "pendingEmptyText"
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    visible: pendingModel.count === 0
                    text: I18n.tr("待删除区为空")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }
        }
    }
}
