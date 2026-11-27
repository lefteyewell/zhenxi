/* PhotoManager - 照片管理系统
 * Copyright (C) 2026 蒙汗药
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License at
 *
 *     http://www.gnu.org/licenses/gpl-3.0.html
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

/* 球面 GPS 散点图（0.7.8）：纯 Canvas 正交投影，无瓦片、离线、不联网。
   - 拖拽旋转地球（yaw 经度 / pitch 纬度）；滚轮缩放（半径放大=看局部）
   - 屏幕空间分级聚合：密集点合并成一个大点，点击进该处照片图库
   - 地名只显示用户自己标注的（place_labels 表），绝不自动标注 GeoNames
   合规：不画任何国界/行政区划/底图，仅经纬网格 + 照片点 + 用户文字。 */
Item {
    id: root
    objectName: "mapPage"

    signal locationClicked(double lat, double lon)
    /* 聚合点点击：整组坐标 [{lat,lon}...] + 显示名（打开整组照片，不是只代表点） */
    signal coordsClicked(var coords, string label)
    /* 0.7.8d：当前视野内可见的已标地名 key 列表（"lat,lon"），供右栏
       已标地点面板做视野过滤（转到背面/视野外的标注不列出） */
    signal visibleKeysChanged(var keys)

    property string selectedPlace: ""
    property string selectedStats: ""       // 选中点的照片/文件夹数（0.7.8b）
    property var _pts: []            // 原始聚合点 [{lat, lon, count}]
    property var _labels: ({})       // "lat,lon" -> 用户标注文字
    property var _clusters: []       // 屏幕聚合 [{x, y, lat, lon, count, label}]
    property real _yaw: 0            // 视角中心经度（度）
    property real _pitch: 20         // 视角中心纬度（度）
    property real _zoom: 1.0         // 缩放（1=整球入画）
    readonly property real _minZoom: 0.7
    readonly property real _maxZoom: 2048.0  /* 0.7.8c：真实库最近两点仅约 140m
        （0.0013°），64× 下相距不足 1px 无法区分；10px 分辨需 ~1348×，上限 2048 */
    property int _selected: -1
    /* 0.7.8d：选中的代表点坐标——_selected 只是聚合数组下标，每次旋转
       都会重新聚合、数组顺序随网格划分变化，按下标跟踪会"选中点漂移
       到别的点"；按坐标身份跟踪，重聚合后在 _recluster 里重定位 */
    property var _selRep: null       // {lat, lon}
    property string suggestedName: ""       // 点选位置的离线建议地名（仅作输入辅助）
    property real _lastMouseX: -1           // 按钮缩放的锚点（最后鼠标位置）
    property real _lastMouseY: -1
    property real _dragX: 0
    property real _dragY: 0
    property bool _dragging: false
    property real _dragDist: 0
    readonly property real _radius: Math.min(mapCanvas.width, mapCanvas.height) * 0.46 * _zoom

    ListModel { id: model }

    /* 只重载用户标注：保存/清除标注时不能重置视角（否则用户转到某地标注后
       视角弹回全球）——与 refresh() 的「进入页面重置」分开。
       0.7.8c：地点列表面板已迁至右栏（MapPlacePanel 顶替信息栏），此处只刷点旁文字 */
    function _reloadLabels() {
        var raw = JSON.parse(LibraryBridge.mapLabels() || "[]")
        var m = {}
        for (var k = 0; k < raw.length; ++k)
            m[raw[k][0].toFixed(3) + "," + raw[k][1].toFixed(3)] = raw[k][2]
        _labels = m
        _recluster()
    }

    /* 右栏地点面板点击：转到该坐标视角并打开整组照片（经 coordsClicked） */
    function focusPlace(lat, lon, label) {
        _yaw = lon
        _pitch = Math.max(-85, Math.min(85, lat))
        _zoom = Math.max(_zoom, 2.0)
        _recluster()
        coordsClicked([{ lat: lat, lon: lon }], label)
    }

    function refresh() {
        _pts = LibraryBridge.mapPoints()
        _reloadLabels()
        countText.text = _pts.length + I18n.tr(" 个地点 · ") + LibraryBridge.mapCount() + I18n.tr(" 张照片")
        selectedPlace = ""
        selectedStats = ""
        _selected = -1
        _selRep = null
        _yaw = 0; _pitch = 20; _zoom = 1.0
        model.clear()
        for (var i = 0; i < _pts.length; ++i) model.append(_pts[i])
        _recluster()
    }

    /* 0.7.8d：从图库返回进入（navBack）——刷新数据但保留视角/缩放/选中，
       用户应精确回到点击条目离开时的视图，而不是弹回全球视角 */
    function reloadKeepView() {
        _pts = LibraryBridge.mapPoints()
        _reloadLabels()
        countText.text = _pts.length + I18n.tr(" 个地点 · ") + LibraryBridge.mapCount() + I18n.tr(" 张照片")
        model.clear()
        for (var i = 0; i < _pts.length; ++i) model.append(_pts[i])
        _recluster()   // _remapSelection 按坐标身份找回选中簇
    }

    /* 正交投影：把 (lat, lon) 映射到画布坐标；背面返回 null。
       yaw/pitch 是视角中心（经度/纬度），先绕 Y 转经度、再绕 X 转纬度。 */
    function _project(lat, lon, w, h) {
        var phi = lat * Math.PI / 180
        var lam = (lon - _yaw) * Math.PI / 180
        var p0 = _pitch * Math.PI / 180
        var cp = Math.cos(p0), sp = Math.sin(p0)
        var cl = Math.cos(phi), sl = Math.sin(phi)
        /* 旋转后的 Z（朝观察者为正） */
        var z = sl * sp + cl * cp * Math.cos(lam)
        if (z <= 0) return null
        var x = cl * Math.sin(lam)
        var y = cp * sl - sp * cl * Math.cos(lam)
        var r = Math.min(w, h) * 0.46 * _zoom
        return { x: w / 2 + x * r, y: h / 2 - y * r }
    }

    /* 鼠标锚定缩放：缩放前后鼠标所指的球面点不动。
       正交投影下用逆投影求鼠标处经纬，缩放后反解 yaw/pitch 使其投影回同一屏幕点。 */
    function _zoomAt(mx, my, factor) {
        var w = mapCanvas.width, h = mapCanvas.height
        if (w <= 0 || h <= 0) return
        var oldZ = _zoom
        var newZ = Math.max(_minZoom, Math.min(_maxZoom, oldZ * factor))
        if (Math.abs(newZ - oldZ) < 0.0001) return
        var cx = w / 2, cy = h / 2
        var rOld = Math.min(w, h) * 0.46 * oldZ
        var nx = (mx - cx) / rOld
        var ny = -(my - cy) / rOld
        var n2 = nx * nx + ny * ny
        if (n2 >= 0.999) {           // 鼠标在球外：无锚点，直接缩放
            _zoom = newZ; _recluster(); return
        }
        var nz = Math.sqrt(1 - n2)
        /* 相机坐标 → 经纬：与 _project 严格互逆
           lat = asin(cp*ny + sp*nz)；lon-yaw = atan2(nx, -sp*ny + cp*nz) */
        var p0 = _pitch * Math.PI / 180
        var cp = Math.cos(p0), sp = Math.sin(p0)
        var lat = Math.asin(Math.max(-1, Math.min(1, cp * ny + sp * nz)))
        var lon = Math.atan2(nx, -sp * ny + cp * nz) * 180 / Math.PI + _yaw
        /* 缩放后：求 yaw/pitch 使该经纬投影到同一 (mx,my) */
        var rNew = Math.min(w, h) * 0.46 * newZ
        var nnx = (mx - cx) / rNew
        var nny = -(my - cy) / rNew
        var nn2 = nnx * nnx + nny * nny
        if (nn2 >= 0.999) {          // 缩放后该点超出球面：退回球心锚定
            _zoom = newZ; _recluster(); return
        }
        var nnz = Math.sqrt(1 - nn2)
        var cl = Math.cos(lat)
        if (Math.abs(cl) < 1e-6) { _zoom = newZ; _recluster(); return }
        /* nnx = cos(lat)·sin(lon-yaw') → 两解取与当前 yaw 接近者 */
        var lam = Math.asin(Math.max(-1, Math.min(1, nnx / cl)))
        var yawA = lon - lam * 180 / Math.PI
        var yawB = lon - (180 - lam * 180 / Math.PI)
        var diffA = Math.abs(Math.atan2(Math.sin((yawA - _yaw) * Math.PI / 180),
                                        Math.cos((yawA - _yaw) * Math.PI / 180)))
        var diffB = Math.abs(Math.atan2(Math.sin((yawB - _yaw) * Math.PI / 180),
                                        Math.cos((yawB - _yaw) * Math.PI / 180)))
        var yawNew = diffA <= diffB ? yawA : yawB
        var lamP = (lon - yawNew) * Math.PI / 180
        var pitchNew = Math.atan2(nnz, nny) - Math.atan2(cl * Math.cos(lamP), Math.sin(lat))
        _yaw = yawNew
        _pitch = Math.max(-85, Math.min(85, pitchNew * 180 / Math.PI))
        _zoom = newZ
        _recluster()
    }

    /* 屏幕空间网格分桶： zoom 越大桶越小 → 放大后自动展开密集点 */
    function _recluster() {
        var w = mapCanvas.width, h = mapCanvas.height
        if (w <= 0 || h <= 0) return
        var cell = Math.max(10, Math.min(40, 26 / _zoom))
        var buckets = {}
        var out = []
        for (var i = 0; i < _pts.length; ++i) {
            var p = _pts[i]
            var xy = _project(p.lat, p.lon, w, h)
            if (!xy) continue
            var gx = Math.floor(xy.x / cell), gy = Math.floor(xy.y / cell)
            var key = gx + ":" + gy
            var b = buckets[key]
            if (!b) {
                b = { sx: 0, sy: 0, n: 0, count: 0, lat: p.lat, lon: p.lon,
                      label: _labels[p.lat.toFixed(3) + "," + p.lon.toFixed(3)] || p.autoName || "",
                      autoName: p.autoName || "",
                      members: [] }
                buckets[key] = b
                out.push(b)
            }
            b.members.push({ lat: p.lat, lon: p.lon })
            b.sx += xy.x; b.sy += xy.y; b.n += 1; b.count += p.count
            var lab = _labels[p.lat.toFixed(3) + "," + p.lon.toFixed(3)]
            if (lab) b.label = lab
        }
        for (var j = 0; j < out.length; ++j) {
            out[j].x = out[j].sx / out[j].n
            out[j].y = out[j].sy / out[j].n
        }
        /* 合并"大点套小点"：不同网格桶的中心可能近到圆重叠，二次合并。
           合并半径按点数估算（点半径 3+8*sqrt(count/maxC)，取保守 10px）。 */
        var maxC0 = 1
        for (var q = 0; q < out.length; ++q) maxC0 = Math.max(maxC0, out[q].count)
        var merged = []
        for (var i2 = 0; i2 < out.length; ++i2) {
            var c = out[i2]
            var target = -1
            for (var k = 0; k < merged.length; ++k) {
                var m = merged[k]
                var rc = 3 + 8 * Math.sqrt(c.count / maxC0)
                var rm = 3 + 8 * Math.sqrt(m.count / maxC0)
                if (Math.abs(c.x - m.x) < (rc + rm) * 0.6 &&
                    Math.abs(c.y - m.y) < (rc + rm) * 0.6) { target = k; break }
            }
            if (target < 0) { merged.push(c); continue }
            var mm = merged[target]
            for (var t = 0; t < c.members.length; ++t) mm.members.push(c.members[t])
            var tot = mm.count + c.count
            mm.x = (mm.x * mm.count + c.x * c.count) / tot
            mm.y = (mm.y * mm.count + c.y * c.count) / tot
            mm.count = tot
            if (!mm.label && c.label) mm.label = c.label
            if (!mm.autoName && c.autoName) mm.autoName = c.autoName
        }
        _clusters = merged
        _remapSelection()
        mapCanvas.requestPaint()
        _emitVisibleKeys()
    }

    /* 已标地名中落在当前可见范围（正面半球 + 画布外扩 60px）的 key 列表 */
    function _emitVisibleKeys() {
        var w = mapCanvas.width, h = mapCanvas.height
        if (w <= 0 || h <= 0) return
        var out = []
        for (var key in _labels) {
            var parts = key.split(",")
            var xy = _project(parseFloat(parts[0]), parseFloat(parts[1]), w, h)
            if (!xy) continue
            if (xy.x < -60 || xy.x > w + 60 || xy.y < -60 || xy.y > h + 60)
                continue
            out.push(key)
        }
        visibleKeysChanged(out)
    }

    /* 画一条基准线（经线或纬线）：按可见性分段，背面断开，
       绝不把不连续的两段用 lineTo 连起来（否则横跨隐藏半球成直线）。
       samples: [{lat, lon}...]；label 标在最长可见段的中点。 */
    function _drawReferenceLine(ctx, w, h, samples, label) {
        var segments = []
        var cur = []
        for (var i = 0; i < samples.length; ++i) {
            var q = _project(samples[i].lat, samples[i].lon, w, h)
            if (q) { cur.push(q); continue }
            if (cur.length > 1) segments.push(cur)
            cur = []
        }
        if (cur.length > 1) segments.push(cur)
        if (segments.length === 0) return
        var best = segments[0]
        for (var s = 1; s < segments.length; ++s)
            if (segments[s].length > best.length) best = segments[s]
        ctx.lineWidth = 1.6
        ctx.strokeStyle = Theme.accent
        for (var k = 0; k < segments.length; ++k) {
            var seg = segments[k]
            ctx.beginPath()
            ctx.moveTo(seg[0].x, seg[0].y)
            for (var j = 1; j < seg.length; ++j) ctx.lineTo(seg[j].x, seg[j].y)
            ctx.stroke()
        }
        var mid = best[Math.floor(best.length / 2)]
        ctx.font = "11px " + Theme.fontFamily
        ctx.fillStyle = Theme.accent
        ctx.fillText(label, mid.x + 5, mid.y - 4)
    }

    function _drawGraticule(ctx, w, h) {
        var r = Math.min(w, h) * 0.46 * _zoom
        var cx = w / 2, cy = h / 2
        ctx.lineWidth = 0.7
        ctx.strokeStyle = Theme.divider
        /* 球体轮廓 */
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.stroke()
        /* 经线：每 30° */
        for (var lon = -180; lon < 180; lon += 30) {
            var started = false
            for (var lat = -90; lat <= 90; lat += 5) {
                var q = _project(lat, lon, w, h)
                if (q) {
                    if (!started) { ctx.beginPath(); ctx.moveTo(q.x, q.y); started = true }
                    else ctx.lineTo(q.x, q.y)
                } else if (started) { ctx.stroke(); started = false }
            }
            if (started) ctx.stroke()
        }
        /* 纬线：每 30° */
        for (var la = -60; la <= 60; la += 30) {
            var started2 = false
            for (var lo = -180; lo <= 180; lo += 5) {
                var q2 = _project(la, lo, w, h)
                if (q2) {
                    if (!started2) { ctx.beginPath(); ctx.moveTo(q2.x, q2.y); started2 = true }
                    else ctx.lineTo(q2.x, q2.y)
                } else if (started2) { ctx.stroke(); started2 = false }
            }
            if (started2) ctx.stroke()
        }

        /* 基准线：0° 经线 / 180° 经线 / 赤道（0° 纬线）。
           只画数学参考线，不涉及任何国界/行政区划。 */
        var mer0 = [], mer180 = [], equator = []
        for (var lat0 = -90; lat0 <= 90; lat0 += 3) {
            mer0.push({ lat: lat0, lon: 0 })
            mer180.push({ lat: lat0, lon: 180 })
        }
        for (var lon0 = -180; lon0 <= 180; lon0 += 3)
            equator.push({ lat: 0, lon: lon0 })
        _drawReferenceLine(ctx, w, h, mer0, I18n.tr("0° 经线"))
        _drawReferenceLine(ctx, w, h, mer180, I18n.tr("180° 经线"))
        _drawReferenceLine(ctx, w, h, equator, I18n.tr("0° 纬线（赤道）"))
    }

    /* 点选命中：阈值随点大小；选中后可标注 / 看照片 */
    function _pick(mx, my) {
        var best = -1, bestD = 20 * 20
        for (var i = 0; i < _clusters.length; ++i) {
            var c = _clusters[i]
            var dx = mx - c.x, dy = my - c.y
            var d = dx * dx + dy * dy
            if (d < bestD) { bestD = d; best = i }
        }
        _selected = best
        if (best >= 0) {
            var hit = _clusters[best]
            _selRep = { lat: hit.lat, lon: hit.lon }
            selectedPlace = hit.label || hit.autoName
                    || hit.lat.toFixed(2) + "°, " + hit.lon.toFixed(2) + "°"
            /* 选中点统计（0.7.8b）：整组成员的照片数 + 文件夹数 */
            var coords = hit.members && hit.members.length
                    ? hit.members : [{ lat: hit.lat, lon: hit.lon }]
            var st = JSON.parse(LibraryBridge.mapCoordsStats(
                                JSON.stringify(coords)) || "{}")
            selectedStats = (st.photos !== undefined)
                    ? coords.length + I18n.tr(" 个地点 · ")
                      + st.photos + I18n.tr(" 张照片 · ") + st.folders
                      + I18n.tr(" 个文件夹") : ""
        } else {
            _selRep = null
            selectedPlace = ""
            selectedStats = ""
        }
        mapCanvas.requestPaint()
    }

    /* 重聚合后按 _selRep 坐标找回选中簇（旋转/缩放导致数组顺序变化时
       选中高亮不漂移）；选中点转到背面不在列表里时暂时无高亮，
       转回来即恢复 */
    function _remapSelection() {
        if (!_selRep) { _selected = -1; return }
        _selected = -1
        for (var s = 0; s < _clusters.length; ++s) {
            var mem = _clusters[s].members
            for (var t = 0; mem && t < mem.length; ++t)
                if (mem[t].lat === _selRep.lat && mem[t].lon === _selRep.lon) {
                    _selected = s
                    return
                }
        }
    }

    Connections {
        target: LibraryBridge
        function onMapLabelsChanged() { _reloadLabels() }
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
            Text {
                text: selectedStats
                visible: selectedStats !== ""
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
                    if (_pts.length === 0) return
                    root._drawGraticule(ctx, width, height)
                    var maxC = 1
                    for (var m = 0; m < _clusters.length; ++m)
                        maxC = Math.max(maxC, _clusters[m].count)
                    for (var i = 0; i < _clusters.length; ++i) {
                        var c = _clusters[i]
                        var r = 3 + 8 * Math.sqrt(c.count / maxC)
                        var isSel = (i === _selected)
                        ctx.beginPath()
                        ctx.arc(c.x, c.y, r + (isSel ? 3 : 0), 0, Math.PI * 2)
                        ctx.fillStyle = isSel ? "rgba(60, 160, 190, 0.75)" : "rgba(220, 120, 60, 0.55)"
                        ctx.fill()
                        ctx.lineWidth = isSel ? 2.5 : 1.5
                        ctx.strokeStyle = isSel ? "#1B6E86" : "rgba(160, 70, 20, 0.9)"
                        ctx.stroke()
                        /* 聚合点提示（0.7.8b）：一处点含多个坐标时标「N处·M张」，
                           否则全球视角下同城邻近点被合并会误以为丢点了 */
                        if (c.members && c.members.length > 1) {
                            ctx.font = "10px " + Theme.fontFamily
                            ctx.fillStyle = Theme.textDim
                            ctx.fillText(c.members.length + I18n.tr(" 处 · ")
                                         + c.count + I18n.tr(" 张"),
                                         c.x + r + 4, c.y - 6)
                        }
                        if (c.label) {
                            ctx.font = "12px " + Theme.fontFamily
                            ctx.fillStyle = Theme.text
                            ctx.fillText(c.label,
                                         c.x + r + 4,
                                         c.y + (c.members && c.members.length > 1 ? 10 : 4))
                        }
                    }
                }
            }

            MouseArea {
                id: mapMouse
                objectName: "mapMouse"
                anchors.fill: mapCanvas
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    _dragging = true
                    _dragX = mouse.x; _dragY = mouse.y; _dragDist = 0
                    mouse.accepted = true
                }
                onPositionChanged: {
                    _lastMouseX = mouse.x; _lastMouseY = mouse.y
                    if (!_dragging) return
                    var dx = mouse.x - _dragX
                    var dy = mouse.y - _dragY
                    _dragDist += Math.abs(dx) + Math.abs(dy)
                    root._yaw -= dx * 0.32 / root._zoom
                    root._pitch = Math.max(-85, Math.min(85, root._pitch + dy * 0.32 / root._zoom))
                    _dragX = mouse.x; _dragY = mouse.y
                    root._recluster()
                }
                onReleased: {
                    var wasDrag = _dragDist > 6
                    _dragging = false
                    if (!wasDrag) root._pick(mouse.x, mouse.y)
                }
                onWheel: {
                    /* Qt Quick 的滚轮事件对象叫 wheel（x/y/angleDelta），
                       不是 mouse——用错会得到 undefined → 缩放失效 */
                    _lastMouseX = wheel.x; _lastMouseY = wheel.y
                    root._zoomAt(wheel.x, wheel.y,
                                 wheel.angleDelta.y > 0 ? 1.25 : 1 / 1.25)
                    wheel.accepted = true
                }
            }

            Text {
                anchors.centerIn: parent
                visible: _pts.length === 0
                text: I18n.tr("暂无带 GPS 坐标的照片（先扫描并提取 EXIF）")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
            }

            RowLayout {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: Theme.spacingSmall
                spacing: Theme.spacingSmall
                PMButton {
                    objectName: "mapZoomInBtn"
                    text: "+"
                    width: 34; height: 30
                    tooltip: I18n.tr("放大（也可滚轮）")
                    onClicked: {
                        var ax = _lastMouseX >= 0 ? _lastMouseX : mapCanvas.width / 2
                        var ay = _lastMouseY >= 0 ? _lastMouseY : mapCanvas.height / 2
                        root._zoomAt(ax, ay, 1.5)
                    }
                }
                PMButton {
                    objectName: "mapZoomOutBtn"
                    text: "−"
                    width: 34; height: 30
                    tooltip: I18n.tr("缩小（也可滚轮）")
                    onClicked: {
                        var ax = _lastMouseX >= 0 ? _lastMouseX : mapCanvas.width / 2
                        var ay = _lastMouseY >= 0 ? _lastMouseY : mapCanvas.height / 2
                        root._zoomAt(ax, ay, 1 / 1.5)
                    }
                }
                Text {
                    objectName: "mapZoomLabel"
                    text: I18n.tr("放大 ")
                          + (root._zoom >= 100 ? Math.round(root._zoom)
                                               : root._zoom.toFixed(1)) + "×"
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                    anchors.verticalCenter: parent.verticalCenter
                    Layout.preferredWidth: 88
                }
                PMButton {
                    objectName: "mapResetBtn"
                    text: I18n.tr("重置")
                    height: 30
                    tooltip: I18n.tr("回到全球视角")
                    onClicked: {
                        root._yaw = 0; root._pitch = 20; root._zoom = 1.0
                        root._selected = -1; root._selRep = null
                        selectedPlace = ""; selectedStats = ""
                        _lastMouseX = -1; _lastMouseY = -1
                        root._recluster()
                    }
                }
                PMButton {
                    objectName: "mapLabelBtn"
                    text: I18n.tr("标注地名")
                    height: 30
                    enabled: _selected >= 0
                    tooltip: I18n.tr("给选中位置写地名；可一键采用离线数据的建议名")
                    onClicked: {
                        var c = _clusters[_selected]
                        labelField.text = c.label || ""
                        /* 建议名：离线逆地理编码（显示层已做本地化映射）*/
                        suggestedName = LibraryBridge.reverseGeocode(c.lat, c.lon) || ""
                        labelDialog.open()
                    }
                }
                PMButton {
                    objectName: "mapOpenBtn"
                    text: I18n.tr("查看照片")
                    height: 30
                    enabled: _selected >= 0
                    tooltip: I18n.tr("打开选中位置的照片")
                    onClicked: {
                        var c = _clusters[_selected]
                        root.coordsClicked(c.members && c.members.length ? c.members
                                                                        : [{ lat: c.lat, lon: c.lon }],
                                           c.label || "")
                    }
                }
                Text {
                    text: I18n.tr("拖动旋转 · 滚轮缩放 · 点击选点")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }

    /* 用户自标地名输入（Popup contentItem 必须 ColumnLayout） */
    Popup {
        id: labelDialog
        objectName: "mapLabelDialog"
        modal: true
        closePolicy: Popup.CloseOnEscape
        width: Math.min(400, root.width - 40)
        x: (root.width - width) / 2
        y: (root.height - height) / 2
        padding: Theme.spacingMedium
        background: Rectangle {
            radius: Theme.radiusLarge
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider
        }
        contentItem: ColumnLayout {
            spacing: Theme.spacingMedium
            Text {
                text: I18n.tr("标注地名")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                text: I18n.tr("只有你确认的名字才会显示；留空则删除标注。")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSmall
                Text {
                    Layout.fillWidth: true
                    text: suggestedName !== ""
                          ? I18n.tr("建议：") + suggestedName
                          : I18n.tr("无可用的建议地名")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: suggestedName !== "" ? Theme.accent : Theme.textDim
                    wrapMode: Text.Wrap
                }
                PMButton {
                    objectName: "mapAdoptBtn"
                    text: I18n.tr("采用")
                    height: 28
                    enabled: suggestedName !== ""
                    tooltip: I18n.tr("采用建议名作为我的标注")
                    onClicked: labelField.text = suggestedName
                }
            }
            TextField {
                id: labelField
                objectName: "mapLabelField"
                Layout.fillWidth: true
                placeholderText: I18n.tr("输入地名，如：老家的院子")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.text
                onAccepted: labelSaveBtn.clicked()
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSmall
                Item { Layout.fillWidth: true }
                PMButton {
                    text: I18n.tr("取消")
                    height: 30
                    onClicked: labelDialog.close()
                }
                PMButton {
                    id: labelSaveBtn
                    objectName: "mapLabelSaveBtn"
                    text: I18n.tr("保存")
                    height: 30
                    onClicked: {
                        if (_selected < 0) { labelDialog.close(); return }
                        var c = _clusters[_selected]
                        LibraryBridge.setMapLabel(c.lat, c.lon, labelField.text)
                        labelDialog.close()
                    }
                }
            }
        }
    }
}
