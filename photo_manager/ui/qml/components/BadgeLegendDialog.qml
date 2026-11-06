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

/* 网格覆盖标志图例（0.6.20）：把照片卡片上的全部角标集中解释，
   用户反馈「标志太多、不知道什么意思」。样式与 photoCell 一一对应。 */
Popup {
    id: root

    objectName: "badgeLegendDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 460
    height: Math.min(parent.height - 40, 560)
    padding: 0

    /* 每项：badge(示例控件类型由 delegate 绘制) / desc(说明) */
    readonly property var legendItems: [
        { kind: "check", desc: I18n.tr("已选中（主色边框 + 勾选徽标 + 整格着色）") },
        { kind: "faces", label: "◎3", desc: I18n.tr("已识别到 N 张人脸（数字为人脸数）") },
        { kind: "text", label: I18n.tr("文"), desc: I18n.tr("照片内识别到文字（OCR），可用 text: 语法搜索") },
        { kind: "warn", label: "!", desc: I18n.tr("文件数据不完整（可能传输中断/损坏），预览为相机内嵌图") },
        { kind: "pick", label: "√", desc: I18n.tr("「精选」旗标（P 键或右键设置）") },
        { kind: "reject", label: "×", desc: I18n.tr("「排除」旗标（X 键或右键设置；筛选候选）") },
        { kind: "rating", label: "★★★", desc: I18n.tr("星级评分（1~5 星，左下角金星）") },
        { kind: "stack", label: "▦4", desc: I18n.tr("照片堆叠（相似连拍归并为一组，数字为成员数）") },
        { kind: "video", label: "▶", desc: I18n.tr("视频（左下角 ▶ 加时长）") },
        { kind: "color", color: "#e53935", desc: I18n.tr("色标圆点（红/黄/绿/蓝/紫，右键「色标」设置）") },
        { kind: "caption", desc: I18n.tr("底部小字：拍摄日期 + 文件名") }
    ]

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 52 }

            Column {
                spacing: 2
                Text {
                    text: I18n.tr("照片标志图例")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("网格照片上各类角标的含义")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("关闭")
                onClicked: root.close()
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

        ListView {
            id: legendList
            objectName: "badgeLegendList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Theme.spacingMedium
            spacing: Theme.spacingTiny
            clip: true
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
            model: root.legendItems

            delegate: Rectangle {
                width: legendList.width
                height: 44
                radius: Theme.radiusSmall
                color: Theme.bg
                border.width: 1
                border.color: Theme.divider

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingMedium
                    anchors.rightMargin: Theme.spacingMedium
                    spacing: Theme.spacingMedium

                    /* 示例徽标（与 photoCell 同款画法） */
                    Item {
                        Layout.preferredWidth: 64
                        Layout.fillHeight: true

                        Rectangle {
                            visible: modelData.kind === "check"
                            anchors.centerIn: parent
                            width: 20; height: 20; radius: 10
                            color: Theme.primary
                            border.width: 2; border.color: "white"
                            Text { anchors.centerIn: parent; text: "√"
                                   font.pixelSize: 12; font.weight: Font.Bold; color: "white" }
                        }
                        Rectangle {
                            visible: modelData.kind === "faces" || modelData.kind === "stack"
                            anchors.centerIn: parent
                            width: 30; height: 18; radius: 9
                            color: modelData.kind === "stack" ? Theme.primary : Theme.accent
                            Text { anchors.centerIn: parent; text: modelData.label || ""
                                   font.pixelSize: 10; color: "white" }
                        }
                        Rectangle {
                            visible: modelData.kind === "text"
                            anchors.centerIn: parent
                            width: 18; height: 18; radius: 4
                            color: Theme.primary
                            Text { anchors.centerIn: parent; text: modelData.label || ""
                                   font.pixelSize: 10; color: "white" }
                        }
                        Rectangle {
                            visible: modelData.kind === "warn"
                            anchors.centerIn: parent
                            width: 18; height: 18; radius: 9
                            color: "#e65100"
                            Text { anchors.centerIn: parent; text: modelData.label || ""
                                   font.pixelSize: 11; font.weight: Font.DemiBold; color: "white" }
                        }
                        Rectangle {
                            visible: modelData.kind === "pick" || modelData.kind === "reject"
                            anchors.centerIn: parent
                            width: 22; height: 18; radius: 9
                            color: modelData.kind === "pick" ? "#2e7d32" : "#b71c1c"
                            Text { anchors.centerIn: parent; text: modelData.label || ""
                                   font.pixelSize: 10; font.weight: Font.DemiBold; color: "white" }
                        }
                        Text {
                            visible: modelData.kind === "rating"
                            anchors.centerIn: parent
                            text: modelData.label || ""
                            font.pixelSize: 11
                            color: "#f5c842"
                            style: Text.Outline
                            styleColor: "black"
                        }
                        Rectangle {
                            visible: modelData.kind === "video"
                            anchors.centerIn: parent
                            width: 30; height: 18; radius: 9
                            color: "#CC000000"
                            Text { anchors.centerIn: parent; text: "▶ 1:23"
                                   font.pixelSize: 9; color: "white" }
                        }
                        Rectangle {
                            visible: modelData.kind === "color"
                            anchors.centerIn: parent
                            width: 14; height: 14; radius: 7
                            border.width: 1; border.color: "white"
                            color: modelData.color || "transparent"
                        }
                        Text {
                            visible: modelData.kind === "caption"
                            anchors.centerIn: parent
                            text: "03-02  IMG_1234.jpg"
                            font.pixelSize: 9
                            color: "white"
                            style: Text.Outline
                            styleColor: "black"
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: modelData.desc
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
