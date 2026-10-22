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

/* 重复照片视图：按组展示（主 + 冗余），仅报告不删除 */
Item {
    id: root

    signal photoClicked(int photoId, var ids)

    /* 0.5.36：分组排序（0=检测顺序；1=冗余张数多→少） */
    property int sortMode: 0

    function refresh() {
        groupsModel.clear()
        /* 0.5.35：QML ListModel 的嵌套数组 role 跨 delegate 访问会得到 undefined
           （members 丢失），role 一律存 JSON 字符串，delegate 内解析 */
        var arr = JSON.parse(LibraryBridge.duplicatesJson(6))
        if (root.sortMode === 1)
            arr = arr.slice().sort(function (a, b) { return (b.duplicates || 0) - (a.duplicates || 0) })
        dupCountText.text = arr.length + I18n.tr(" 组")
        for (var i = 0; i < arr.length; ++i)
            groupsModel.append({
                "duplicates": arr[i].duplicates,
                "membersJson": JSON.stringify(arr[i].members)
            })
    }

    ListModel { id: groupsModel }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Text {
                text: I18n.tr("重复照片")
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                id: dupCountText
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Item { Layout.fillWidth: true; width: 10 }
            PMButton {
                objectName: "dupSortBtn"
                tooltip: I18n.tr("切换重复组排序（检测顺序/冗余张数）")
                text: I18n.tr("排序 ▾")
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                Menu {
                    id: dupSortMenu
                    MenuItem { text: I18n.tr("检测顺序"); checkable: true; checked: root.sortMode === 0
                               onTriggered: { root.sortMode = 0; root.refresh() } }
                    MenuItem { text: I18n.tr("按冗余张数（多→少）"); checkable: true; checked: root.sortMode === 1
                               onTriggered: { root.sortMode = 1; root.refresh() } }
                }
                onClicked: dupSortMenu.popup(this, 0, height + 2)
            }
            Text {
                text: I18n.tr("仅报告，不删除 · 未计算的感知哈希可在工具中心一键补齐")
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall
            clip: true
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
            model: groupsModel

            delegate: Rectangle {
                id: groupCard
                /* role 存的是 membersJson 字符串，这里解析为组员数组 */
                property var members: JSON.parse(model.membersJson)

                width: ListView.view.width
                /* 0.5.28：此前无高度（默认0），内容溢出导致组与组重叠、字看不清 */
                height: groupCol.implicitHeight + Theme.spacingSmall * 2
                radius: Theme.radiusMedium
                color: Theme.surface
                border.width: 1
                border.color: Theme.divider

                Column {
                    id: groupCol
                    x: Theme.spacingSmall
                    y: Theme.spacingSmall
                    width: parent.width - Theme.spacingSmall * 2
                    spacing: 6

                    Row {
                        spacing: 6
                        Text {
                            text: model.duplicates + I18n.tr(" 张冗余")
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: Theme.accent
                        }
                        Text {
                            /* 0.5.36：model.members 越过 delegate 属性直查 model role
                               得 undefined（既有 TypeError 噪音），改走 groupCard.members */
                            text: I18n.tr("（组内 ") + groupCard.members.length + I18n.tr(" 张）")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }

                    /* 0.5.35：弃用 delegate 内嵌 ListModel（其 Component.onCompleted
                       上下文里 model 解析不到 delegate 角色，导致 memberModel 恒空、
                       内层列表无 chip 可点）；改 int model + 索引直读组数据 */
                    ListView {
                        width: parent.width
                        height: 120
                        orientation: ListView.Horizontal
                        spacing: 6
                        clip: true
                        ScrollBar.horizontal: PMScrollBar { policy: ScrollBar.AsNeeded }
                        model: groupCard.members.length

                        delegate: Rectangle {
                            property var m: groupCard.members[index]

                            width: 150
                            height: 120
                            radius: Theme.radiusMedium
                            border.width: 1
                            border.color: m.primary ? Theme.primary : Theme.divider
                            color: Theme.bg

                            Column {
                                anchors.fill: parent
                                anchors.margins: 4
                                spacing: 3
                                Image {
                                    width: 142
                                    height: 78
                                    fillMode: Image.PreserveAspectFit
                                    source: m.thumb ? "file:///" + m.thumb.replace(/\\/g, "/") : ""
                                }
                                Text {
                                    width: parent.width
                                    text: (m.primary ? I18n.tr("主 ") : I18n.tr("冗余 ")) + m.name
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 12
                                    color: m.primary ? Theme.primary : Theme.text
                                    elide: Text.ElideMiddle
                                }
                                Text {
                                    width: parent.width
                                    text: m.width + "x" + m.height + "  " + m.takenAt
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 10
                                    color: Theme.textDim
                                    elide: Text.ElideMiddle
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    /* 0.5.28：把组内全部 id 作为上下文传给大图查看器 */
                                    var ids = []
                                    for (var i = 0; i < groupCard.members.length; ++i)
                                        ids.push(groupCard.members[i].id)
                                    root.photoClicked(m.id, ids)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
