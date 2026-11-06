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

/* 库统计详情弹窗（0.6.22）：原先「详细统计」只往状态栏 toast 塞一长行，
   窗口窄时显示不全（用户反馈）。改为模态弹窗分格展示 + 扫描根目录清单。
   用法：statsDetailDialog.openWith(LibraryBridge.dbDetail()) */
Popup {
    id: root

    objectName: "statsDetailDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 560
    height: Math.min(parent.height - 40, 620)
    padding: 0

    /* dbDetail() 返回的统计数据，openWith 时填充 */
    property var stats: ({})
    readonly property var rootModel: {
        var r = stats.roots
        return Array.isArray(r) ? r : []
    }

    function openWith(d) {
        stats = d || {}
        open()
    }

    function _fmtCount(label, value) {
        return { label: label, value: value }
    }

    /* 上半部分：数字卡片网格（两项一行） */
    readonly property var countCards: [
        _fmtCount(I18n.tr("照片总数"), stats.photos),
        _fmtCount(I18n.tr("已索引"), stats.indexed),
        _fmtCount(I18n.tr("解析失败"), stats.failed),
        _fmtCount(I18n.tr("文件缺失"), stats.missing),
        _fmtCount(I18n.tr("人脸标注"), stats.faces),
        _fmtCount(I18n.tr("人物"), stats.persons),
        _fmtCount(I18n.tr("事件"), stats.events),
        _fmtCount(I18n.tr("标签记录"), stats.tags)
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
                    text: I18n.tr("库统计详情")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("照片数量、分析状态与扫描根目录")
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

        /* 数字卡片：GridLayout 两列，卡片间留缝显示边界 */
        GridLayout {
            Layout.fillWidth: true
            Layout.margins: Theme.spacingMedium
            columns: 2
            columnSpacing: Theme.spacingSmall
            rowSpacing: Theme.spacingSmall

            Repeater {
                model: root.countCards

                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    radius: Theme.radiusMedium
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.rightMargin: Theme.spacingMedium
                        spacing: Theme.spacingSmall

                        Text {
                            Layout.fillWidth: true
                            text: modelData.label
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textDim
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.value === undefined || modelData.value === null
                                  ? "-" : String(modelData.value)
                            font.family: Theme.fontFamily
                            font.pixelSize: 20
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                    }
                }
            }
        }

        Text {
            Layout.leftMargin: Theme.spacingLarge
            Layout.bottomMargin: Theme.spacingTiny
            text: I18n.tr("扫描根目录（") + root.rootModel.length + I18n.tr("）")
            font.family: Theme.fontFamily
            font.pixelSize: 12
            font.weight: Font.DemiBold
            color: Theme.text
        }

        ListView {
            id: rootsList
            objectName: "statsRootsList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            clip: true
            spacing: 0
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
            model: root.rootModel

            delegate: Rectangle {
                width: rootsList.width
                height: 40
                color: index % 2 === 0 ? Theme.bg : Theme.surface
                /* 0.6.22：行间分隔线（用户反馈：行与行没有边界） */
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Theme.divider
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingMedium
                    anchors.rightMargin: Theme.spacingMedium
                    spacing: 1

                    Text {
                        Layout.fillWidth: true
                        text: modelData.path || ""
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                        elide: Text.ElideMiddle
                    }
                    Text {
                        Layout.fillWidth: true
                        text: modelData.last
                              ? I18n.tr("上次扫描：") + modelData.last
                              : I18n.tr("尚未扫描")
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        color: Theme.textDim
                        elide: Text.ElideRight
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: rootsList.count === 0
                text: I18n.tr("还没有登记扫描根目录")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
        }
    }
}
