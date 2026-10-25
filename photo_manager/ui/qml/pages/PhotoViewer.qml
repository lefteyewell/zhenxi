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
import QtQuick.Window
import theme 1.0
import components 1.0
import i18n 1.0

/* 大图查看独立窗口：位于屏幕中央，可调整大小。
   显示原图，支持滚轮缩放 / 左键拖动平移 / 双击复位 / Esc 关闭。
   用法：viewer.showPhoto(url, title) */
Window {
    id: root
    objectName: "photoViewer"

    title: I18n.tr("照片预览")
    width: 960
    height: 640
    minimumWidth: 480
    minimumHeight: 400
    color: "#1c1c1e"
    flags: Qt.Window

    property real _scale: 1.0
    property real _baseScale: 1.0
    property real _imgW: 0
    property real _imgH: 0
    property var _ids: []
    property int _index: -1

    /* 胶片条（ACDsee 风格）：默认隐藏，工具栏可切换，避免遮挡大图 */
    property bool filmVisible: false
    ListModel { id: filmModel }
    property bool _slideshow: false
    property int _slideInterval: 4000
    property int _curRating: 0
    property string _curFlag: ""
    property var _faces: []
    property bool _showFaces: false
    signal assignFaceRequested(int faceId)
    /* 0.5.29：当前照片变化（翻页/跳转/评级/旗标）时通知主窗口，
       右侧信息面板自动跟随，避免基于旧信息误操作 */
    signal currentChanged(int photoId)
    /* 0.5.64：当前照片为损坏文件（photos.decode_error）时显示底部提示条 */
    property bool _decodeWarn: false

    function _loadMeta() {
        if (_index < 0 || _index >= _ids.length) return
        var d = LibraryBridge.photoDetail(_ids[_index])
        _decodeWarn = d.decodeError === true
        _curRating = d.rating || 0
        _curFlag = d.flag || ""
        var mark = ""
        if (_curRating > 0) mark += "★" + _curRating
        if (_curFlag === "pick") mark += (mark ? "  " : "") + I18n.tr("精选")
        if (_curFlag === "reject") mark += (mark ? "  " : "") + I18n.tr("排除")
        markText.text = mark
        _loadFaces()
        /* 0.5.29：通知右栏跟随（prev/next/jumpTo/评级/旗标都经此函数） */
        root.currentChanged(_ids[_index])
    }

    /* 载入当前照片人脸框（归一化坐标，叠加在原图上） */
    function _loadFaces() {
        _faces = (_index >= 0 && _index < _ids.length)
                 ? LibraryBridge.photoFaces(_ids[_index]) : []
    }

    function toggleFaces() {
        _showFaces = !_showFaces
        faceBtn.text = _showFaces ? I18n.tr("人脸框 开") : I18n.tr("人脸框 关")
    }

    function _setRating(r) {
        if (_index < 0) return
        LibraryBridge.setRating(_ids[_index], r)
        _curRating = r
        _loadMeta()
    }

    function _setFlag(f) {
        if (_index < 0) return
        LibraryBridge.setFlag(_ids[_index], f)
        _curFlag = f
        _loadMeta()
    }

    function showPhoto(url, title, photoId) {
        image.source = url || ""
        /* 0.5.38：只显示一个名字（此前 title 与文件名拼在一起重复显示） */
        titleText.text = title || url.split("/").pop() || ""
        _scale = 1.0
        image.x = 0
        image.y = 0
        _center()
        /* 单人查看：仅在无图库上下文时记录，避免覆盖已注入的照片序列 */
        if ((photoId !== undefined && photoId > 0) && (!_ids || _ids.length === 0)) {
            _ids = [photoId]
            _index = 0
        }
        _loadFaces()
        if (photoId !== undefined && photoId > 0) {
            var dd = LibraryBridge.photoDetail(photoId)
            _decodeWarn = dd.decodeError === true
            root.currentChanged(photoId)
        }
        /* 居中于屏幕（多屏按主屏） */
        root.x = Math.max(0, Math.round((Screen.width - root.width) / 2))
        root.y = Math.max(0, Math.round((Screen.height - root.height) / 2))
        root.show()
        root.requestActivate()
    }

    /* 图库上下文：记录当前可见照片 id 序列与索引，供上/下一张翻页。
       只记录不弹窗——图库单击仅联动右侧信息面板，弹出大图需显式调用
       showCurrent()（右键I18n.tr("打开大图")）或 showPhoto()（信息面板图片点击）。 */
    function setContext(ids, index) {
        if (!ids || ids.length === 0) return
        _ids = ids
        _index = Math.max(0, Math.min(index, ids.length - 1))
    }

    function showCurrent() {
        _loadCurrent()
    }

    function _loadCurrent() {
        if (_index < 0 || _index >= _ids.length) return
        var d = LibraryBridge.photoDetail(_ids[_index])
        if (d) {
            /* 0.5.51：RAW/HEIC/AVIF 等 Qt 无法解码的格式经 photoViewUrl 拿
               解码预览 URL；解不了退回原文件 URL（QML 显示占位） */
            image.source = LibraryBridge.photoViewUrl(_ids[_index]) || d.fullUrl || ""
            /* 0.5.38：只显示文件名一次（此前 name 与 URL 文件名重复拼接） */
            titleText.text = d.name || ""
            _scale = 1.0
            image.x = 0
            image.y = 0
            _fitWindow()
            root.show()
            _loadMeta()
            if (root.filmVisible) root._loadFilm()
        }
    }

    function prev() {
        if (_index > 0) { _index--; _loadCurrent() }
    }

    function next() {
        if (_index >= 0 && _index < _ids.length - 1) { _index++; _loadCurrent() }
    }

    function toggleSlideshow() {
        _slideshow = !_slideshow
        slideBtn.text = _slideshow ? I18n.tr("停止 ⏸") : I18n.tr("幻灯片 ▶")
        if (_slideshow) slideTimer.start()
        else slideTimer.stop()
    }

    /* ---- ACDsee 风格胶片条：底部缩略图条，点击快速跳图 ---- */
    function _loadFilm() {
        filmModel.clear()
        if (!_ids || _ids.length < 2) return
        var start = Math.max(0, _index - 30)
        var end = Math.min(_ids.length - 1, _index + 30)
        for (var i = start; i <= end; ++i) {
            var d = LibraryBridge.photoDetail(_ids[i])
            filmModel.append({ idx: i, thumb: (d && d.thumb) ? d.thumb : "" })
        }
        filmList.currentIndex = _index - start
        if (filmVisible) filmList.positionViewAtIndex(filmList.currentIndex, ListView.Center)
    }

    function jumpTo(idx) {
        if (idx < 0 || idx >= _ids.length) return
        _index = idx
        _loadCurrent()
    }

    function toggleFilm() {
        filmVisible = !filmVisible
        if (filmVisible) _loadFilm()
        /* 胶片条占位变化后重新适配大图（0.5.28：修"开后关不掉/图片被截"） */
        _fitScale()
    }

    Shortcut {
        sequence: "Esc"
        enabled: root.visible
        onActivated: root.close()
    }

    Shortcut {
        sequence: "Left"
        enabled: root.visible
        onActivated: { _slideshow = false; slideBtn.text = I18n.tr("幻灯片 ▶"); root.prev() }
    }

    Shortcut {
        sequence: "Right"
        enabled: root.visible
        onActivated: { _slideshow = false; slideBtn.text = I18n.tr("幻灯片 ▶"); root.next() }
    }

    /* 评级快捷键：1-5 星，0 清除 */
    Shortcut { sequence: "1"; enabled: root.visible; onActivated: root._setRating(1) }
    Shortcut { sequence: "2"; enabled: root.visible; onActivated: root._setRating(2) }
    Shortcut { sequence: "3"; enabled: root.visible; onActivated: root._setRating(3) }
    Shortcut { sequence: "4"; enabled: root.visible; onActivated: root._setRating(4) }
    Shortcut { sequence: "5"; enabled: root.visible; onActivated: root._setRating(5) }
    Shortcut { sequence: "0"; enabled: root.visible; onActivated: root._setRating(0) }
    /* 旗标快捷键：P 精选，X 排除，U 清除；排除一律经确认弹窗（0.5.39） */
    Shortcut { sequence: "P"; enabled: root.visible; onActivated: root._setFlag("pick") }
    Shortcut { sequence: "X"; enabled: root.visible; onActivated: root.openRejectConfirm() }
    Shortcut { sequence: "U"; enabled: root.visible; onActivated: root._setFlag("") }
    /* 0.5.35：Delete/Backspace 常用键位（仅旗标，可逆；程序内无删除原图功能） */
    Shortcut { sequence: "Delete"; enabled: root.visible; onActivated: root.openRejectConfirm() }
    Shortcut { sequence: "Backspace"; enabled: root.visible; onActivated: root._setFlag("") }

    /* 0.5.39：排除确认弹窗——说明「排除」的作用，确认后才生效 */
    function openRejectConfirm() {
        if (_index < 0) return
        rejectConfirm.open()
    }

    Dialog {
        id: rejectConfirm
        objectName: "viewerRejectConfirm"
        modal: true
        width: 460
        anchors.centerIn: parent
        padding: 16

        background: Rectangle {
            color: "#2a2a2c"
            radius: 10
            border.width: 1
            border.color: "#444446"
        }

        contentItem: ColumnLayout {
            spacing: 10

            Text {
                text: I18n.tr("把这张照片标记为「排除」？")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: "white"
            }
            Text {
                Layout.fillWidth: true
                text: I18n.tr("「排除」是选片淘汰标记：照片原样保留，不会被删除或隐藏。\n\n")
                      + I18n.tr("· 图库顶部的「排除 ✕」筛选可列出所有排除照片，方便统一处理\n")
                      + I18n.tr("· 搜索 flag:reject 可随时找到它们\n")
                      + I18n.tr("· 随时按 U 或「清除旗标」即可撤销")
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: "#cccccc"
                lineHeight: 1.4
            }
            Row {
                spacing: 8
                layoutDirection: Qt.RightToLeft
                anchors.right: parent.right
                PMButton {
                    text: I18n.tr("取消")
                    height: 30
                    onClicked: rejectConfirm.close()
                }
                PMButton {
                    objectName: "viewerRejectYesBtn"
                    text: I18n.tr("标记排除")
                    height: 30
                    emphasized: true
                    onClicked: {
                        rejectConfirm.close()
                        root._setFlag("reject")
                    }
                }
            }
        }
    }

    Timer {
        id: slideTimer
        interval: root._slideInterval
        repeat: true
        onTriggered: {
            if (_index < _ids.length - 1) root.next()
            else root.toggleSlideshow()
        }
    }

    ColumnLayout {
        anchors.fill: contentItem
        anchors.margins: 10
        spacing: 8

        /* 顶部信息行：z 序恒在图片上层（imgArea 已 clip，放大的照片不会盖上来）。
           0.5.38：去掉「关闭」按钮（与窗口自带关闭重复）。 */
        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            spacing: 8
            z: 10

            Text {
                id: titleText
                objectName: "viewerTitle"
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth + 4, parent.width * 0.7)
                elide: Text.ElideMiddle
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "white"
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: _scale > 0 ? (Math.round(_scale * 100) + "%") : ""
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: "white"
            }
            Text {
                id: markText
                objectName: "viewerMark"
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: "#f5c842"
            }
            Item { Layout.fillWidth: true; height: 10 }
        }

        Item {
            id: imgArea
            /* 0.5.38：高度交给 ColumnLayout 自动分配（此前手工算窗口高度减
               固定值，胶片条/按钮行变化后错位——图片被胶片条遮挡、不居中）。
               clip 保证放大的照片只在图片区内绘制，不遮挡顶部信息行。 */
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Image {
                id: image
                objectName: "viewerImage"
                x: 0
                y: 0
                width: _imgW * _scale
                height: _imgH * _scale
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true
                clip: false
                visible: status === Image.Ready
                transformOrigin: Item.TopLeft
                onSourceSizeChanged: {
                    /* 0.5.38：载入完成即按窗口适配并居中（此前 _fitScale 上限
                       1.0 且居中用窗口坐标，点胶片条换图后错位/被胶片条遮挡） */
                    _fitWindow()
                }
            }
            Text {
                anchors.centerIn: parent
                visible: image.status !== Image.Ready && !image.source
                text: I18n.tr("无法预览（格式不支持解码或文件已缺失）")
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: "white"
            }

            /* 人脸框叠加层：跟随 image 位置与尺寸，归一化坐标换算 */
            Item {
                id: faceLayer
                objectName: "faceLayer"
                x: image.x
                y: image.y
                width: image.width
                height: image.height
                visible: root._showFaces && image.visible && root._faces.length > 0
                Repeater {
                    model: root._faces
                    Rectangle {
                        x: modelData.nx * faceLayer.width
                        y: modelData.ny * faceLayer.height
                        width: modelData.nw * faceLayer.width
                        height: modelData.nh * faceLayer.height
                        color: "transparent"
                        border.width: 2
                        border.color: modelData.personId > 0 ? "#4dd0e1" : "#f5c842"
                        Rectangle {
                            anchors.bottom: parent.top
                            anchors.left: parent.left
                            height: 18
                            width: labelText.implicitWidth + 10
                            radius: 3
                            color: "#cc000000"
                            Text {
                                id: labelText
                                anchors.centerIn: parent
                                text: modelData.personName
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: "white"
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.assignFaceRequested(modelData.id)
                        }
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.OpenHandCursor
                onWheel: (wheel) => {
                    var factor = wheel.angleDelta.y > 0 ? 1.15 : 1 / 1.15
                    _zoomAt(wheel.x, wheel.y, factor)
                    wheel.accepted = true
                }
                onDoubleClicked: (mouse) => {
                    _fitWindow()
                }
                onPressed: (mouse) => {
                    _dragStartX = mouse.x - image.x
                    _dragStartY = mouse.y - image.y
                }
                onPositionChanged: (mouse) => {
                    if (pressed) {
                        image.x = mouse.x - _dragStartX
                        image.y = mouse.y - _dragStartY
                    }
                }
                property real _dragStartX: 0
                property real _dragStartY: 0
            }
        }

        /* 0.5.64：损坏文件提示条（当前照片 decode_error=1 时显示） */
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: decWarnText.implicitHeight + 14
            visible: root._decodeWarn
            color: "#fff3e0"
            border.width: 1
            border.color: "#e65100"
            z: 10
            Text {
                id: decWarnText
                anchors.verticalCenter: parent.verticalCenter
                x: 10
                width: parent.width - 20
                text: I18n.tr("⚠ 文件数据不完整（可能传输中断/损坏）——当前显示相机内嵌预览，导出原图前请知悉")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: "#e65100"
                wrapMode: Text.WordWrap
            }
        }

        /* ACDsee 风格胶片条：底部缩略图条，点击快速跳图（可开关） */
        Rectangle {
            id: filmStrip
            objectName: "viewerFilmStrip"
            Layout.fillWidth: true
            Layout.preferredHeight: 78
            visible: root.filmVisible && filmModel.count > 1
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ListView {
                id: filmList
                objectName: "viewerFilmList"
                anchors.fill: parent
                anchors.margins: 7
                orientation: ListView.Horizontal
                spacing: 6
                clip: true
                ScrollBar.horizontal: PMScrollBar { policy: ScrollBar.AlwaysOn }
                model: filmModel

                delegate: Rectangle {
                    width: 64
                    height: 64
                    radius: Theme.radiusSmall
                    color: Theme.bg
                    border.width: model.idx === root._index ? 2 : 1
                    border.color: model.idx === root._index ? Theme.primary : Theme.divider

                    Image {
                        anchors.fill: parent
                        anchors.margins: 2
                        /* 0.5.28：PreserveAspectFit 完整显示整张照片（此前
                           PreserveAspectCrop 把竖图裁得只剩中段，用户反馈I18n.tr("高度被截矮")） */
                        fillMode: Image.PreserveAspectFit
                        source: model.thumb || ""
                        asynchronous: true
                        cache: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.jumpTo(model.idx)
                    }
                }
            }
        }

        /* 0.5.38：按钮行改 Flow 自适应换行——窗口缩小时折行而不是被截断 */
        Flow {
            Layout.fillWidth: true
            spacing: 8

            PMButton {
                objectName: "viewerFilmBtn"
                text: root.filmVisible ? I18n.tr("▤ 胶片条 ✓") : I18n.tr("▤ 胶片条")
                width: 92
                height: 28
                tooltip: I18n.tr("开关底部缩略图胶片条，点击缩略图可快速跳到那张照片")
                onClicked: root.toggleFilm()
            }
            PMButton {
                objectName: "viewerPrev"
                text: I18n.tr("上一张 ◀")
                width: 88
                height: 28
                tooltip: I18n.tr("查看上一张照片（快捷键 ←）")
                enabled: root._index > 0
                onClicked: root.prev()
            }
            PMButton {
                objectName: "viewerNext"
                text: I18n.tr("下一张 ▶")
                width: 88
                height: 28
                tooltip: I18n.tr("查看下一张照片（快捷键 →）")
                enabled: root._index >= 0 && root._index < root._ids.length - 1
                onClicked: root.next()
            }
            PMButton {
                objectName: "viewerZoomIn"
                text: I18n.tr("放大 +")
                width: 72
                height: 28
                tooltip: I18n.tr("以中心为基准放大（也可用滚轮向上）")
                onClicked: root._zoomCenter(1.25)
            }
            PMButton {
                objectName: "viewerZoomOut"
                text: I18n.tr("缩小 −")
                width: 72
                height: 28
                tooltip: I18n.tr("以中心为基准缩小（也可用滚轮向下）")
                onClicked: root._zoomCenter(0.8)
            }
            PMButton {
                objectName: "viewerFit"
                text: I18n.tr("适应窗口")
                width: 88
                height: 28
                tooltip: I18n.tr("完整显示整张照片并居中（双击图片同效）")
                onClicked: root._fitWindow()
            }
            PMButton {
                objectName: "viewerOriginal"
                text: I18n.tr("1:1 原始")
                width: 88
                height: 28
                tooltip: I18n.tr("按原始分辨率显示（1 图像像素 = 1 屏幕像素）")
                onClicked: root._original()
            }
            PMButton {
                id: slideBtn
                objectName: "viewerSlide"
                text: I18n.tr("幻灯片 ▶")
                width: 96
                height: 28
                tooltip: I18n.tr("每 4 秒自动切换下一张，到最后一张自动停止")
                onClicked: root.toggleSlideshow()
            }
            PMButton {
                id: faceBtn
                objectName: "viewerFaces"
                text: I18n.tr("人脸框 关")
                width: 88
                height: 28
                tooltip: I18n.tr("在照片上叠加显示已检测的人脸框和人物名，可点击框指派人物")
                onClicked: root.toggleFaces()
            }
            /* 0.5.39：旗标按钮组常显（此前只有快捷键）；排除需确认 */
            PMButton {
                objectName: "viewerPickBtn"
                text: I18n.tr("精选 ✓")
                width: 76
                height: 28
                tooltip: I18n.tr("给当前照片打「精选」旗标，表示选片保留（快捷键 P）")
                onClicked: root._setFlag("pick")
            }
            PMButton {
                objectName: "viewerRejectBtn"
                text: I18n.tr("排除 ✕")
                width: 76
                height: 28
                tooltip: I18n.tr("把当前照片标记为「排除」（选片淘汰标记，照片不会删除；点击后需确认）")
                onClicked: root.openRejectConfirm()
            }
            PMButton {
                objectName: "viewerFlagClearBtn"
                text: I18n.tr("清除旗标")
                width: 88
                height: 28
                tooltip: I18n.tr("清除当前照片的精选/排除旗标（快捷键 U）")
                onClicked: root._setFlag("")
            }
        }
    }

    onClosing: {
        _slideshow = false
        if (slideBtn) slideBtn.text = I18n.tr("幻灯片 ▶")
        slideTimer.stop()
    }

    function _fitScale() {
        /* 0.5.38：与 _fitWindow 统一（此前两套算法且居中用窗口坐标，导致错位） */
        _fitWindow()
    }

    /* 窗口大小变化：若当前处于"适应窗口"状态则重新适配（手动缩放状态不干扰） */
    onWidthChanged: if (visible && image.status === Image.Ready
                        && Math.abs(_scale - _baseScale) < 0.001) _fitWindow()
    onHeightChanged: if (visible && image.status === Image.Ready
                        && Math.abs(_scale - _baseScale) < 0.001) _fitWindow()

    function _fitWindow() {
        if (!image.sourceSize.width) return
        _imgW = image.sourceSize.width
        _imgH = image.sourceSize.height
        /* 0.5.38：以图片区（imgArea）为基准适配并居中——此前用整个窗口坐标
           计算，图片垂直方向偏下，底部被胶片条遮挡、看起来不居中 */
        var availW = imgArea.width
        var availH = imgArea.height
        if (availW <= 0 || availH <= 0) return
        _baseScale = Math.min(availW / _imgW, availH / _imgH)
        _scale = _baseScale
        _center()
    }

    function _center() {
        /* 0.5.38：在图片区内居中（此前用窗口 width/height） */
        image.x = (imgArea.width - image.width) / 2
        image.y = (imgArea.height - image.height) / 2
    }

    /* 原始分辨率：1 像素 = 1 屏幕像素 */
    function _original() {
        _scale = 1.0
        _center()
    }

    function _zoomCenter(factor) {
        _zoomAt(imgArea.width / 2, imgArea.height / 2, factor)
    }

    function _zoomAt(px, py, factor) {
        var newScale = Math.max(0.05, Math.min(10.0, _scale * factor))
        if (Math.abs(newScale - _scale) < 0.001) return
        var oldScale = _scale
        _scale = newScale
        image.x = px - (px - image.x) * (newScale / oldScale)
        image.y = py - (py - image.y) * (newScale / oldScale)
    }
}