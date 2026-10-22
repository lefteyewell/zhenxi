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

/* 0.5.48：定时任务时间输入（从设置迁到「定时任务」菜单）。
   mode: "daily" → HH:mm；"once" → YYYY-MM-DD HH:mm。
   用法：schedTimeDialog.openFor("daily" | "once")。 */
Popup {
    id: root
    objectName: "scheduleTimeDialog"
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    width: 340
    height: 170
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: Theme.spacingMedium

    property string mode: "daily"

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    function openFor(mode) {
        root.mode = mode
        input.text = mode === "daily"
            ? (LibraryBridge ? LibraryBridge.scheduleTime() : "09:00")
            : (LibraryBridge ? LibraryBridge.scheduleOnceAt() : "")
        errText.text = ""
        root.open()
    }

    contentItem: ColumnLayout {
        spacing: Theme.spacingSmall

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSmall

            PopupDragHandle { objectName: "schedTimeDragHandle"; target: root; Layout.fillWidth: true; Layout.preferredHeight: 24 }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: root.mode === "daily" ? I18n.tr("每日执行时间（HH:mm）") : I18n.tr("一次性时间（YYYY-MM-DD HH:mm）")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: Theme.text
            }
        }
        TextField {
            id: input
            Layout.fillWidth: true
            font.family: Theme.fontFamily
            font.pixelSize: 13
            color: Theme.text
            placeholderText: root.mode === "daily" ? "09:00" : "2026-10-20 09:00"
            onAccepted: okBtn.clicked()
        }
        Text {
            id: errText
            Layout.fillWidth: true
            visible: text !== ""
            text: ""
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.danger
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            text: root.mode === "daily"
                  ? I18n.tr("每天到点自动执行所选任务（程序运行期间；配合开机启动+托盘常驻更可靠）。")
                  : I18n.tr("到点执行一次后自动关闭定时（程序运行期间）。")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
        Item { Layout.fillHeight: true }
        Row {
            Layout.alignment: Qt.AlignRight
            spacing: Theme.spacingSmall
            PMButton {
                text: I18n.tr("取消")
                onClicked: root.close()
            }
            PMButton {
                id: okBtn
                text: I18n.tr("确定")
                onClicked: {
                    var v = input.text.trim()
                    if (root.mode === "daily") {
                        if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) {
                            errText.text = I18n.tr("格式应为 HH:mm，例如 09:00")
                            return
                        }
                        LibraryBridge.setScheduleTime(v)
                    } else {
                        var d = new Date(v.replace(" ", "T"))
                        if (isNaN(d.getTime())) {
                            errText.text = I18n.tr("格式应为 YYYY-MM-DD HH:mm，例如 2026-10-20 09:00")
                            return
                        }
                        LibraryBridge.setScheduleOnceAt(v)
                    }
                    root.close()
                }
            }
        }
    }
}
