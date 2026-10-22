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

/* 导出历史（0.5.39）：每次导出的记录（文件/目录/格式/分辨率/时间）。
   纯记录视图，不参与任何删除；点「打开目录」定位到导出文件夹。 */
Item {
    id: root
    objectName: "exportHistoryPage"

    ListModel { id: historyModel }

    function refresh() {
        historyModel.clear()
        var n = LibraryBridge.exportHistoryCount()
        countText.text = n > 0 ? (n + I18n.tr(" 条记录")) : ""
        var arr = LibraryBridge.exportHistory(0, 1000)
        for (var i = 0; i < arr.length; ++i)
            historyModel.append(arr[i])
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
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.tr("已导出")
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
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.tr("导出记录仅供查阅，删除这些文件不影响照片库")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
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
                objectName: "exportHistoryList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingTiny
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: historyModel

                delegate: Rectangle {
                    width: listView.width
                    height: 56
                    radius: Theme.radiusSmall
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.rightMargin: Theme.spacingMedium
                        spacing: Theme.spacingMedium

                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: model.name
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: Theme.text
                                elide: Text.ElideMiddle
                                width: parent.width
                            }
                            Text {
                                text: model.destDir
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.textDim
                                elide: Text.ElideMiddle
                                width: parent.width
                            }
                        }
                        Text {
                            text: model.fmtText + " · " + model.resText
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                        Text {
                            text: model.exportedAt
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                        PMButton {
                            objectName: "exportOpenDirBtn"
                            text: I18n.tr("打开目录")
                            height: 26
                            tooltip: I18n.tr("在资源管理器中打开导出目录")
                            onClicked: Qt.openUrlExternally(
                                "file:///" + model.destDir.replace(/\\/g, "/"))
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: historyModel.count === 0
                    text: I18n.tr("还没有导出记录\n在图库选中照片后点「导出…」即可导出，记录会出现在这里")
                    horizontalAlignment: Text.AlignHCenter
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                    lineHeight: 1.6
                }
            }
        }
    }
}