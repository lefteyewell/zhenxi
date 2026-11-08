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

/* 统计看板：总量卡片 + 按年/月/设备/地点的分布。 */
Item {
    id: root
    objectName: "statsPage"

    ListModel { id: yearModel }
    ListModel { id: monthModel }
    ListModel { id: deviceModel }
    ListModel { id: locationModel }
    ListModel { id: ratingModel }

    function refresh() {
        var d = LibraryBridge.statsDashboard()
        var t = d.totals
        totalsText.text = I18n.tr("照片 ") + t.photos + I18n.tr(" · 人脸 ") + t.faces
            + I18n.tr(" · 人物 ") + t.persons + I18n.tr(" · 事件 ") + t.events
            + I18n.tr(" · 标签 ") + t.tags + I18n.tr(" · 重复组 ") + t.dupGroups
            + I18n.tr(" · 已移出 ") + t.movedOut
            + I18n.tr(" · 已评级 ") + t.rated + I18n.tr(" · 精选 ") + t.picked + I18n.tr(" · 排除 ") + t.rejected
        _fill(yearModel, d.byYear)
        _fill(monthModel, d.byMonth)
        _fill(deviceModel, d.byDevice)
        _fill(locationModel, d.byLocation)
        _fill(ratingModel, d.byRating)
    }

    function _fill(model, arr) {
        model.clear()
        for (var i = 0; i < arr.length; ++i)
            model.append(arr[i])
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
                text: I18n.tr("统计")
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true; width: 10 }
            Text {
                id: totalsText
                objectName: "statsTotals"
                /* 限定宽度使 elide 生效（Row 内隐式宽度曾溢出页面 66px） */
                width: parent.width - titleText.width - 2 * parent.spacing
                       - parent.leftPadding - parent.rightPadding
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.primary
                elide: Text.ElideRight
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

            GridLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingMedium
                columns: 2
                columnSpacing: Theme.spacingMedium
                rowSpacing: Theme.spacingMedium

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.surfaceAlt
                    radius: Theme.radiusMedium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSmall
                        spacing: 4
                        Text {
                            text: I18n.tr("按年份")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            objectName: "statsYearList"
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            model: yearModel
                            /* 0.6.22：表格行加底部分隔线（用户反馈：行与行边界
                               不明显）。RowLayout 不能画线，外包一层 Item。 */
                            delegate: Item {
                                width: parent ? parent.width : 0
                                height: 26
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingSmall
                                    /* 0.6.24 补20：右侧避让 12px 覆盖式滚动条+2px 间隙，
                                       数字列不再被滚动条遮挡 */
                                    anchors.rightMargin: 14
                                    Text {
                                        Layout.fillWidth: true
                                        text: model.key
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.text
                                        elide: Text.ElideMiddle
                                    }
                                    Text {
                                        text: model.count
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textDim
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.surfaceAlt
                    radius: Theme.radiusMedium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSmall
                        spacing: 4
                        Text {
                            text: I18n.tr("按月份")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            objectName: "statsMonthList"
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            model: monthModel
                            /* 0.6.22：表格行加底部分隔线（用户反馈：行与行边界
                               不明显）。RowLayout 不能画线，外包一层 Item。 */
                            delegate: Item {
                                width: parent ? parent.width : 0
                                height: 26
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingSmall
                                    /* 0.6.24 补20：右侧避让 12px 覆盖式滚动条+2px 间隙，
                                       数字列不再被滚动条遮挡 */
                                    anchors.rightMargin: 14
                                    Text {
                                        Layout.fillWidth: true
                                        text: model.key
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.text
                                        elide: Text.ElideMiddle
                                    }
                                    Text {
                                        text: model.count
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textDim
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.surfaceAlt
                    radius: Theme.radiusMedium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSmall
                        spacing: 4
                        Text {
                            text: I18n.tr("按设备")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            objectName: "statsDeviceList"
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            model: deviceModel
                            /* 0.6.22：表格行加底部分隔线（用户反馈：行与行边界
                               不明显）。RowLayout 不能画线，外包一层 Item。 */
                            delegate: Item {
                                width: parent ? parent.width : 0
                                height: 26
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingSmall
                                    /* 0.6.24 补20：右侧避让 12px 覆盖式滚动条+2px 间隙，
                                       数字列不再被滚动条遮挡 */
                                    anchors.rightMargin: 14
                                    Text {
                                        Layout.fillWidth: true
                                        text: model.key
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.text
                                        elide: Text.ElideMiddle
                                    }
                                    Text {
                                        text: model.count
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textDim
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.surfaceAlt
                    radius: Theme.radiusMedium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSmall
                        spacing: 4
                        Text {
                            text: I18n.tr("按地点")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            objectName: "statsLocationList"
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            model: locationModel
                            /* 0.6.22：表格行加底部分隔线（用户反馈：行与行边界
                               不明显）。RowLayout 不能画线，外包一层 Item。 */
                            delegate: Item {
                                width: parent ? parent.width : 0
                                height: 26
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingSmall
                                    /* 0.6.24 补20：右侧避让 12px 覆盖式滚动条+2px 间隙，
                                       数字列不再被滚动条遮挡 */
                                    anchors.rightMargin: 14
                                    Text {
                                        Layout.fillWidth: true
                                        text: model.key
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.text
                                        elide: Text.ElideMiddle
                                    }
                                    Text {
                                        text: model.count
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textDim
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }
                            }
                        }
                    }
                }
            Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Theme.surfaceAlt
                    radius: Theme.radiusMedium
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSmall
                        spacing: 4
                        Text {
                            text: I18n.tr("按评级")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            objectName: "statsRatingList"
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            model: ratingModel
                            /* 0.6.22：表格行加底部分隔线（同上） */
                            delegate: Item {
                                width: parent ? parent.width : 0
                                height: 26
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Theme.spacingSmall
                                    /* 0.6.24 补20：右侧避让 12px 覆盖式滚动条+2px 间隙，
                                       数字列不再被滚动条遮挡 */
                                    anchors.rightMargin: 14
                                    Text {
                                        Layout.fillWidth: true
                                        text: "★".repeat(parseInt(model.key)) + " " + model.key + I18n.tr(" 星")
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: "#f5c842"
                                        elide: Text.ElideMiddle
                                    }
                                    Text {
                                        text: model.count
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textDim
                                    }
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}