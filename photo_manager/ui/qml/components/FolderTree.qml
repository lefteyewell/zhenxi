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
import i18n 1.0

/* 侧边栏"全部照片"下拉展开的整台电脑文件夹树
   mode="addedI18n.tr(": 只显示已添加的文件夹（此时隐藏右侧")添加到图库"按钮）
   mode="all":    显示整台电脑目录树，可逐级展开；每行左侧三态复选框
                 （0 未添加 / 1 部分子目录已入库 / 2 该文件夹已入库），
                 右侧I18n.tr("添加到图库")按钮将整个文件夹（含子文件夹）入库 */
Item {
    id: root

    /* 0.5.66：默认"仅已添加"（用户反馈——按文件夹打开时应默认聚焦已入库目录，
       而非整个磁盘树） */
    property string mode: "added"     // "added" | "all"
    signal folderChosen(string path, int count)
    signal ingestRequested(string path)   // 点击"添加到图库"：与文件菜单"添加照片文件夹"一致
    signal ingestMany(var paths)          // 勾选多个文件夹后批量添加

    property bool _busy: false
    property var _expanded: ({})      // path -> true
    property var _sel: ({})           // 勾选待添加的文件夹 path -> true
    property int _selCount: 0

    function toggleSelect(path) {
        var n = normalize(path)
        var m = {}
        for (var k in root._sel) m[k] = true
        if (m[n]) {
            delete m[n]
        } else {
            m[n] = true
        }
        /* 必须整体重新赋值触发 var 属性变更通知：QML 绑定对 JS 对象的内部修改
           无感知，delegate 的勾选视觉只会在重建时刷新（同 FolderPickerDialog）。 */
        root._sel = m
        root._selCount = 0
        for (var k in m) root._selCount++
    }

    function clearSelection() {
        root._sel = {}
        root._selCount = 0
    }

    function selectedPaths() {
        var arr = []
        for (var k in root._sel) arr.push(k)
        return arr
    }

    ListModel { id: treeModel }

    function normalize(p) {
        if (!p) return ""
        return p.replace(/\\/g, "/").replace(/\/+$/, "")
    }

    function depthOf(p) {
        var n = normalize(p)
        if (!n) return 0
        return n.split("/").length
    }

    function refresh() {
        // 保留展开状态，仅刷新数据（入库后自动刷新而不丢失展开层级）
        var keep = {}
        for (var key in _expanded) if (_expanded[key]) keep[key] = true
        treeModel.clear()
        _expanded = keep
        _busy = false
        loadChildren("")
        var keys = []
        for (var k in keep) keys.push(k)
        keys.sort(function (a, b) { return a.split("/").length - b.split("/").length })
        for (var i = 0; i < keys.length; ++i) {
            var pi = findIndex(keys[i])
            if (pi < 0) continue
            var row = treeModel.get(pi)
            if (row.hasChildren) {
                treeModel.set(pi, { expanded: true })
                loadChildren(row.path)
            }
        }
    }

    function loadChildren(dir) {
        if (_busy) return
        _busy = true
        var kids = LibraryBridge.dirChildren(dir)
        _busy = false
        var onlyAdded = root.mode === "added"

        var items = []
        for (var i = 0; i < kids.length; ++i) {
            var k = kids[i]
            if (onlyAdded && !k.added) continue
            var addIdx = root._expanded[normalize(k.path)] === true
            var hasCh = onlyAdded ? k.hasAddedSub : k.hasSub
            items.push({
                name: k.name, path: k.path, photoCount: k.photoCount,
                added: k.added, state: k.state, hasChildren: hasCh,
                expanded: addIdx, depth: depthOf(k.path)
            })
        }
        if (dir === "") {
            for (var j = 0; j < items.length; ++j) treeModel.append(items[j])
        } else {
            insertInto(dir, items)
        }
    }

    function insertInto(parentPath, items) {
        var pi = findIndex(parentPath)
        if (pi < 0) return
        // 找到父节点下最后一个后代的行号（其后插入）
        var anchor = pi
        for (var i = pi + 1; i < treeModel.count; ++i) {
            var row = treeModel.get(i)
            if (row.depth > treeModel.get(pi).depth) anchor = i
            else break
        }
        for (var j = 0; j < items.length; ++j) {
            treeModel.insert(anchor + 1 + j, items[j])
        }
    }

    function findIndex(path) {
        var n = normalize(path)
        for (var i = 0; i < treeModel.count; ++i)
            if (normalize(treeModel.get(i).path) === n) return i
        return -1
    }

    function toggle(path) {
        var n = normalize(path)
        var pi = findIndex(n)
        if (pi < 0) return
        var row = treeModel.get(pi)
        if (!row.hasChildren) {
            root.folderChosen(row.path, row.photoCount)
            return
        }
        if (row.expanded) {
            _expanded[n] = false
            // 移除其后代
            var d = row.depth
            var removeFrom = pi + 1
            var removeCount = 0
            for (var i = pi + 1; i < treeModel.count; ++i) {
                if (treeModel.get(i).depth > d) removeCount++
                else break
            }
            for (var r = 0; r < removeCount; ++r) treeModel.remove(removeFrom)
            treeModel.set(pi, { expanded: false })
        } else {
            _expanded[n] = true
            treeModel.set(pi, { expanded: true })
            loadChildren(path)
        }
        // 点击文件夹即加载其中照片（与系统浏览器行为一致）
        root.folderChosen(row.path, row.photoCount)
    }

    /* 三态复选框（0 空白 / 1 部分 / 2 全选，微软经典样式）；勾选表示纳入批量添加 */
    component TriCheck: Rectangle {
        property int checkState: 0
        property bool selected: false
        property string path: ""
        width: 14
        height: 14
        radius: 3
        border.width: 1
        border.color: (checkState === 0 && !selected) ? Theme.divider : Theme.primary
        color: checkState === 0 ? (selected ? Theme.primary : "transparent")
               : checkState === 2 ? Theme.primary
               : Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.18)

        Text {                // 全选勾
            visible: checkState === 2 || selected
            text: "✓"
            color: Theme.textOnPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 10
            font.bold: true
            anchors.centerIn: parent
        }
        Rectangle {           // 部分横线
            visible: checkState === 1 && !selected
            width: 8
            height: 2
            radius: 1
            color: Theme.primary
            anchors.centerIn: parent
        }
        MouseArea {           // 点击复选框：切换批量选择（不进入子文件夹）
            anchors.fill: parent
            anchors.margins: -4
            onClicked: root.toggleSelect(path)
        }
    }

    Connections {
        target: LibraryBridge
        function onPhotosChanged() {
            root.refresh()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 10
            Layout.rightMargin: 10
            Layout.bottomMargin: 4
            spacing: 4

            Rectangle {
                id: addedBtn
                objectName: "treeModeAdded"
                Layout.fillWidth: true
                Layout.preferredHeight: 22
                radius: 11
                color: root.mode === "added" ? Theme.primary : Theme.surfaceAlt
                Text {
                    anchors.centerIn: parent
                    text: I18n.tr("仅已添加")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: root.mode === "added" ? Theme.textOnPrimary : Theme.textDim
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (root.mode !== "added") { root.mode = "added"; root.refresh() }
                    }
                }
            }
            Rectangle {
                id: allBtn
                objectName: "treeModeAll"
                Layout.fillWidth: true
                Layout.preferredHeight: 22
                radius: 11
                color: root.mode === "all" ? Theme.primary : Theme.surfaceAlt
                Text {
                    anchors.centerIn: parent
                    text: I18n.tr("全部")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: root.mode === "all" ? Theme.textOnPrimary : Theme.textDim
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (root.mode !== "all") { root.mode = "all"; root.refresh() }
                    }
                }
            }
        }

        ListView {
            id: treeList
            objectName: "folderTreeList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: treeModel
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

            delegate: Rectangle {
                id: row
                property int photoCount: model.photoCount
                property int checkState: model.state
                property bool added: model.added
                property string fpath: model.path
                property bool isSel: root._sel[normalize(model.path)] === true
                width: treeList.width
                height: 30

                /* 行点击区置于底部（先声明），确保右侧"添加到图库"按钮可接收点击 */
                MouseArea {
                    id: rowArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.toggle(model.path)
                }

                color: root._expanded[normalize(model.path)] === true || row.isSel
                       ? Theme.hover
                       : (rowArea.hovered ? Qt.rgba(Theme.hover.r, Theme.hover.g, Theme.hover.b, 0.5) : "transparent")

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8 + (model.depth - 1) * 14
                    anchors.rightMargin: 8
                    spacing: 5

                    TriCheck {
                        checkState: model.state
                        selected: row.isSel
                        path: model.path
                    }
                    Text {
                        width: 12
                        text: model.hasChildren ? (model.expanded ? "▾" : "▸") : "•"
                        font.pixelSize: 11
                        color: Theme.textDim
                    }
                    Text {
                        Layout.fillWidth: true
                        text: model.name
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: model.added ? Font.DemiBold : Font.Normal
                        color: model.added ? Theme.text : Theme.textDim
                        opacity: model.added ? 1 : 0.45
                        elide: Text.ElideRight
                    }
                    Text {
                        visible: model.photoCount > 0
                        text: model.photoCount
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        color: Theme.textDim
                    }

                    Rectangle {
                        id: addBtn
                        objectName: "treeAddBtn"
                        Layout.preferredWidth: 68
                        Layout.preferredHeight: 20
                        visible: root.mode === "all"
                        radius: 10
                        color: addHover.hovered ? Theme.primaryDark : Theme.primary
                        Text {
                            anchors.centerIn: parent
                            text: I18n.tr("添加到图库")
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                            color: Theme.textOnPrimary
                        }
                        MouseArea {
                            id: addHover
                            objectName: "treeAddBtnArea"
                            property string tooltipText: I18n.tr("将整个文件夹下的图片（含子文件夹）添加到图库")
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: ToolTip.show(tooltipText, 2000)
                            onExited: ToolTip.hide()
                            onClicked: root.ingestRequested(model.path)
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: treeModel.count === 0
                text: root.mode === "added" ? I18n.tr("（尚未添加照片文件夹）") : I18n.tr("（无文件夹）")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
        }

        /* 批量添加栏：勾选多个文件夹后出现 */
        Rectangle {
            id: bulkBar
            objectName: "treeBulkBar"
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            visible: root._selCount > 0
            color: Theme.bg
            border.width: 1
            border.color: Theme.divider

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: I18n.tr("已选 ") + root._selCount + I18n.tr(" 个文件夹")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.text
                }
                Rectangle {
                    id: bulkAddBtn
                    objectName: "treeBulkAdd"
                    Layout.preferredWidth: 96
                    Layout.preferredHeight: 24
                    radius: 12
                    color: bulkAddHover.hovered ? Theme.primaryDark : Theme.primary
                    Text {
                        anchors.centerIn: parent
                        text: I18n.tr("添加所选到图库")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textOnPrimary
                    }
                    MouseArea {
                        id: bulkAddHover
                        objectName: "treeBulkAddArea"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.ingestMany(root.selectedPaths())
                            root.clearSelection()
                        }
                    }
                }
            }
        }
    }
}
