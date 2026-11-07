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

/* 疑似重复人物（0.6.20 阶段一）：Top-N 未命名人物代表脸批量余弦扫描，
   列出卡在聚类阈值边缘（0.35~阈值）的候选对，并排预览 + 相似度百分比，
   支持合并（并入照片数多的一方）与忽略（跨扫描持久）。
   红线：合并只改 faces.person_id 标签，绝不触碰照片文件。 */
Dialog {
    popupType: Popup.Item   /* 0.6.23：统一场景内渲染（原生顶层窗口在麒麟不显示/Windows 可能被主窗遮挡） */
    id: root
    objectName: "dupPersonsDialog"

    signal messageRequested(string msg, string kind)

    modal: true
    width: Math.min(parent ? parent.width - 60 : 760, 720)
    height: Math.min(parent ? parent.height - 60 : 600, 580)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    function openDialog() {
        root.open()
    }

    /* 0.6.21 假死修复：候选构建移到后台线程，本方法只发请求；
       数据经 onDupCandidatesReady 信号回填（同步版在大库上会卡 UI 数秒） */
    function reload() {
        loading = true
        LibraryBridge.dupCandidatesAsync()
    }

    function _status() { return LibraryBridge.dupScanStatus() }

    onOpened: {
        /* 0.6.21：不再自动开全库扫描（真机反馈资源不可预期）——
           扫描由入口显式触发（人物页「查找疑似重复」锚点扫 / 本弹窗
           「全库扫描」按钮），这里只反映状态 + 拉候选 */
        var s = _status()
        scanBusy = s.running === true
        countText.text = I18n.tr("加载中…")
        reload()
    }

    /* 扫描在后台跑：完成信号到达时（弹窗开着就）刷新列表 */
    property bool scanBusy: false
    property bool loading: false
    Connections {
        target: LibraryBridge
        function onDupScanFinished(n) {
            root.scanBusy = false
            if (root.visible) {
                root.reload()
                if (n > 0)
                    root.messageRequested(
                        I18n.tr("扫描完成：发现 ") + n + I18n.tr(" 组疑似重复人物"), "success")
                else if (n === 0)
                    root.messageRequested(I18n.tr("扫描完成：未发现疑似重复人物"), "info")
            }
        }
        function onDupCandidatesReady(arr) {
            if (!root.visible)
                return
            root.loading = false
            pairModel.clear()
            for (var i = 0; i < arr.length; ++i)
                pairModel.append(arr[i])
            countText.text = pairModel.count > 0
                ? I18n.tr("共 ") + pairModel.count + I18n.tr(" 组疑似重复")
                : (root.scanBusy ? I18n.tr("扫描中…") : I18n.tr("暂无候选"))
        }
    }

    ListModel { id: pairModel }

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
                text: I18n.tr("疑似重复人物")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
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
                objectName: "dupRescanBtn"
                text: I18n.tr("全库扫描")
                height: 28
                enabled: !root.scanBusy
                Layout.alignment: Qt.AlignVCenter
                tooltip: I18n.tr("对照片数前 1500 的未命名人物做全对全扫描（推荐先用人物页的「查找疑似重复」按人查）")
                onClicked: {
                    root.scanBusy = true
                    countText.text = I18n.tr("扫描中…")
                    LibraryBridge.dupScanStart()
                }
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
            text: I18n.tr("相似度在聚类阈值边缘、可能是同一个人的未命名人物组合。合并会把照片少的一方并入照片多的一方（只改归属标签，照片不受影响）。")
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

            ListView {
                id: pairList
                objectName: "dupPairList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                spacing: 4
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                model: pairModel

                delegate: Rectangle {
                    width: pairList.width
                    height: 92
                    radius: Theme.radiusMedium
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.divider

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.rightMargin: Theme.spacingMedium
                        spacing: Theme.spacingMedium

                        /* 左侧人物头像（代表脸缓存裁剪，无需等 HQ） */
                        Rectangle {
                            width: 64; height: 64; radius: 32
                            color: Theme.surfaceAlt
                            clip: true
                            property bool hasAv: typeof model.avA !== "undefined" && !!model.avA
                            Image {
                                anchors.fill: parent
                                visible: parent.hasAv
                                source: parent.hasAv
                                        ? "file:///" + String(model.avA.avatarSrc).replace(/\\/g, "/") : ""
                                sourceClipRect: parent.hasAv
                                        ? Qt.rect(model.avA.avatarX || 0, model.avA.avatarY || 0,
                                                  model.avA.avatarW || 1, model.avA.avatarH || 1) : Qt.rect(0, 0, 1, 1)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: !parent.hasAv
                                text: "◎"; font.pixelSize: 22
                            }
                        }
                        Column {
                            Layout.preferredWidth: pairList.width * 0.24
                            Text {
                                width: parent.width
                                text: model.aName
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideMiddle
                            }
                            Text {
                                text: (model.aCount || 0) + I18n.tr(" 张")
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textDim
                            }
                        }

                        Text {
                            text: I18n.tr("相似 ") + model.sim + "%"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: model.sim >= 45 ? Theme.warning : Theme.text
                        }

                        Rectangle {
                            width: 64; height: 64; radius: 32
                            color: Theme.surfaceAlt
                            clip: true
                            property bool hasAv: typeof model.avB !== "undefined" && !!model.avB
                            Image {
                                anchors.fill: parent
                                visible: parent.hasAv
                                source: parent.hasAv
                                        ? "file:///" + String(model.avB.avatarSrc).replace(/\\/g, "/") : ""
                                sourceClipRect: parent.hasAv
                                        ? Qt.rect(model.avB.avatarX || 0, model.avB.avatarY || 0,
                                                  model.avB.avatarW || 1, model.avB.avatarH || 1) : Qt.rect(0, 0, 1, 1)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: !parent.hasAv
                                text: "◎"; font.pixelSize: 22
                            }
                        }
                        Column {
                            Layout.preferredWidth: pairList.width * 0.24
                            Text {
                                width: parent.width
                                text: model.bName
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideMiddle
                            }
                            Text {
                                text: (model.bCount || 0) + I18n.tr(" 张")
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textDim
                            }
                        }

                        Item { Layout.fillWidth: true }
                        PMButton {
                            objectName: "dupMergeBtn"
                            text: I18n.tr("合并 →")
                            width: 84
                            height: 30
                            tooltip: I18n.tr("把左侧人物并入右侧（照片数多的一方）")
                            onClicked: {
                                var n = LibraryBridge.mergePersons(model.a, model.b)
                                if (n > 0) {
                                    root.messageRequested(
                                        I18n.tr("已合并：") + model.aName + " → " + model.bName, "success")
                                    root.reload()
                                } else {
                                    root.messageRequested(I18n.tr("合并失败"), "warning")
                                }
                            }
                        }
                        PMButton {
                            objectName: "dupIgnoreBtn"
                            text: I18n.tr("忽略")
                            width: 64
                            height: 30
                            tooltip: I18n.tr("不再提示这一对（重新扫描也会跳过）")
                            onClicked: {
                                LibraryBridge.dupIgnore(model.a, model.b)
                                root.reload()
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: pairModel.count === 0
                    text: root.scanBusy
                          ? I18n.tr("正在扫描未命名人物代表脸…")
                          : I18n.tr("暂无候选：在人物页勾选 1 个人物点「查找疑似重复」，或点上方「全库扫描」")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }
        }
    }
}
