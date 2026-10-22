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

/* 分类浏览页：人物 / 地点 / 设备 共用。
   kind: "people" | "locations" | "devices"，由 LibraryBridge 对应方法取数。 */
Item {
    id: root

    property string kind: "people"
    property string title: I18n.tr("分类")
    property string hint: ""

    signal itemClicked(var item)
    signal renameRequested(int personId, string name)
    signal mergeRequested(int personId, string name)
    signal batchMergeRequested(var ids)

    ListModel { id: itemsModel }
    property var selectedIds: []
    property bool _batchMode: false
    /* 0.5.36：列表排序（0=数量多→少，后端默认序；1=名称 A→Z） */
    property int sortMode: 0

    function _sortedArr(arr) {
        if (root.sortMode === 1)
            return arr.slice().sort(function (a, b) {
                return String(a.name || a.cameraModel || "").localeCompare(
                       String(b.name || b.cameraModel || ""), "zh")
            })
        return arr
    }

    function toggleSelect(id) {
        /* QML 属性 var 的就地修改（push/splice）不触发绑定更新（0.5.x 教训，
           FolderPickerDialog 同款）——必须整体替换新数组，勾选框才会重绘 */
        var arr = selectedIds.slice()
        var idx = arr.indexOf(id)
            if (idx >= 0) arr.splice(idx, 1)
        else arr.push(id)
        selectedIds = arr
        updateBatchBar()
    }

    function updateBatchBar() {
        /* 0.5.41：批量条在「多选模式」下常驻占位（保留 40px 高度），
           避免勾选第二个头像时列表突然下跳、上方空出一行 */
        batchBar.visible = root._batchMode
    }

    function enterBatch() {
        _batchMode = !_batchMode
        if (!_batchMode) selectedIds = []
        updateBatchBar()
    }

    function refresh() {
        itemsModel.clear()
        var arr = LibraryBridge.people()
        if (kind === "locations")
            arr = LibraryBridge.locations()
        else if (kind === "devices")
            arr = LibraryBridge.devices()
        else if (kind === "tags")
            arr = LibraryBridge.tags()
        arr = root._sortedArr(arr)
        for (var i = 0; i < arr.length; ++i) {
            var it = arr[i]
            if (it.lat === undefined) it.lat = 0
            if (it.lon === undefined) it.lon = 0
            itemsModel.append(it)
        }
        countText.text = arr.length + I18n.tr(" 项")
    }

    function _icon() {
        if (kind === "people") return "👤"
        if (kind === "locations") return "📍"
        if (kind === "tags") return "#"
        return "📷"
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
                objectName: "categorySortBtn"
                tooltip: I18n.tr("切换列表排序方式（数量/名称）")
                text: I18n.tr("排序 ▾")
                height: 30
                Menu {
                    id: categorySortMenu
                    MenuItem { text: I18n.tr("按数量（多→少）"); checkable: true; checked: root.sortMode === 0
                               onTriggered: { root.sortMode = 0; root.refresh() } }
                    MenuItem { text: I18n.tr("按名称（A→Z）"); checkable: true; checked: root.sortMode === 1
                               onTriggered: { root.sortMode = 1; root.refresh() } }
                }
                onClicked: categorySortMenu.popup(this, 0, height + 2)
            }
            PMButton {
                objectName: "categoryBatchBtn"
                tooltip: I18n.tr("进入/退出多选模式，可勾选多个人物批量合并")
                text: _batchMode ? I18n.tr("退出多选") : I18n.tr("多选")
                width: 72
                height: 30
                visible: kind === "people"
                anchors.verticalCenter: parent.verticalCenter
                onClicked: root.enterBatch()
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

        /* 批量合并条：进入多选模式后常驻占位（0.5.41），避免勾选第二个头像时列表跳动 */
        Row {
            id: batchBar
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            visible: root._batchMode
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
                    visible: root.selectedIds.length >= 2
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("已选 ") + root.selectedIds.length + I18n.tr(" 个人物")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                    }
                    Item { Layout.fillWidth: true; width: 10 }
                    PMButton {
                        objectName: "categoryBatchMergeBtn"
                        tooltip: I18n.tr("把勾选的人物合并到第一个（照片归属一并转移）")
                        text: I18n.tr("合并选中（") + root.selectedIds.length + I18n.tr(" 个）")
                        height: 26
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: root.batchMergeRequested(root.selectedIds)
                    }
                    PMButton {
                        objectName: "categoryBatchClearBtn"
                        tooltip: I18n.tr("清空多选勾选")
                        text: I18n.tr("取消")
                        width: 64
                        height: 26
                        anchors.verticalCenter: parent.verticalCenter
                        onClicked: { root.selectedIds = []; root.updateBatchBar() }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: root.selectedIds.length < 2
                    text: I18n.tr("勾选两个以上人物，可批量合并 / 转移")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
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
                    visible: kind !== "people"
                    anchors.fill: parent
                    anchors.margins: Theme.spacingSmall
                    spacing: Theme.spacingTiny
                    clip: true
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                    model: itemsModel

                delegate: Rectangle {
                    width: listView.width
                    height: 52
                    radius: Theme.radiusMedium
                    color: listView.currentIndex === index ? Theme.hover : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.rightMargin: Theme.spacingMedium
                        spacing: Theme.spacingMedium

                        Rectangle {
                            width: 18
                            height: 18
                            radius: 4
                            visible: root._batchMode && kind === "people"
                            color: root.selectedIds.indexOf(model.id) >= 0 ? Theme.primary : Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                            Text {
                                anchors.centerIn: parent
                                visible: root.selectedIds.indexOf(model.id) >= 0
                                text: "✓"
                                font.pixelSize: 12
                                color: Theme.textOnPrimary
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.toggleSelect(model.id)
                            }
                        }

                        Rectangle {
                            width: 34
                            height: 34
                            radius: Theme.radiusMedium
                            color: Theme.surfaceAlt
                            clip: true
                            /* 0.5.28：人物行显示真实人像（bridge 给出缩略图+像素裁剪框，
                               Image.sourceRect 裁出人脸），便于按长相命名 */
                            property bool hasAvatar: kind === "people"
                                                     && typeof model.avatarW !== "undefined"
                                                     && model.avatarW > 0
                                                     && !!model.avatarSrc
                            Image {
                                anchors.fill: parent
                                visible: parent.hasAvatar
                                source: parent.hasAvatar
                                        ? "file:///" + String(model.avatarSrc).replace(/\\/g, "/") : ""
                                sourceClipRect: Qt.rect(model.avatarX || 0, model.avatarY || 0,
                                                        model.avatarW || 1, model.avatarH || 1)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: !parent.hasAvatar
                                text: root._icon()
                                font.pixelSize: 16
                            }
                        }
                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: kind === "devices" ? (model.name || model.cameraModel) : model.name
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideRight
                                width: parent.width
                            }
                            Text {
                                visible: kind === "locations" && (model.lat || 0) !== 0
                                text: "GPS " + (model.lat || 0).toFixed(3) + ", " + (model.lon || 0).toFixed(3)
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.textDim
                            }
                            Text {
                                visible: kind === "devices"
                                text: model.make || ""
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.textDim
                            }
                            /* 0.5.37：人物平均人脸模糊指数（0-100，越大越模糊） */
                            Text {
                                visible: kind === "people"
                                         && typeof model.blurIdx !== "undefined"
                                         && model.blurIdx >= 0
                                text: I18n.tr("模糊指数 ") + model.blurIdx
                                      + (model.blurIdx >= 70 ? I18n.tr("（建议清理）") : "")
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: model.blurIdx >= 70 ? Theme.danger : Theme.textDim
                            }
                        }
                        Text {
                            text: model.photoCount + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                            Layout.rightMargin: (kind === "people" || kind === "tags") ? 200 : 0
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root._batchMode && kind === "people") {
                                root.toggleSelect(model.id)
                                return
                            }
                            listView.currentIndex = index
                            root.itemClicked({
                                name: model.name,
                                id: model.id,
                                lat: model.lat,
                                lon: model.lon,
                                cameraModel: model.cameraModel
                            })
                        }
                    }

                    Row {
                        id: actionButtons
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.spacingSmall
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        visible: kind === "people" || kind === "tags"
                        z: 2

                        PMButton {
                            objectName: "personRenameBtn"
                            tooltip: I18n.tr("给该人物起名（显示名，不影响文件）")
                            text: I18n.tr("✎ 重命名")
                            width: 92
                            height: 28
                            visible: kind === "people" && (model.id || 0) > 0
                            onClicked: root.renameRequested(model.id, model.name)
                        }
                        PMButton {
                            objectName: "tagRenameBtn"
                            tooltip: I18n.tr("重命名标签（含子标签层级路径）")
                            text: I18n.tr("✎ 重命名")
                            width: 92
                            height: 28
                            visible: kind === "tags"
                            onClicked: root.renameRequested(0, model.name)
                        }
                        PMButton {
                            objectName: "personMergeBtn"
                            tooltip: I18n.tr("把该人物并入另一人物（同一个人被识别成两个簇时用）")
                            text: I18n.tr("⊕ 合并")
                            width: 76
                            height: 28
                            visible: kind === "people" && (model.id || 0) > 0
                            onClicked: root.mergeRequested(model.id, model.name)
                        }
                        PMButton {
                            objectName: "tagMergeBtn"
                            tooltip: I18n.tr("把该标签并入另一个标签（照片标签记录一并转移）")
                            text: I18n.tr("⊕ 合并")
                            width: 76
                            height: 28
                            visible: kind === "tags"
                            onClicked: root.mergeRequested(0, model.name)
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: itemsModel.count === 0
                    text: I18n.tr("暂无数据（先扫描照片并运行分析）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }

            /* 人物视图：网格排列（0.5.41），参考全部照片缩略图网格，头像更大更直观 */
            GridView {
                id: gridView
                objectName: "categoryGrid"
                visible: kind === "people"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                cellWidth: 124
                cellHeight: 152
                currentIndex: -1
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: itemsModel

                delegate: Rectangle {
                    width: gridView.cellWidth
                    height: gridView.cellHeight
                    color: gridView.currentIndex === index ? Theme.hover : "transparent"
                    radius: Theme.radiusMedium

                    Rectangle {
                        id: gAvatar
                        width: 86; height: 86
                        radius: 43
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 10
                        color: Theme.surfaceAlt
                        clip: true
                        property bool hasAvatar: typeof model.avatarW !== "undefined"
                                                 && model.avatarW > 0 && !!model.avatarSrc
                        Image {
                            anchors.fill: parent
                            visible: parent.hasAvatar
                            source: parent.hasAvatar
                                    ? "file:///" + String(model.avatarSrc).replace(/\\/g, "/") : ""
                            sourceClipRect: Qt.rect(model.avatarX || 0, model.avatarY || 0,
                                                    model.avatarW || 1, model.avatarH || 1)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !parent.hasAvatar
                            text: "👤"
                            font.pixelSize: 34
                        }
                        /* 多选勾选框（左上角） */
                        Rectangle {
                            visible: root._batchMode
                            width: 22; height: 22; radius: 6
                            anchors.top: parent.top; anchors.left: parent.left
                            anchors.margins: 5
                            color: root.selectedIds.indexOf(model.id) >= 0 ? Theme.primary : Theme.surface
                            border.width: 1; border.color: Theme.divider
                            Text {
                                anchors.centerIn: parent
                                visible: root.selectedIds.indexOf(model.id) >= 0
                                text: "✓"; font.pixelSize: 13; color: Theme.textOnPrimary
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.toggleSelect(model.id)
                            }
                        }
                        /* 严重模糊徽标（右上角） */
                        Rectangle {
                            visible: typeof model.blurIdx !== "undefined" && model.blurIdx >= 70
                            width: 16; height: 16; radius: 8
                            anchors.top: parent.top; anchors.right: parent.right
                            anchors.margins: 5
                            color: Theme.danger
                        }
                    }

                    Text {
                        id: gName
                        anchors.top: gAvatar.bottom
                        anchors.topMargin: 6
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width - 12
                        horizontalAlignment: Text.AlignHCenter
                        text: model.name || (I18n.tr("人物 #") + model.id)
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: Theme.text
                        elide: Text.ElideMiddle
                    }
                    Text {
                        anchors.top: gName.bottom
                        anchors.topMargin: 2
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: model.photoCount + I18n.tr(" 张")
                              + (typeof model.blurIdx !== "undefined" && model.blurIdx >= 0
                                 ? I18n.tr(" · 糊") + model.blurIdx : "")
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        color: (typeof model.blurIdx !== "undefined" && model.blurIdx >= 70)
                               ? Theme.danger : Theme.textDim
                    }

                    MouseArea {
                        id: gma
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root._batchMode) { root.toggleSelect(model.id); return }
                            gridView.currentIndex = index
                            root.itemClicked({
                                name: model.name, id: model.id,
                                lat: model.lat, lon: model.lon, cameraModel: model.cameraModel
                            })
                        }
                    }
                    /* 悬停操作：重命名 / 合并（卡片底部，不遮挡头像点击区）
                       0.5.63 修复「点人物无反应」：原实现按钮锚定头像中央且默认
                       接收悬停事件——按钮出现时从 gma 抢走悬停态 →
                       containsMouse=false → 按钮消失 → gma 得回悬停 → 按钮又出现，
                       形成闪烁环；用户点击在闪烁周期中按下/释放落在不同元素上，
                       点击事件被吞。修复：① 按钮移到底部（头像点击区始终可导航）
                       ② hoverEnabled:false（按钮不再抢悬停，彻底消除闪烁） */
                    Row {
                        id: gActions
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 2
                        spacing: 4
                        visible: gma.containsMouse && (model.id || 0) > 0
                        z: 3
                        PMButton {
                            objectName: "personRenameBtn"
                            text: I18n.tr("重命名"); width: 60; height: 20
                            hoverEnabled: false
                            onClicked: root.renameRequested(model.id, model.name)
                        }
                        PMButton {
                            objectName: "personMergeBtn"
                            text: I18n.tr("合并"); width: 48; height: 20
                            hoverEnabled: false
                            onClicked: root.mergeRequested(model.id, model.name)
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: itemsModel.count === 0
                text: I18n.tr("暂无数据（先扫描照片并运行分析）")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
            }
        }
    }
}
