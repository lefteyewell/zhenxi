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

/* GPS 散点地图：无瓦片、离线，把带坐标的照片按经纬度画点。
   点越大照片越多；点击聚合点进入该坐标的照片图库。 */
Item {
    id: root
    objectName: "mapPage"

    signal locationClicked(double lat, double lon)

    property string selectedPlace: ""
    property var _pts: []
    property real _minLat: 0
    property real _maxLat: 0
    property real _minLon: 0
    property real _maxLon: 0
    property real _pad: 0.12

    ListModel { id: model }

    function refresh() {
        _pts = LibraryBridge.mapPoints()
        countText.text = _pts.length + I18n.tr(" 个地点 · ") + LibraryBridge.mapCount() + I18n.tr(" 张照片")
        selectedPlace = ""
        if (_pts.length === 0) {
            model.clear()
            return
        }
        _minLat = _maxLat = _pts[0].lat
        _minLon = _maxLon = _pts[0].lon
        for (var i = 1; i < _pts.length; ++i) {
            _minLat = Math.min(_minLat, _pts[i].lat)
            _maxLat = Math.max(_maxLat, _pts[i].lat)
            _minLon = Math.min(_minLon, _pts[i].lon)
            _maxLon = Math.max(_maxLon, _pts[i].lon)
        }
        var dlat = Math.max((_maxLat - _minLat), 0.0001)
        var dlon = Math.max((_maxLon - _minLon), 0.0001)
        _minLat -= dlat * _pad
        _maxLat += dlat * _pad
        _minLon -= dlon * _pad
        _maxLon += dlon * _pad
        model.clear()
        for (var j = 0; j < _pts.length; ++j)
            model.append(_pts[j])
        mapCanvas.requestPaint()
    }

    function _pxX(lon) { return (lon - _minLon) / (_maxLon - _minLon) * mapCanvas.width }
    function _pxY(lat) { return (1 - (lat - _minLat) / (_maxLat - _minLat)) * mapCanvas.height }

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
                text: I18n.tr("地图")
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
            Text {
                text: selectedPlace
                visible: selectedPlace !== ""
                anchors.verticalCenter: parent.verticalCenter
                leftPadding: Theme.spacingSmall
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: Theme.accent
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
            clip: true

            Canvas {
                id: mapCanvas
                objectName: "mapCanvas"
                anchors.fill: parent
                anchors.margins: Theme.spacingMedium

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.clearRect(0, 0, width, height)
                    if (model.count === 0) return
                    /* 浅色网格（近似经纬度） */
                    ctx.strokeStyle = Theme.divider
                    ctx.lineWidth = 0.5
                    for (var gx = 0; gx < width; gx += 40) {
                        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, height); ctx.stroke()
                    }
                    for (var gy = 0; gy < height; gy += 40) {
                        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke()
                    }
                    var maxC = 1
                    for (var m = 0; m < model.count; ++m)
                        maxC = Math.max(maxC, model.get(m).count)
                    for (var i = 0; i < model.count; ++i) {
                        var p = model.get(i)
                        var x = root._pxX(p.lon)
                        var y = root._pxY(p.lat)
                        var r = 3 + 9 * Math.sqrt(p.count / maxC)
                        ctx.beginPath()
                        ctx.arc(x, y, r, 0, Math.PI * 2)
                        ctx.fillStyle = "rgba(220, 120, 60, 0.55)"
                        ctx.fill()
                        ctx.lineWidth = 1.5
                        ctx.strokeStyle = "rgba(160, 70, 20, 0.9)"
                        ctx.stroke()
                    }
                }
            }

            MouseArea {
                anchors.fill: mapCanvas
                onClicked: {
                    /* 命中最近点（阈值 18px） */
                    var best = -1
                    var bestD = 18 * 18
                    for (var i = 0; i < model.count; ++i) {
                        var p = model.get(i)
                        var dx = mouse.x - root._pxX(p.lon)
                        var dy = mouse.y - root._pxY(p.lat)
                        var d = dx * dx + dy * dy
                        if (d < bestD) { bestD = d; best = i }
                    }
                    if (best >= 0) {
                        var hit = model.get(best)
                        var name = LibraryBridge.reverseGeocode(hit.lat, hit.lon)
                        selectedPlace = (name && name.length > 0) ? name : I18n.tr("（未识别地名）")
                        root.locationClicked(hit.lat, hit.lon)
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: model.count === 0
                text: I18n.tr("暂无带 GPS 坐标的照片（先扫描并提取 EXIF）")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
            }
        }
    }
}