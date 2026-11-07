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

/* 0.6.23：月历式日期选择弹窗（用户反馈：年起止不该有范围限制，
   要月历效果）——手绘月网格，年份/月份无限翻页，零外部依赖。
   用法：openFor(currentDateStr) 预选；picked(date) 信号带回所选日期。 */
Popup {
    id: root

    objectName: "datePickerPopup"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    padding: 10
    width: 252

    /* 弹窗当前显示的年月（以此渲染网格；翻页只改它，无任何范围限制） */
    property int shownYear: new Date().getFullYear()
    property int shownMonth: new Date().getMonth()          // 0-11
    property date selected: new Date(NaN)

    signal picked(date d)

    function openFor(currentStr) {
        if (currentStr && currentStr.length === 10) {
            var p = currentStr.split("-")
            var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]))
            if (!isNaN(d.getTime())) {
                selected = d
                shownYear = d.getFullYear()
                shownMonth = d.getMonth()
            }
        } else {
            selected = new Date(NaN)
            shownYear = new Date().getFullYear()
            shownMonth = new Date().getMonth()
        }
        open()
    }

    function _shiftMonths(n) {
        var d = new Date(shownYear, shownMonth + n, 1)
        shownYear = d.getFullYear()
        shownMonth = d.getMonth()
        gridModelReset++
    }

    property int gridModelReset: 0
    /* 网格行数：首日偏移 + 当月天数 ≤35 → 5 行，否则 6 行 */
    property int _gridRows: ((new Date(shownYear, shownMonth, 1).getDay() + 6) % 7
                             + new Date(shownYear, shownMonth + 1, 0).getDate()) > 35 ? 6 : 5
    /* 42 格（6 行 × 7 列，周一起始）：本月日期 + 前后月补位 */
    function _cellDate(i) {
        var first = new Date(shownYear, shownMonth, 1)
        var lead = (first.getDay() + 6) % 7                    // 周一=0
        return new Date(shownYear, shownMonth, 1 - lead + i)
    }

    background: Rectangle {
        radius: Theme.radiusMedium
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        spacing: 6

        /* 年月表头：‹‹ ‹ 2026-11 › ›（无限翻页）。
           0.6.23：RowLayout 忽略子项显式 width——必须用 Layout.preferredWidth，
           否则按钮按 implicit 96px 渲染把弹窗撑爆（用户截图月历显示不正确的根因） */
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            PMButton { text: "«"; Layout.preferredWidth: 34; Layout.preferredHeight: 26; tooltip: I18n.tr("上一年"); onClicked: root._shiftMonths(-12) }
            PMButton { text: "‹"; Layout.preferredWidth: 30; Layout.preferredHeight: 26; tooltip: I18n.tr("上个月"); onClicked: root._shiftMonths(-1) }
            Item { Layout.fillWidth: true }
            Text {
                text: root.shownYear + "-" + (root.shownMonth < 9 ? "0" : "") + (root.shownMonth + 1)
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
            PMButton { text: "›"; Layout.preferredWidth: 30; Layout.preferredHeight: 26; tooltip: I18n.tr("下个月"); onClicked: root._shiftMonths(1) }
            PMButton { text: "»"; Layout.preferredWidth: 34; Layout.preferredHeight: 26; tooltip: I18n.tr("下一年"); onClicked: root._shiftMonths(12) }
        }

        /* 星期表头（周一起始） */
        Row {
            Layout.fillWidth: true
            spacing: 0
            Repeater {
                model: [I18n.tr("一"), I18n.tr("二"), I18n.tr("三"), I18n.tr("四"),
                        I18n.tr("五"), I18n.tr("六"), I18n.tr("日")]
                delegate: Item {
                    width: 33
                    height: 20
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        color: index >= 5 ? Theme.accent : Theme.textDim
                    }
                }
            }
        }

        /* 6×7 日网格 */
        Grid {
            id: dayGrid
            Layout.fillWidth: true
            columns: 7
            spacing: 0
            property int reset: root.gridModelReset

            Repeater {
                /* 0.6.23：格数 = 行数×7（Grid columns=7，model 是 Cell 数不是行数！
                   此前误写行数导致整月只渲染一行——用户实测反馈） */
                model: root._gridRows * 7

                delegate: Item {
                    width: 33
                    height: 28

                    readonly property var cellDate: root._cellDate(index)
                    readonly property bool inMonth: cellDate.getMonth() === root.shownMonth
                    readonly property bool isSel: !isNaN(root.selected.getTime())
                            && cellDate.getFullYear() === root.selected.getFullYear()
                            && cellDate.getMonth() === root.selected.getMonth()
                            && cellDate.getDate() === root.selected.getDate()
                    readonly property bool isToday: {
                        var t = new Date()
                        return cellDate.getFullYear() === t.getFullYear()
                                && cellDate.getMonth() === t.getMonth()
                                && cellDate.getDate() === t.getDate()
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: 26
                        height: 24
                        radius: 6
                        color: isSel ? Theme.primary
                             : dayMa.containsMouse ? Theme.hover : "transparent"
                        border.width: isToday && !isSel ? 1 : 0
                        border.color: Theme.primary
                        Text {
                            anchors.centerIn: parent
                            text: cellDate.getDate()
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: isSel ? "white"
                                 : !inMonth ? Theme.textDim
                                 : dayMa.containsMouse ? Theme.text : Theme.text
                            opacity: inMonth ? 1 : 0.45
                        }
                        MouseArea {
                            id: dayMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.selected = cellDate
                                root.picked(cellDate)
                                root.close()
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            PMButton {
                text: I18n.tr("今天")
                Layout.preferredWidth: 96
                Layout.preferredHeight: 26
                tooltip: I18n.tr("选中今天")
                onClicked: {
                    var t = new Date()
                    root.selected = t
                    root.picked(t)
                    root.close()
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("清除")
                Layout.preferredWidth: 96
                Layout.preferredHeight: 26
                tooltip: I18n.tr("清除已选日期（不限）")
                onClicked: {
                    root.selected = new Date(NaN)
                    root.picked(new Date(NaN))
                    root.close()
                }
            }
        }
    }
}
