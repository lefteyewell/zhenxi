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

/* 已标地点面板（0.7.8c 自地图页中栏迁至右栏，地图页时顶替照片信息栏）。
   列出用户自标地名 + 照片数 + 文件夹数，点击定位到该坐标并打开照片。
   数据只来自 place_labels（用户确认过的名字），绝不自动显示数据产地名。 */
Rectangle {
    id: root
    objectName: "mapPlacePanel"

    color: Theme.surfaceAlt
    radius: Theme.radiusLarge

    signal placeClicked(real lat, real lon, string label)

    /* 0.7.8d：视野过滤。null = 尚未收到地图页通知（显示全部）；
       数组 = 只显示 key（"lat,lon"）在其中的标注，随地图旋转/缩放自动更新 */
    property var visibleKeys: null

    ListModel { id: placeModel }
    property var _allPlaces: []   // 全量标注数据（含视野外），过滤前缓存

    function rebuild() {
        placeModel.clear()
        for (var i = 0; i < _allPlaces.length; ++i) {
            var p = _allPlaces[i]
            if (visibleKeys !== null && visibleKeys.indexOf(p.key) < 0)
                continue
            placeModel.append({ lat: p.lat, lon: p.lon, label: p.label,
                                photoCount: p.photoCount,
                                folderCount: p.folderCount })
        }
    }

    function refresh() {
        var places = []
        try {
            places = JSON.parse(LibraryBridge.mapPlaceList() || "[]")
        } catch (e) {
            console.warn("mapPlaceList 解析失败:", e)
            places = []
        }
        _allPlaces = []
        for (var i = 0; i < places.length; ++i)
            _allPlaces.push({
                lat: places[i][0], lon: places[i][1], label: places[i][2],
                photoCount: places[i][3],
                folderCount: places[i][4] !== undefined ? places[i][4] : 0,
                key: places[i][0].toFixed(3) + "," + places[i][1].toFixed(3)
            })
        rebuild()
    }

    function setKeys(keys) {
        visibleKeys = keys
        rebuild()
    }

    Component.onCompleted: refresh()
    Connections {
        target: LibraryBridge
        function onMapLabelsChanged() { root.refresh() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingSmall
        spacing: Theme.spacingSmall

        Text {
            Layout.fillWidth: true
            text: I18n.tr("已标地点")
            font.family: Theme.fontFamily
            font.pixelSize: 14
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Text {
            Layout.fillWidth: true
            visible: placeModel.count === 0
            text: visibleKeys === null
                  ? I18n.tr("还没有已标注的地名。在地图上选中点后点「标注地名」即可添加")
                  : I18n.tr("当前视野内没有已标地点（旋转或缩放地图可查看其他地点）")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
        ListView {
            id: placeList
            objectName: "mapPlaceList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: placeModel
            clip: true
            spacing: 2
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
            delegate: ItemDelegate {
                width: placeList.width
                height: 46
                onClicked: root.placeClicked(model.lat, model.lon, model.label)
                contentItem: ColumnLayout {
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: model.label
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: Theme.text
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        text: model.photoCount + I18n.tr(" 张照片 · ")
                              + model.folderCount + I18n.tr(" 个文件夹")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                    }
                }
            }
        }
    }
}
