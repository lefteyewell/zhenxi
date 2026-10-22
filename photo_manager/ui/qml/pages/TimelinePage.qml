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

/* 时间线：按 年 → 月 → 天 层级浏览拍摄时间。
   年行点击展开/收起（显示该年月与天）；月行点击进入该月照片；天行点击进入该天照片。 */
Item {
    id: root
    objectName: "timelinePage"

    signal monthClicked(string ym)
    signal dayClicked(string day)

    property string _expandedYear: ""

    ListModel { id: timelineModel }

    function refresh() {
        timelineModel.clear()
        var years = LibraryBridge.timeline()
        for (var y = 0; y < years.length; ++y) {
            var yr = years[y]
            timelineModel.append({
                isYear: true, isMonth: false, isDay: false,
                label: yr.year + I18n.tr(" 年"), count: yr.photoCount, key: yr.year
            })
            if (root._expandedYear !== yr.year) continue
            for (var m = 0; m < yr.months.length; ++m) {
                var mo = yr.months[m]
                timelineModel.append({
                    isYear: false, isMonth: true, isDay: false,
                    label: mo.label, count: mo.photoCount, key: mo.key
                })
                var days = LibraryBridge.timelineDays(mo.key)
                for (var d = 0; d < days.length; ++d) {
                    var dd = days[d]
                    timelineModel.append({
                        isYear: false, isMonth: false, isDay: true,
                        label: dd.day, count: dd.photoCount, key: dd.day
                    })
                }
            }
        }
        countText.text = years.length + I18n.tr(" 年")
    }

    function _toggleYear(key) {
        root._expandedYear = (root._expandedYear === key) ? "" : key
        refresh()
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
                text: I18n.tr("时间线")
                anchors.verticalCenter: parent.verticalCenter
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
                objectName: "timelineList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingTiny
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: timelineModel

                delegate: Rectangle {
                    width: listView.width
                    height: model.isDay ? 32 : 44
                    radius: Theme.radiusMedium
                    color: model.isYear ? Theme.surfaceAlt : "transparent"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spacingMedium + (model.isMonth ? 24 : model.isDay ? 48 : 0)
                        anchors.rightMargin: Theme.spacingMedium
                        spacing: Theme.spacingSmall

                        Text {
                            text: (model.isYear ? (root._expandedYear === model.key ? "▾ " : "▸ ")
                                 : model.isMonth ? "▸ " : "· ")
                                  + model.label
                            font.family: Theme.fontFamily
                            font.pixelSize: model.isDay ? 12 : 14
                            font.weight: model.isDay ? Font.Normal : Font.DemiBold
                            color: Theme.text
                            elide: Text.ElideMiddle
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: model.count + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (model.isYear) root._toggleYear(model.key)
                            else if (model.isMonth) root.monthClicked(model.key)
                            else root.dayClicked(model.key)
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: timelineModel.count === 0
                    text: I18n.tr("暂无数据（先扫描照片）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
            }
        }
    }
}