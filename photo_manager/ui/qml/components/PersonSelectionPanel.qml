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

/* 0.7.3：人物页多选的右侧「已选人物」面板——进入选择模式时顶替照片
   信息栏，实时列出已勾选人物（头像 / 名称 / 照片数），行上 ✕ 即取消
   勾选（与网格勾选框双向联动）；退出选择模式由宿主切换回信息栏。
   数据来源：page.selectedIds（CategoryPage 整体替换数组，绑定天然刷新，
   取消勾选的人自动从列表消失）。 */
Rectangle {
    id: root

    color: Theme.surfaceAlt
    radius: Theme.radiusLarge

    /* 宿主人物页（CategoryPage，kind=people）：取人物信息 + 取消勾选 */
    property var page: null
    property var selectedIds: page ? page.selectedIds : []
    onSelectedIdsChanged: _syncModel()
    Component.onCompleted: _syncModel()

    function _syncModel() {
        listModel.clear()
        var p = page
        if (!p)
            return
        for (var i = 0; i < selectedIds.length; ++i) {
            var pid = selectedIds[i]
            var info = p.personInfo ? p.personInfo(pid) : null
            if (info)
                listModel.append(info)
            else
                /* 该人物不在已载入分页（理论上勾选必已渲染，兜底显示）。
                   0.7.3b：兜底名走 bridge 显示口径（名称/界面编号），
                   不再显示「人物 #内部id」——与界面编号对不上 */
                listModel.append({ id: pid,
                                   name: LibraryBridge.personDisplayLabel(pid),
                                   photoCount: 0, avatarSrc: "", avatarW: 0 })
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingSmall
        spacing: Theme.spacingSmall

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            spacing: Theme.spacingSmall

            Text {
                text: I18n.tr("已选人物")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
            Text {
                Layout.alignment: Qt.AlignVCenter
                text: root.selectedIds.length > 0
                      ? I18n.tr("已选 ") + root.selectedIds.length + I18n.tr(" 个人物")
                      : I18n.tr("尚未勾选人物")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
        }

        /* 空态引导 */
        Text {
            visible: listModel.count === 0
            Layout.fillWidth: true
            Layout.topMargin: 40
            horizontalAlignment: Text.AlignHCenter
            text: I18n.tr("点击左侧网格中的人物卡片即可勾选")
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textDim
            wrapMode: Text.Wrap
        }

        ListView {
            id: selList
            objectName: "personSelList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: listModel
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

            delegate: Rectangle {
                width: selList.width
                height: 48
                radius: Theme.radiusMedium
                /* ⚠️ 行 hover 用 HoverHandler 而非 MouseArea：MouseArea 声明在
                   RowLayout（含 ✕ 按钮）之后会盖在上层，无 onClicked 也照样
                   accept 按下事件，✕ 的 onClicked 永远收不到（hover 广播不
                   受影响，故此前「悬停变色正常、点击无效」）；HoverHandler
                   纯探测不抢事件，彻底规避层叠问题（0.7.3 修复） */
                HoverHandler { id: rowHover }
                color: rowHover.hovered ? Theme.hover : Theme.surface
                border.width: 1
                border.color: Theme.divider

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSmall
                    anchors.rightMargin: Theme.spacingSmall
                    spacing: Theme.spacingSmall

                    /* 代表脸头像（同人物网格裁剪口径） */
                    Rectangle {
                        width: 40; height: 40; radius: 20
                        color: Theme.surfaceAlt
                        clip: true
                        property bool hasAv: model.avatarW > 0 && !!model.avatarSrc
                        Image {
                            anchors.fill: parent
                            visible: parent.hasAv
                            source: parent.hasAv
                                    ? "file:///" + String(model.avatarSrc).replace(/\\/g, "/") : ""
                            sourceClipRect: Qt.rect(model.avatarX || 0, model.avatarY || 0,
                                                    model.avatarW || 1, model.avatarH || 1)
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !parent.hasAv
                            text: "◎"
                            font.pixelSize: 18
                        }
                    }

                    Column {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            width: parent.width
                            text: model.name || LibraryBridge.personDisplayLabel(model.id)
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            color: Theme.text
                            elide: Text.ElideMiddle
                        }
                        Text {
                            text: model.photoCount + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                            color: Theme.textDim
                        }
                    }

                    /* ✕ 取消勾选：与网格勾选框同一 toggleSelect 入口，
                       行随绑定自动从本面板消失 */
                    Rectangle {
                        objectName: "personSelRemoveBtn"
                        width: 24; height: 24; radius: 6
                        Layout.alignment: Qt.AlignVCenter
                        color: xma.containsMouse ? Theme.danger : Theme.surfaceAlt
                        border.width: 1
                        border.color: Theme.divider
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            font.pixelSize: 12
                            color: xma.containsMouse ? "#ffffff" : Theme.textDim
                        }
                        ToolTip.visible: xma.containsMouse
                        ToolTip.delay: 500
                        ToolTip.text: I18n.tr("取消勾选该人物")
                        MouseArea {
                            id: xma
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.page)
                                    root.page.toggleSelect(model.id)
                            }
                        }
                    }
                }
            }
        }
    }

    ListModel { id: listModel }
}
