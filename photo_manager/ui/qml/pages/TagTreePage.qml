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

/* 层级标签树浏览页（C8 + 进阶）。
   LibraryBridge.tagTree() 返回前序扁平列表（含 depth/photoCount/path），按 depth 缩进即成树。
   - 点击节点 → 按该节点及其子孙浏览照片
   - 拖拽节点到另一节点上 → 移动（含子孙，禁止移到自己的子孙下）
   - 拖到顶部「移到顶层」区域 → 变为一级标签
   - 多选后可「归入…」批量收编到某个父节点下 */
Item {
    id: root

    property string title: I18n.tr("标签")
    property string hint: I18n.tr("拖拽可移动层级；多选后可批量归入某个父节点")
    property var checkedPaths: []
    property bool multiSelect: false
    property string draggingPath: ""

    signal itemClicked(var item)
    signal renameRequested(string path)
    signal mergeRequested(string path)
    signal moveRequested(var paths)

    ListModel { id: itemsModel }

    function refresh() {
        itemsModel.clear()
        var arr = LibraryBridge.tagTree()
        for (var i = 0; i < arr.length; ++i)
            itemsModel.append(arr[i])
        countText.text = arr.length + I18n.tr(" 个节点")
        root.checkedPaths = []
        root.updateBatchBar()
    }

    function toggleCheck(path) {
        /* 0.6.20 修复「多选不能勾选」：var 属性就地 push/splice 不触发绑定更新
           （CategoryPage.toggleSelect 同款教训）——必须整体替换新数组，
           否则勾选框 checked 绑定永不重绘，用户看到的就是勾不上。 */
        var arr = root.checkedPaths.slice()
        var idx = arr.indexOf(path)
        if (idx >= 0) arr.splice(idx, 1)
        else arr.push(path)
        root.checkedPaths = arr
        root.updateBatchBar()
    }

    function updateBatchBar() {
        /* 0.6.23：改为进多选模式即占位（常驻），不再「勾选后才插入一行」——
           动态插入会把下方列表整体顶下去（用户感知为顶部多出一行、行错位叠加） */
        batchBar.visible = root.multiSelect
    }

    function enterMulti() {
        root.multiSelect = !root.multiSelect
        if (!root.multiSelect) root.checkedPaths = []
        root.updateBatchBar()
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
                id: titleText
                text: root.title
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
            Item { Layout.fillWidth: true; width: 10 }
            PMButton {
                objectName: "tagMultiBtn"
                tooltip: I18n.tr("进入/退出多选模式，勾选多个标签节点批量移动")
                text: root.multiSelect ? I18n.tr("退出多选") : I18n.tr("多选")
                width: 72
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                onClicked: root.enterMulti()
            }
            Text {
                text: root.hint
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                elide: Text.ElideRight
            }
        }

        /* 多选批量条：选中节点后可「归入…」某个父节点。
           0.6.23：外层 Row→RowLayout——positioner 里 Layout.fillHeight 无效，
           内层 Rectangle 高度 0、内容溢出叠加到下方首行「场景」上（用户反馈） */
        RowLayout {
            id: batchBar
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            /* 0.6.23：上限锁 40——内层 fillHeight 会把整行撑到数百像素 */
            Layout.maximumHeight: 40
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            visible: false
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radiusMedium
                color: Theme.surface
                border.width: 1
                border.color: Theme.primary
                Row {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingMedium
                    anchors.rightMargin: Theme.spacingMedium
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("已选 ") + root.checkedPaths.length + I18n.tr(" 个标签")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                    }
                    Item { Layout.fillWidth: true; width: 10 }
                    PMButton {
                        objectName: "tagMoveBtn"
                        tooltip: I18n.tr("把所选标签移到指定父标签下")
                        text: I18n.tr("归入…")
                        height: 26
                        enabled: root.checkedPaths.length > 0
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: root.moveRequested(root.checkedPaths.concat(["__pick__"]))
                    }
                    PMButton {
                        objectName: "tagMoveTopBtn"
                        tooltip: I18n.tr("把所选标签移到顶层（取消父级）")
                        text: I18n.tr("移到顶层")
                        height: 26
                        enabled: root.checkedPaths.length > 0
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: root.moveRequested(root.checkedPaths.concat(["__top__"]))
                    }
                    PMButton {
                        objectName: "tagClearBtn"
                        tooltip: I18n.tr("删除所选标签（仅移除标签记录，照片文件不动）")
                        text: I18n.tr("取消")
                        width: 64
                        height: 26
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: { root.checkedPaths = []; root.updateBatchBar() }
                    }
                }
            }
        }

        /* 拖到此处 = 移到顶层。
           0.6.20：固定占位（visible 恒真）——此前仅拖拽时插入行，
           ColumnLayout 整体下移 34px，用户按下瞬间标签行位置突变，
           看不出点中了哪个（麒麟真机反馈）。非拖拽时半透明弱化。 */
        Rectangle {
            id: topDrop
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            radius: Theme.radiusSmall
            opacity: root.draggingPath !== "" ? 1.0 : 0.45
            color: topDropArea.containsDrag ? Theme.hover : Theme.surfaceAlt
            border.width: 1
            border.color: topDropArea.containsDrag ? Theme.primary : Theme.divider
            Text {
                anchors.centerIn: parent
                text: I18n.tr("拖到此处 → 变为一级标签（移到顶层）")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: root.draggingPath !== "" ? Theme.text : Theme.textDim
            }
            DropArea {
                id: topDropArea
                anchors.fill: parent
                keys: ["tagpath"]
                onDropped: (drop) => {
                    if (drop.source && drop.source.tagPath !== undefined)
                        root.moveRequested([drop.source.tagPath, "__top__"])
                    root.draggingPath = ""
                }
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

            ListView {
                id: listView
                objectName: "categoryList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingTiny
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                model: itemsModel

                delegate: Rectangle {
                    id: rowItem
                    width: listView.width
                    height: 48
                    radius: Theme.radiusMedium
                    color: dropArea.containsDrag ? Theme.hover
                         : (listView.currentIndex === index ? Theme.hover : "transparent")

                    // 拖拽源：整行可拖。Drag.source 必须是 QObject，
                    // 因此把路径挂在 rowItem 的 tagPath 属性上（不能直接赋 QString）。
                    property string tagPath: model.path || ""
                    Drag.active: rowMouse.drag.active
                    Drag.keys: ["tagpath"]
                    Drag.source: rowItem

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium + (model.depth || 0) * 18
                        /* 0.6.21：右侧常驻「重命名/合并」按钮约 180px，行内容
                           此前直接被盖住；非多选时留出按钮宽度，多选时按钮
                           隐藏、空间还给内容（同时消除多选勾选重叠错位） */
                        anchors.rightMargin: root.multiSelect
                            ? Theme.spacingMedium : 190
                        spacing: Theme.spacingSmall

                        Rectangle {
                            width: 18
                            height: 18
                            radius: 4
                            visible: root.multiSelect
                            color: root.checkedPaths.indexOf(model.path) >= 0 ? Theme.primary : Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                            Text {
                                anchors.centerIn: parent
                                visible: root.checkedPaths.indexOf(model.path) >= 0
                                text: "√"
                                font.pixelSize: 12
                                color: Theme.textOnPrimary
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.toggleCheck(model.path)
                            }
                        }

                        Text {
                            text: "≡"
                            font.pixelSize: 14
                            color: Theme.textDim
                        }
                        Rectangle {
                            width: 30
                            height: 30
                            radius: Theme.radiusMedium
                            color: Theme.surfaceAlt
                            Text {
                                anchors.centerIn: parent
                                text: "#"
                                font.pixelSize: 15
                            }
                        }
                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: model.name
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideRight
                                width: parent.width
                            }
                            Text {
                                visible: (model.depth || 0) > 0
                                text: model.path
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.textDim
                                elide: Text.ElideRight
                                width: parent.width
                            }
                        }
                        Text {
                            text: model.photoCount + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        /* 0.5.63 修复「点标签无反应」：drag.target 下轻微鼠标
                           抖动（<8px）即激活拖拽，onClicked 不再触发——点击被吞。
                           改为在 onReleased 里按位移判定：小于 8px 视为点击
                           （拖拽仍需明显移动才生效，排序功能不受影响）。 */
                        property real _pressX: 0
                        property real _pressY: 0
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        drag.target: rowItem
                        onPressed: (mouse) => {
                            _pressX = mouse.x
                            _pressY = mouse.y
                            root.draggingPath = model.path
                        }
                        onReleased: (mouse) => {
                            var dx = mouse.x - _pressX
                            var dy = mouse.y - _pressY
                            var dist = Math.sqrt(dx * dx + dy * dy)
                            rowItem.Drag.drop()
                            // 复位拖动产生的位移（ListView 布局不受影响）
                            rowItem.x = 0
                            rowItem.y = 0
                            root.draggingPath = ""
                            if (dist < 8) {
                                if (root.multiSelect) {
                                    root.toggleCheck(model.path)
                                    return
                                }
                                listView.currentIndex = index
                                root.itemClicked({ name: model.path, path: model.path })
                            }
                        }
                    }

                    /* 放到本行 = 成为本节点的子节点 */
                    DropArea {
                        id: dropArea
                        anchors.fill: parent
                        keys: ["tagpath"]
                        onDropped: (drop) => {
                            if (drop.source && drop.source.tagPath !== undefined)
                                root.moveRequested([drop.source.tagPath, model.path])
                            root.draggingPath = ""
                        }
                    }

                    Row {
                        id: actionButtons
                        /* 0.6.21：多选模式下隐藏（勾选框出现后与行内容重叠
                           错位的来源之一；批量操作走顶部批量栏） */
                        visible: !root.multiSelect
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.spacingSmall
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        z: 2

                        PMButton {
                            objectName: "tagRenameBtn"
                            tooltip: I18n.tr("重命名标签")
                            text: I18n.tr("≡ 重命名")
                            width: 92
                            height: 28
                            onClicked: root.renameRequested(model.path)
                        }
                        PMButton {
                            objectName: "tagMergeBtn"
                            tooltip: I18n.tr("把该标签并入另一个标签")
                            text: I18n.tr("＋ 合并")
                            width: 76
                            height: 28
                            onClicked: root.mergeRequested(model.path)
                        }
                    }

                    /* 0.6.22：行间分隔线（用户反馈：行与行边界不明显） */
                    Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.spacingMedium
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Theme.divider
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: itemsModel.count === 0
                    text: I18n.tr("暂无标签（先在信息面板给照片打标签，用 / 分隔层级，如 旅行/北京）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }
        }
    }
}
