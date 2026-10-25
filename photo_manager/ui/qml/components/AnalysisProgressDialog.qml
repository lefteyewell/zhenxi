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

/* 分析进度弹窗：扫描/分析期间自动显示，醒目提示后台任务进度。
   0.5.53：① 任务列表（自动链共 N 阶段/当前第 i，单阶段任务不显示列表）；
   ② 「隐藏」后本次任务不再自动弹出（进度仍持续更新，手动可再打开）；
   ③ 明示「可正常操作、关闭不中断任务」。 */
Popup {
    id: root

    objectName: "analysisProgressDialog"

    modal: false
    closePolicy: Popup.CloseOnEscape
    x: Math.round((parent.width - width) / 2)
    y: Math.round(parent.height - height - 48)
    width: 520
    height: contentColumn.implicitHeight + padding * 2
    padding: 0

    /* 任务队列状态（LibraryBridge.chainProgress 驱动） */
    property var chainStages: []
    property int chainCurrent: 0
    /* 用户点「隐藏」后置 true：本次任务会话内不再自动弹出 */
    property bool suppressPop: false

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        id: contentColumn
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 42 }

            Rectangle {
                width: 26
                height: 26
                radius: Theme.radiusMedium
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.primary }
                    GradientStop { position: 1.0; color: Theme.accent }
                }
                Text {
                    anchors.centerIn: parent
                    text: "⏳"
                    font.pixelSize: 14
                }
            }
            Column {
                spacing: 2
                Text {
                    text: root.chainStages.length > 1
                          ? I18n.tr("后台任务运行中…（第 ") + Math.max(root.chainCurrent, 1) + " / "
                            + root.chainStages.length + I18n.tr(" 项）")
                          : I18n.tr("后台任务运行中…")
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    id: stageText
                    objectName: "stageText"
                    text: ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    elide: Text.ElideRight
                    Layout.maximumWidth: 380
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("隐藏")
                objectName: "btnHideProgress"
                tooltip: I18n.tr("隐藏弹窗（任务继续在后台运行；点状态栏的进度条可重新打开）")
                onClicked: {
                    root.suppressPop = true
                    root.close()
                }
            }
        }

        ProgressBar {
            id: taskBar
            objectName: "analysisProgressBar"
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: Theme.spacingMedium
            from: 0
            to: 100
            value: 0
        }
        Text {
            id: countText
            objectName: "analysisCountText"
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: 6
            Layout.maximumWidth: 480
            text: ""
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
            elide: Text.ElideLeft
            wrapMode: Text.WrapAnywhere
        }

        /* 任务列表（多阶段时显示：✓已完成 / ▶进行中 / ·待办） */
        Column {
            id: chainList
            objectName: "analysisChainList"
            visible: root.chainStages.length > 1
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: 8
            spacing: 3

            Repeater {
                model: root.chainStages.length

                Row {
                    required property int index
                    spacing: 6
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 14
                        text: index + 1 < root.chainCurrent ? "✓"
                              : (index + 1 === root.chainCurrent ? "▶" : "·")
                        color: index + 1 < root.chainCurrent ? "#2e7d32"
                               : (index + 1 === root.chainCurrent ? Theme.primary : Theme.textDim)
                        font.pixelSize: 11
                        font.weight: Font.Bold
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (index + 1) + ". " + root.chainStages[index]
                              + (index + 1 < root.chainCurrent ? I18n.tr("（已完成）") : "")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: index + 1 === root.chainCurrent ? Theme.text : Theme.textDim
                        font.weight: index + 1 === root.chainCurrent ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: 8
            Layout.bottomMargin: Theme.spacingSmall
            text: I18n.tr("任务在后台运行，可正常浏览与管理照片；隐藏本弹窗不会中断任务。")
            font.family: Theme.fontFamily
            font.pixelSize: 10
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
    }

    /* 0.5.67：从状态栏重新调出（用户点底部进度条/任务文字时调用） */
    function reopen() {
        root.suppressPop = false
        hideTimer.stop()
        root.open()
    }

    /* 收到任一进度信号即弹出并刷新；total<=0 视为结束并延迟收起 */
    Connections {
        target: LibraryBridge
        function onChainProgress(current, totalStages, stagesJson) {
            try {
                root.chainStages = JSON.parse(stagesJson)
            } catch (e) {
                root.chainStages = []
            }
            root.chainCurrent = current
            if (current === 0 && totalStages > 0)
                root.suppressPop = false   /* 新任务会话开始：恢复自动弹出 */
        }
        function onTaskProgress(done, total, labelText) {
            if (total > 0) {
                taskBar.value = done * 100 / total
                /* labelText 形如"文字识别|C:\dir\a.jpg"：竖线前为阶段名，后为正在处理的文件 */
                var sep = labelText.indexOf("|")
                var stage = sep >= 0 ? labelText.substring(0, sep) : labelText
                var fileP = sep >= 0 ? labelText.substring(sep + 1) : ""
                stageText.text = (stage ? stage + "：" : "") + done + " / " + total
                countText.text = fileP
                countText.visible = fileP !== ""
                if (!root.suppressPop)
                    root.open()
            } else {
                taskBar.value = 0
                stageText.text = labelText || ""
                countText.text = ""
                countText.visible = false
                hideTimer.restart()
            }
        }
        function onMessage(msg) {
            /* 阶段完成/失败消息：仅当弹窗已打开时展示，避免打扰 */
            if (root.opened) {
                stageText.text = msg
                countText.text = ""
                countText.visible = false
                taskBar.value = 0
                hideTimer.restart()
            }
        }
        function onBusyChanged() {
            /* 任务会话结束（互斥释放）→ 解除隐藏抑制 */
            if (LibraryBridge && LibraryBridge.busyCount() === 0)
                root.suppressPop = false
        }
    }

    Timer {
        id: hideTimer
        interval: 2500
        repeat: false
        onTriggered: root.close()
    }

    onOpened: hideTimer.stop()
}
