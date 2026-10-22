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

/* 低质量人脸清理（0.5.37）：按模糊指数列出人脸，支持隐藏 / 删除人脸标签。
   红线：只动 faces 记录（隐藏=可逆标记；删除=仅删人脸标签行），
   绝不删除/移动任何照片文件。删除人脸标签与信息面板「忽略」同源（dismissFace）。 */
Dialog {
    id: root
    objectName: "faceCleanDialog"

    signal messageRequested(string msg, string kind)

    modal: true
    width: Math.min(parent ? parent.width - 60 : 800, 780)
    height: Math.min(parent ? parent.height - 60 : 620, 600)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.width: 1
        border.color: Theme.divider
    }

    property real threshold: 60
    property int faceCount: 0
    property bool confirmPurge: false
    /* 0.5.41：列表排序（0=模糊指数高→低；1=照片名；2=人物名） */
    property int sortMode: 0
    /* 0.5.52：多选勾选的 faceId 集合（数组须整体替换以触发绑定，禁止 push/splice） */
    property var checkedFaceIds: []
    /* 删除选中标签的二次确认态（与 confirmPurge 各自独立） */
    property bool confirmPurgeSel: false

    /* 全选/反选作用于当前列表（阈值过滤后的 faceModel） */
    function selectAllFaces() {
        var arr = []
        for (var i = 0; i < faceModel.count; ++i)
            arr.push(faceModel.get(i).faceId)
        checkedFaceIds = arr
    }
    /* 反选：当前列表里未勾选的勾上、已勾选的取消 */
    function invertFaceSelection() {
        var arr = []
        for (var i = 0; i < faceModel.count; ++i) {
            var fid = faceModel.get(i).faceId
            if (checkedFaceIds.indexOf(fid) < 0)
                arr.push(fid)
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

    function refresh() {
        var st = JSON.parse(LibraryBridge.faceBlurStatus())
        statusText.text = I18n.tr("已评分 ") + st.scored + " / " + st.total
                          + (st.unscored > 0 ? I18n.tr("（未评分 ") + st.unscored + "）" : "")
                          + (st.missing > 0 ? I18n.tr(" · 无法评估 ") + st.missing : "")
        var arr = LibraryBridge.blurryFaces(root.threshold)
        if (root.sortMode === 1)
            arr = arr.slice().sort(function (a, b) {
                return String(a.photoId).localeCompare(String(b.photoId), "zh")
            })
        else if (root.sortMode === 2)
            arr = arr.slice().sort(function (a, b) {
                return String(a.personName || a.name || "").localeCompare(
                       String(b.personName || b.name || ""), "zh")
            })
        /* sortMode===0：保持后端 blur DESC 默认序 */
        faceModel.clear()
        for (var i = 0; i < arr.length; ++i)
            faceModel.append(arr[i])
        faceCount = arr.length
        countText.text = I18n.tr("指数 ≥ ") + Math.round(root.threshold) + "：" + arr.length + I18n.tr(" 张人脸")
        /* 列表刷新后清理无效勾选（已隐藏/已删除/被阈值过滤掉的 faceId） */
        var present = {}
        for (var i = 0; i < faceModel.count; ++i)
            present[faceModel.get(i).faceId] = true
        var keep = []
        for (var j = 0; j < checkedFaceIds.length; ++j)
            if (present[checkedFaceIds[j]]) keep.push(checkedFaceIds[j])
        checkedFaceIds = keep
        root.confirmPurge = false
        root.confirmPurgeSel = false
    }

    onOpened: {
        confirmPurge = false
        confirmPurgeSel = false
        checkedFaceIds = []
        refresh()
    }

    ListModel { id: faceModel }
    Timer {
        id: pollTimer
        interval: 1200
        repeat: true
        running: root.visible && LibraryBridge.busyCount() > 0
        onTriggered: {
            if (LibraryBridge.busyCount() === 0) {
                root.refresh()
                running = false
            }
        }
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
                text: I18n.tr("低质量人脸清理")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                id: countText
                Layout.alignment: Qt.AlignVCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true }
            Text {
                id: statusText
                Layout.alignment: Qt.AlignVCenter
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            PMButton {
                objectName: "faceBlurBackfillBtn"
                tooltip: I18n.tr("按「可辨认程度」为全部人脸重算指数（0.5.42 算法：\n归一化高频能量比，与人脸内容、裁剪大小无关；\n清晰脸稳定低分、模糊脸稳定高分，不再误伤清晰脸）")
                text: I18n.tr("重新评分全部")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    LibraryBridge.faceBlurBackfill(true)
                    pollTimer.running = true
                }
            }
            PMButton {
                objectName: "faceSelectAllBtn"
                tooltip: I18n.tr("勾选当前列表中的全部人脸")
                text: I18n.tr("全选")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                enabled: root.faceCount > 0
                onClicked: root.selectAllFaces()
            }
            PMButton {
                objectName: "faceInvertBtn"
                tooltip: I18n.tr("反选：取消已勾选的，勾选列表中其余未勾选的")
                text: I18n.tr("反选")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                enabled: root.faceCount > 0
                onClicked: root.invertFaceSelection()
            }
            PMButton {
                objectName: "faceCleanSortBtn"
                tooltip: I18n.tr("切换列表排序方式")
                text: I18n.tr("排序 ▾")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                Menu {
                    id: faceCleanSortMenu
                    MenuItem { text: I18n.tr("按模糊指数（高→低）"); checkable: true; checked: root.sortMode === 0
                               onTriggered: { root.sortMode = 0; root.refresh() } }
                    MenuItem { text: I18n.tr("按照片名（A→Z）"); checkable: true; checked: root.sortMode === 1
                               onTriggered: { root.sortMode = 1; root.refresh() } }
                    MenuItem { text: I18n.tr("按人物（A→Z）"); checkable: true; checked: root.sortMode === 2
                               onTriggered: { root.sortMode = 2; root.refresh() } }
                }
                onClicked: faceCleanSortMenu.popup(this, 0, height + 2)
            }
            PMButton {
                text: I18n.tr("关闭")
                height: 28
                Layout.alignment: Qt.AlignVCenter
                onClicked: root.close()
            }
        }

        /* 阈值滑条（0.5.64：Row→RowLayout——普通 Row 不收缩子项，
           末尾长提示文本曾把内容撑出弹窗右缘超出窗口宽度） */
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.tr("模糊阈值")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Slider {
                id: thresholdSlider
                anchors.verticalCenter: parent.verticalCenter
                Layout.preferredWidth: 240
                from: 0
                to: 100
                stepSize: 5
                value: root.threshold
                onMoved: {
                    root.threshold = value
                    refreshDebouncer.restart()
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: Math.round(root.threshold) + I18n.tr("（越大越严）")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                Layout.fillWidth: true
                text: I18n.tr("隐藏=列表不再显示（可逆）· 删除标签=仅移除人脸记录，照片绝不受影响")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                elide: Text.ElideRight
            }
        }
        Timer { id: refreshDebouncer; interval: 350; onTriggered: root.refresh() }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            color: Theme.bg
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider

            ListView {
                id: faceList
                objectName: "faceCleanList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: 4
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: faceModel

                delegate: Rectangle {
                    objectName: "faceCleanRow"
                    width: faceList.width
                    height: 64
                    radius: Theme.radiusSmall
                    /* 0.5.52：勾选高亮（checkedFaceIds 整体替换触发重算） */
                    property bool checked: root.checkedFaceIds.indexOf(model.faceId) >= 0
                    color: checked ? Theme.surfaceAlt : Theme.surface
                    border.width: checked ? 1 : 0
                    border.color: Theme.primary

                    /* 整行点击切换勾选（置于底层；右侧按钮各自接收点击） */
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.toggleFaceChecked(model.faceId)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: Theme.spacingMedium

                        /* 勾选指示器 */
                        Rectangle {
                            width: 18
                            height: 18
                            radius: 9
                            color: checked ? Theme.primary : "transparent"
                            border.width: 1
                            border.color: checked ? Theme.primary : Theme.divider
                            Text {
                                anchors.centerIn: parent
                                visible: checked
                                text: "✓"
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "white"
                            }
                        }

                        Item {
                            width: 52
                            height: 52
                            clip: true
                            Image {
                                anchors.fill: parent
                                source: model.avatarSrc ? "file:///" + String(model.avatarSrc).replace(/\\/g, "/") : ""
                                sourceClipRect: Qt.rect(model.avatarX || 0, model.avatarY || 0,
                                                        model.avatarW || 1, model.avatarH || 1)
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                            }
                        }

                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: model.name || (I18n.tr("照片 #") + model.photoId)
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideMiddle
                                width: parent.width
                            }
                            Text {
                                text: (model.personId > 0 ? (model.personName || I18n.tr("未命名人物")) : I18n.tr("未指派"))
                                      + I18n.tr(" · 模糊指数 ") + model.blurIdx
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: model.blurIdx >= 85 ? "#b71c1c" : Theme.textDim
                            }
                        }

                        Rectangle {
                            width: 44
                            height: 22
                            radius: 11
                            color: model.blurIdx >= 85 ? "#b71c1c"
                                 : model.blurIdx >= 70 ? "#e65100" : "#616161"
                            Text {
                                anchors.centerIn: parent
                                text: model.blurIdx
                                font.pixelSize: 11
                                font.weight: Font.Bold
                                color: "white"
                            }
                        }

                        PMButton {
                            objectName: "faceHideBtn"
                            tooltip: I18n.tr("隐藏这张人脸（人物列表不再显示，可逆，照片不受影响）")
                            text: I18n.tr("隐藏")
                            height: 28
                            onClicked: {
                                if (LibraryBridge.setFaceHidden(model.faceId, true)) {
                                    root.refresh()
                                    root.messageRequested(I18n.tr("已隐藏（可逆，照片不受影响）"), "success")
                                }
                            }
                        }
                        PMButton {
                            objectName: "faceDeleteBtn"
                            tooltip: I18n.tr("删除这张人脸标签（照片完全不受影响，重跑人脸识别会重新检出）")
                            text: I18n.tr("删除标签")
                            height: 28
                            onClicked: {
                                if (LibraryBridge.dismissFace(model.faceId)) {
                                    root.refresh()
                                    root.messageRequested(I18n.tr("已删除人脸标签（照片不受影响）"), "success")
                                }
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: faceModel.count === 0
                    text: I18n.tr("该阈值下没有模糊人脸（点「重新评分全部」按新算法重算指数）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                    width: parent.width - 60
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.tr("共 ") + root.faceCount + I18n.tr(" 张达到阈值")
                      + (root.checkedFaceIds.length > 0
                         ? I18n.tr(" · 已勾选 ") + root.checkedFaceIds.length + I18n.tr(" 张") : "")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true; width: 10 }
            PMButton {
                objectName: "faceBatchHideSelBtn"
                tooltip: I18n.tr("把勾选的人脸设为隐藏（可逆，照片不受影响）")
                text: I18n.tr("隐藏选中（") + root.checkedFaceIds.length + "）"
                height: 30
                enabled: root.checkedFaceIds.length > 0
                onClicked: {
                    var n = 0
                    for (var i = 0; i < root.checkedFaceIds.length; ++i)
                        if (LibraryBridge.setFaceHidden(root.checkedFaceIds[i], true)) n++
                    root.messageRequested(I18n.tr("已隐藏 ") + n + I18n.tr(" 张人脸（可逆）"),
                               n > 0 ? "success" : "warning")
                    root.refresh()
                }
            }
            PMButton {
                id: purgeSelBtn
                objectName: "faceBatchDeleteSelBtn"
                tooltip: I18n.tr("删除勾选的人脸标签（照片均不受影响，需点两次确认）")
                text: root.confirmPurgeSel
                      ? I18n.tr("确认删除选中（") + root.checkedFaceIds.length + "）？"
                      : I18n.tr("删除选中标签（") + root.checkedFaceIds.length + "）"
                height: 30
                enabled: root.checkedFaceIds.length > 0
                emphasized: root.confirmPurgeSel
                onClicked: {
                    if (!root.confirmPurgeSel) {
                        root.confirmPurgeSel = true
                        purgeReset.restart()
                        return
                    }
                    root.confirmPurgeSel = false
                    purgeReset.stop()
                    var n = 0
                    for (var j = root.checkedFaceIds.length - 1; j >= 0; --j)
                        if (LibraryBridge.dismissFace(root.checkedFaceIds[j])) n++
                    root.messageRequested(I18n.tr("已删除 ") + n + I18n.tr(" 个人脸标签（照片均未受影响）"),
                               n > 0 ? "success" : "warning")
                    root.refresh()
                }
            }
            PMButton {
                objectName: "faceBatchHideBtn"
                tooltip: I18n.tr("把列表中全部人脸设为隐藏（可逆）")
                text: I18n.tr("隐藏全部")
                height: 30
                enabled: root.faceCount > 0
                onClicked: {
                    var n = 0
                    for (var i = 0; i < faceModel.count; ++i)
                        if (LibraryBridge.setFaceHidden(faceModel.get(i).faceId, true)) n++
                    root.messageRequested(I18n.tr("已隐藏 ") + n + I18n.tr(" 张人脸（可逆）"), n > 0 ? "success" : "warning")
                    root.refresh()
                }
            }
            PMButton {
                id: purgeBtn
                objectName: "faceBatchDeleteBtn"
                tooltip: I18n.tr("删除列表中全部人脸标签（照片均不受影响，需点两次确认）")
                text: I18n.tr("删除全部标签")
                height: 30
                enabled: root.faceCount > 0
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
                    for (var i = faceModel.count - 1; i >= 0; --i)
                        if (LibraryBridge.dismissFace(faceModel.get(i).faceId)) n++
                    root.messageRequested(I18n.tr("已删除 ") + n + I18n.tr(" 个人脸标签（照片均未受影响）"),
                               n > 0 ? "success" : "warning")
                    root.refresh()
                }
            }
            Timer { id: purgeReset; interval: 4000;
                    onTriggered: { root.confirmPurge = false; root.confirmPurgeSel = false } }
        }
    }

}
