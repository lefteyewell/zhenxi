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

/* 事件视图：时间聚类结果卡片列表，点击进入事件照片 */
Item {
    id: root

    signal eventClicked(int eventId)

    ListModel { id: eventsModel }

    /* 0.5.36：排序（0=日期新→旧，后端默认序；1=照片数多→少；2=名称） */
    property int sortMode: 0

    function refresh() {
        eventsModel.clear()
        var arr = LibraryBridge.events()
        if (root.sortMode === 1)
            arr = arr.slice().sort(function (a, b) { return (b.photoCount || 0) - (a.photoCount || 0) })
        else if (root.sortMode === 2)
            arr = arr.slice().sort(function (a, b) {
                return String(a.title || a.startAt || "").localeCompare(
                       String(b.title || b.startAt || ""), "zh")
            })
        for (var i = 0; i < arr.length; ++i) {
            var it = arr[i]
            if (it.lat === undefined) it.lat = 0
            if (it.lon === undefined) it.lon = 0
            eventsModel.append(it)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            Layout.leftMargin: Theme.spacingMedium
            rightPadding: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: I18n.tr("事件（按拍摄时间聚类）")
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true; width: 10 }
            PMButton {
                objectName: "eventSortBtn"
                tooltip: I18n.tr("选择事件排序方式（日期/照片数/名称）")
                text: I18n.tr("排序 ▾")
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                Menu {
                    id: eventSortMenu
                    MenuItem { text: I18n.tr("按日期（新→旧）"); checkable: true; checked: root.sortMode === 0
                               onTriggered: { root.sortMode = 0; root.refresh() } }
                    MenuItem { text: I18n.tr("按照片数（多→少）"); checkable: true; checked: root.sortMode === 1
                               onTriggered: { root.sortMode = 1; root.refresh() } }
                    MenuItem { text: I18n.tr("按名称（A→Z）"); checkable: true; checked: root.sortMode === 2
                               onTriggered: { root.sortMode = 2; root.refresh() } }
                }
                onClicked: eventSortMenu.popup(this, 0, height + 2)
            }
        }

        ListView {
            objectName: "eventList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall
            clip: true
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
            model: eventsModel

            delegate: Rectangle {
                width: ListView.view.width
                height: 64
                radius: Theme.radiusMedium
                color: Theme.surface
                border.width: 1
                border.color: Theme.divider

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.eventClicked(model.id)
                    cursorShape: Qt.PointingHandCursor
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingMedium

                    Rectangle {
                        width: 42
                        height: 42
                        radius: Theme.radiusMedium
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: Theme.primary }
                            GradientStop { position: 1.0; color: Theme.accent }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: model.photoCount
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "white"
                        }
                    }
                    Column {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            text: model.title || model.startAt
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: Theme.text
                            elide: Text.ElideRight
                            width: parent.width
                        }
                        Text {
                            text: model.startAt + (model.endAt !== model.startAt ? " ~ " + model.endAt : "") +
                                  (model.lat && model.lon ? "  ·  " + model.lat.toFixed(3) + ", " + model.lon.toFixed(3) : "")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    Text {
                        text: model.photoCount + I18n.tr(" 张")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textDim
                    }
                }
            }
        }
    }
}
