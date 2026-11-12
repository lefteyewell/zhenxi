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

/* 关于：版本与版权信息 */
Popup {
    id: root

    objectName: "aboutDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 420
    height: 280
    padding: 0

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
                    text: I18n.tr("关于")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("软件版本与版权信息")
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

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        Item { Layout.fillWidth: true; Layout.fillHeight: true }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: AppName
                font.family: Theme.fontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: I18n.tr("版本 ") + AppVersion
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.primary
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: I18n.tr("本地照片管理 · 快速检索与智能归类")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: AppCopyright
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            /* 0.6.28：删去「许可证全文见随附 LICENSE 文件」——帮助菜单的
               「开源许可 (GPLv3)」条目显示的就是随包 LICENSE 文件全文，
               上方版权行的「见 帮助 → 开源许可 (GPLv3)」已指向同一内容，
               同弹窗内不再重复表述 */
            /* 0.6.29：整弹窗 GPLv3 只保留版权行一处；本行只作担保声明 +
               指引，不再重复许可名（真机反馈一行内 GPLv3 出现两次） */
            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 4
                text: I18n.tr("本程序为自由软件，不提供任何担保；许可证全文见「帮助 → 开源许可」。")
                font.family: Theme.fontFamily
                font.pixelSize: 10
                color: Theme.textDim
                horizontalAlignment: Text.AlignHCenter
            }
            /* 0.5.66：官方发布地址——源码获取（GPLv3 §6）与官方渠道声明 */
            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 2
                text: I18n.tr("<a href='https://github.com/lefteyewell/zhenxi'>项目主页 / 源码：github.com/lefteyewell/zhenxi</a>")
                font.family: Theme.fontFamily
                font.pixelSize: 10
                /* 0.6.21：深色模式下 primary 与背景对比不足，改亮色变体 */
                color: Theme.dark ? "#7EBCF9" : Theme.primary
                horizontalAlignment: Text.AlignHCenter
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.openUrlExternally(
                        "https://github.com/lefteyewell/zhenxi")
                }
            }
        }

        Item { Layout.fillWidth: true; Layout.fillHeight: true }
    }
}
