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

/* 回忆 · X 年前的今天：按「月-日」回看往年同日拍的照片，按年分组展示。
   默认取今天；可在右上角输入 MM-DD 切换查看任意一天。纯读取、零风险。 */
Item {
    id: root
    objectName: "onThisDayPage"

    signal photoClicked(int photoId)

    property string monthDay: ""      // MM-DD，空=今天
    property int cellSize: 128
    property var yearGroups: []       // [{year, count, photos:[...]}]

    function _today() {
        var d = new Date()
        return ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2)
    }

    function refresh() {
        var md = root.monthDay || _today()
        var rows = LibraryBridge.onThisDay(md, 0, 2000)
        var buckets = {}
        for (var i = 0; i < rows.length; ++i) {
            var y = rows[i].year
            if (!buckets[y]) buckets[y] = []
            buckets[y].push(rows[i])
        }
        var keys = Object.keys(buckets).sort()
        var groups = []
        for (var k = 0; k < keys.length; ++k) {
            var yk = keys[k]
            groups.push({ year: yk, count: buckets[yk].length, photos: buckets[yk] })
        }
        root.yearGroups = groups
        countText.text = rows.length + I18n.tr(" 张 · ") + groups.length + I18n.tr(" 年（") + md + "）"
        emptyText.visible = (rows.length === 0)
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
                text: I18n.tr("回忆 · X 年前的今天")
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
            Item { Layout.fillWidth: true }
            TextField {
                id: mdField
                objectName: "mdField"
                width: 92
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                placeholderText: "MM-DD"
                text: root.monthDay || _today()
                font.family: Theme.fontFamily
                font.pixelSize: 12
                validator: RegularExpressionValidator { regularExpression: /^\d{2}-\d{2}$/ }
            }
            PMButton {
                text: I18n.tr("查看")
                height: 30
                onClicked: { root.monthDay = mdField.text.trim(); refresh() }
            }
            PMButton {
                text: I18n.tr("今天")
                height: 30
                onClicked: { mdField.text = _today(); root.monthDay = ""; refresh() }
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

            ScrollView {
                id: sv
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

                Column {
                    width: sv.availableWidth
                    spacing: Theme.spacingMedium

                    Repeater {
                        model: root.yearGroups
                        delegate: Column {
                            width: parent.width
                            spacing: Theme.spacingTiny

                            Text {
                                text: modelData.year + I18n.tr(" 年  ·  ") + modelData.count + I18n.tr(" 张")
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                color: Theme.text
                            }

                            Flow {
                                width: parent.width
                                spacing: Theme.spacingSmall

                                Repeater {
                                    model: modelData.photos
                                    delegate: Rectangle {
                                        width: root.cellSize
                                        height: root.cellSize
                                        radius: Theme.radiusMedium
                                        color: Theme.bg
                                        border.width: 1
                                        border.color: Theme.divider
                                        clip: true

                                        Image {
                                            id: thumbImg
                                            anchors.fill: parent
                                            anchors.margins: 2
                                            fillMode: Image.PreserveAspectCrop
                                            source: modelData.thumb || ""
                                            asynchronous: true
                                            cache: true
                                            smooth: false
                                            visible: status === Image.Ready
                                        }
                                        Rectangle {
                                            anchors.fill: parent
                                            color: Theme.surfaceAlt
                                            visible: thumbImg.status !== Image.Ready
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.faceCount > 0 ? "👤×" + modelData.faceCount : "?"
                                                font.pixelSize: 18
                                                color: Theme.textDim
                                            }
                                        }
                                        Text {
                                            visible: modelData.rating > 0
                                            anchors.bottom: parent.bottom
                                            anchors.left: parent.left
                                            anchors.margins: 4
                                            text: "★".repeat(modelData.rating)
                                            font.pixelSize: 10
                                            color: "#f5c842"
                                            style: Text.Outline
                                            styleColor: "black"
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.photoClicked(modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        id: emptyText
                        visible: false
                        width: parent.width
                        text: I18n.tr("这一天还没有往年拍下的照片～\n换一天试试，或先扫描更多照片。")
                        horizontalAlignment: Text.AlignHCenter
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.textDim
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
