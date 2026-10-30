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

/* 人物头像批量管理（0.5.67）：列出某人物的全部人脸，多选后
   归为新人物 / 并入其他人物 —— 解决聚类误并后"拆不开"的问题。
   红线：只动 faces.person_id 标签，绝不触碰照片文件。 */
Dialog {
    id: root
    objectName: "personFacesDialog"

    signal messageRequested(string msg, string kind)

    modal: true
    width: Math.min(parent ? parent.width - 60 : 860, 840)
    height: Math.min(parent ? parent.height - 60 : 640, 620)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    property int personId: 0
    property string personName: ""
    /* 0.5.52 同款：勾选集合整体替换触发绑定，禁止 push/splice */
    property var checkedFaceIds: []
    /* 剔除人脸的二次确认态（须显式声明：动态属性不触发绑定更新，
       确认文案不会变化——曾被误报"点击无效"） */
    property bool confirmPurge: false

    function openFor(pid) {
        root.personId = pid
        root.personName = ""
        var ppl = LibraryBridge.people()
        for (var i = 0; i < ppl.length; ++i)
            if (ppl[i].id === pid) { root.personName = ppl[i].name || ""; break }
        root.open()
    }

    function refresh() {
        var arr = LibraryBridge.personFaceList(root.personId)
        faceModel.clear()
        for (var i = 0; i < arr.length; ++i)
            faceModel.append(arr[i])
        /* 口径说明：同一张照片可能含多张该人物的人脸，因此"人脸数"会大于
           "照片数"（用户反馈误解点），两个数都明示 */
        var photos = {}
        for (var p = 0; p < arr.length; ++p)
            photos[arr[p].photoId] = true
        countText.text = I18n.tr("共 ") + arr.length + I18n.tr(" 张人脸 · 来自 ")
                         + Object.keys(photos).length + I18n.tr(" 张照片")
        /* 刷新后清理无效勾选 */
        var present = {}
        for (var j = 0; j < faceModel.count; ++j)
            present[faceModel.get(j).faceId] = true
        var keep = []
        for (var k = 0; k < checkedFaceIds.length; ++k)
            if (present[checkedFaceIds[k]]) keep.push(checkedFaceIds[k])
        checkedFaceIds = keep
    }

    function selectAllFaces() {
        var arr = []
        for (var i = 0; i < faceModel.count; ++i)
            arr.push(faceModel.get(i).faceId)
        checkedFaceIds = arr
    }
    function invertFaceSelection() {
        var arr = []
        for (var i = 0; i < faceModel.count; ++i) {
            var fid = faceModel.get(i).faceId
            if (checkedFaceIds.indexOf(fid) < 0) arr.push(fid)
        }
        checkedFaceIds = arr
    }
    function toggleFaceChecked(faceId) {
        var arr = checkedFaceIds.slice()
        var i = arr.indexOf(faceId)
        if (i >= 0) arr.splice(i, 1)
        else arr.push(faceId)
        checkedFaceIds = arr
    }

    onOpened: { checkedFaceIds = []; refresh() }

    ListModel { id: faceModel }
    ListModel { id: targetModel }

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.width: 1
        border.color: Theme.divider
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 44 }
            Text {
                Layout.alignment: Qt.AlignVCenter
                text: (root.personName || I18n.tr("未命名人物")) + I18n.tr(" · 管理头像")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideRight
                Layout.maximumWidth: 320
            }
            Text {
                id: countText
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                elide: Text.ElideRight
            }
            PMButton {
                text: I18n.tr("关闭")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                onClicked: root.close()
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            text: I18n.tr("勾选要拆分出去的人脸，归为新人物或并入其他人物（只改归属标签，照片不受影响）")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
            wrapMode: Text.Wrap
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            color: Theme.bg
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider

            GridView {
                id: faceGrid
                objectName: "personFaceGrid"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                cellWidth: 96
                cellHeight: 116
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                model: faceModel

                delegate: Item {
                    width: faceGrid.cellWidth
                    height: faceGrid.cellHeight

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: Theme.radiusSmall
                        color: root.checkedFaceIds.indexOf(model.faceId) >= 0
                               ? Theme.surfaceAlt : Theme.surface
                        border.width: root.checkedFaceIds.indexOf(model.faceId) >= 0 ? 2 : 1
                        border.color: root.checkedFaceIds.indexOf(model.faceId) >= 0
                                      ? Theme.primary : Theme.divider

                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.toggleFaceChecked(model.faceId)
                        }

                        Item {
                            id: avBox
                            width: 72
                            height: 72
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 4
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: model.avatarSrc
                                        ? "file:///" + String(model.avatarSrc).replace(/\\/g, "/") : ""
                                sourceClipRect: Qt.rect(model.avatarX || 0, model.avatarY || 0,
                                                        model.avatarW || 1, model.avatarH || 1)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: false
                            }
                            Rectangle {
                                visible: root.checkedFaceIds.indexOf(model.faceId) >= 0
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 3
                                width: 18
                                height: 18
                                radius: 9
                                color: Theme.primary
                                border.width: 2
                                border.color: "white"
                                Text {
                                    anchors.centerIn: parent
                                    text: "✓"
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    color: "white"
                                }
                            }
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 3
                            width: parent.width - 8
                            text: model.name || (I18n.tr("照片 #") + model.photoId)
                            font.family: Theme.fontFamily
                            font.pixelSize: 9
                            color: Theme.textDim
                            elide: Text.ElideMiddle
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: faceModel.count === 0
                    text: I18n.tr("该人物暂无人脸")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            Text {
                Layout.alignment: Qt.AlignVCenter
                Layout.maximumWidth: parent.width * 0.4
                text: root.checkedFaceIds.length > 0
                      ? I18n.tr("已选 ") + root.checkedFaceIds.length + I18n.tr(" 张")
                      : I18n.tr("未选择")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                elide: Text.ElideRight
            }
            PMButton {
                text: I18n.tr("全选")
                height: 28
                enabled: faceModel.count > 0
                onClicked: root.selectAllFaces()
            }
            PMButton {
                text: I18n.tr("反选")
                height: 28
                enabled: faceModel.count > 0
                onClicked: root.invertFaceSelection()
            }
            Item { Layout.fillWidth: true }
            PMButton {
                objectName: "personFaceNewBtn"
                text: I18n.tr("归为新人物")
                height: 30
                enabled: root.checkedFaceIds.length > 0
                onClicked: {
                    var n = LibraryBridge.moveFacesToPerson(root.checkedFaceIds, -1, "")
                    if (n > 0) {
                        root.messageRequested(
                            I18n.tr("已归为新人物（") + n + I18n.tr(" 张），可在人物列表重命名"), "success")
                        root.checkedFaceIds = []
                        root.refresh()
                    } else {
                        root.messageRequested(I18n.tr("归为新人物失败"), "warning")
                    }
                }
            }
            PMButton {
                objectName: "personFaceMergeBtn"
                text: I18n.tr("并入其他人物…")
                height: 30
                enabled: root.checkedFaceIds.length > 0
                onClicked: {
                    picker.rebuildTarget()
                    if (targetModel.count === 0) {
                        root.messageRequested(I18n.tr("没有可并入的其他人物"), "warning")
                        return
                    }
                    picker.open()
                }
            }
            /* 0.5.67：剔除误检的"非人脸"（同 FaceCleanDialog 删除标签：
               仅删 faces 行，照片绝不受影响），两次点击确认 */
            PMButton {
                id: purgeFacesBtn
                objectName: "personFaceDismissBtn"
                text: root.confirmPurge
                      ? I18n.tr("确认剔除所选（") + root.checkedFaceIds.length + I18n.tr("）？")
                      : I18n.tr("剔除所选人脸")
                height: 30
                enabled: root.checkedFaceIds.length > 0
                emphasized: root.confirmPurge
                onClicked: {
                    if (!root.confirmPurge) {
                        root.confirmPurge = true
                        purgeReset.restart()
                        return
                    }
                    root.confirmPurge = false
                    purgeReset.stop()
                    var n = 0
                    for (var i = 0; i < root.checkedFaceIds.length; ++i)
                        if (LibraryBridge.dismissFace(root.checkedFaceIds[i])) n++
                    root.messageRequested(
                        I18n.tr("已剔除 ") + n + I18n.tr(" 个人脸标签（重跑人脸识别会重新检出，照片不受影响）"),
                        n > 0 ? "success" : "warning")
                    root.checkedFaceIds = []
                    root.refresh()
                }
            }
            Timer { id: purgeReset; interval: 4000; onTriggered: root.confirmPurge = false }
        }
    }

    /* 目标人物选择器：搜索过滤 + 列表 */
    Popup {
        id: picker
        parent: Overlay.overlay
        width: Math.min(root.width - 80, 420)
        height: Math.min(root.height - 120, 420)
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        modal: true
        padding: 8

        /* 0.6.15：服务器端搜索——peoplePaged(offset,limit,search) 按名过滤，
           7.8 万人物库不再全量加载（原 masterPeople 全量构建同样吃爆内存） */
        function rebuildTarget() {
            targetModel.clear()
            var r = LibraryBridge.peoplePaged(
                0, 200, targetFilter.text.trim())
            for (var i = 0; i < r.items.length; ++i) {
                if (r.items[i].unassigned) continue
                if (r.items[i].id === root.personId) continue
                targetModel.append(r.items[i])
            }
        }

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 6

            /* 0.6.13：标题 + 显式关闭按钮（原弹窗只能 Esc/点外面关闭） */
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: I18n.tr("并入到目标人物")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: Theme.text
                    Layout.fillWidth: true
                }
                PMButton {
                    text: I18n.tr("关闭")
                    height: 26
                    onClicked: picker.close()
                }
            }
            TextField {
                id: targetFilter
                Layout.fillWidth: true
                placeholderText: I18n.tr("搜索人物名…")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                onTextChanged: picker.rebuildTarget()
            }
            ListView {
                id: targetList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                model: targetModel
                delegate: ItemDelegate {
                    required property int index
                    width: targetList.width
                    height: 40
                    highlighted: false
                    contentItem: Row {
                        spacing: 8
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.name || I18n.tr("未命名人物")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.text
                            elide: Text.ElideRight
                            width: targetList.width - 90
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: (model.photoCount || 0) + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    onClicked: {
                        var n = LibraryBridge.moveFacesToPerson(
                            root.checkedFaceIds, model.id, "")
                        picker.close()
                        if (n > 0) {
                            root.messageRequested(
                                I18n.tr("已并入「") + (model.name || I18n.tr("未命名人物"))
                                + I18n.tr("」（") + n + I18n.tr(" 张）"), "success")
                            root.checkedFaceIds = []
                            root.refresh()
                        } else {
                            root.messageRequested(I18n.tr("并入失败"), "warning")
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: targetList.count === 0
                    text: I18n.tr("无匹配人物")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                }
            }
        }
    }
}
