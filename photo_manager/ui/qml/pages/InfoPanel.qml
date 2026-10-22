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

/* 右侧信息面板（0.5.34 重构：渐进式披露）。
   设计原则：重点突出 + 想看时能看到——
   · 固定区：预览 / 评级 / 旗标（高频操作，常驻）
   · 摘要区：拍摄时间、尺寸、人脸数等一眼可读的关键信息，无 "--" 噪音
   · 折叠区：拍摄参数 / OCR 文字 / 文件信息 默认收起，标题带摘要徽标，点击展开
   · 人脸默认只显示 4 张，其余折叠进「+N」；标签单处呈现，点击=跳转、悬停=移除
   点击预览可放大查看（弹窗，支持滚轮缩放、拖动平移、双击复位）。 */
Rectangle {
    id: root

    color: Theme.surfaceAlt
    radius: Theme.radiusLarge

    /* ---- 分区标题文案助手：▾/▸ + 标签 + 徽标 ---- */
    function _sec(label, open, badge) {
        return (open ? "▾ " : "▸ ") + label + (badge ? "　" + badge : "")
    }

    function showDetail(d) {
        if (!d || Object.keys(d).length === 0) {
            currentName = ""
            currentId = -1
            currentDate = ""
            currentFolder = ""
            currentCamera = ""
            currentMediaType = "photo"
            currentDuration = 0
            currentVideoCodec = ""
            currentPath = ""
            videoFrameUrls = []
            takenAtLine = ""
            sizeLine = ""
            cameraLine = ""
            lensLine = ""
            paramLine = ""
            posLine = ""
            folderLine = ""
            fileNameLine = ""
            decodeWarn = false
            ocrText = ""
            faceCount = 0
            exifOpen = false
            ocrOpen = false
            fileOpen = false
            refreshTags([])
            refreshFaces(-1)
            previewImage.source = ""
            return
        }
        currentId = d.id
        currentName = d.name
        currentDate = (d.takenAt || "").slice(0, 10)
        currentFolder = d.folder || ""
        /* 0.5.64：跳转目标须与 devicePhotos 的 camera_model=? 匹配——
           此前拼接 make+model（"Canon Canon EOS R6"）导致「同相机」跳转恒 0 条 */
        currentCamera = d.model || ""
        currentRating = d.rating || 0
        currentFlag = d.flag || ""
        currentArchived = !!d.archived
        currentMediaType = d.mediaType || "photo"
        currentDuration = d.duration || 0
        currentVideoCodec = d.videoCodec || ""
        currentPath = d.path || ""
        takenAtLine = d.takenAt || "-"
        sizeLine = d.width + "×" + d.height + " · " + d.sizeKB + " KB"
        if (currentMediaType === "video") {
            // 视频：摘要行补 编码 + 时长（分辨率+大小已有）
            var t = Math.floor(currentDuration || 0)
            var mm = Math.floor(t / 60), ss = t % 60
            var dur = t > 0 ? (mm + ":" + (ss < 10 ? "0" : "") + ss) : ""
            sizeLine = d.width + "×" + d.height
                + (currentVideoCodec ? " · " + currentVideoCodec : "")
                + (dur ? " · " + dur : "")
                + " · " + d.sizeKB + " KB"
            // 0.5.51：关键帧带（按时长均匀抽取；同时供 CLIP 编码进语义检索）
            videoFrameUrls = LibraryBridge
                ? LibraryBridge.videoFrames(currentId).map(function (f) { return f.url })
                : []
        } else {
            videoFrameUrls = []
        }
        cameraLine = ((d.make || "") + " " + (d.model || "")).trim() || "-"
        lensLine = (d.lens || "").trim()
        var pp = []
        if (d.fNumber) pp.push("f/" + d.fNumber)
        if (d.exposure) pp.push(d.exposure + "s")
        if (d.iso) pp.push("ISO " + d.iso)
        if (d.focal) pp.push(d.focal + "mm")
        paramLine = pp.join("  ")
        posLine = d.lat ? (d.lat.toFixed(5) + ", " + d.lon.toFixed(5)) : ""
        folderLine = d.folder || "-"
        fileNameLine = d.name || "-"
        decodeWarn = d.decodeError === true
        ocrText = d.ocr || ""
        faceCount = d.faces || 0
        /* 有真实 EXIF（除相机名外任一值）时自动展开参数区，否则保持收起 */
        exifOpen = paramLine.length > 0 || lensLine.length > 0 || !!d.lat
        ocrOpen = false
        fileOpen = false
        faceExpanded = false
        refreshTags(LibraryBridge.photoTags(d.id))
        refreshFaces(d.id)
        /* 预览用缩略图（快速），放大用原图（清晰） */
        previewImage.source = d.thumb || ""
        fullSource = d.fullUrl || ""
        previewHint.visible = !!d.fullUrl
    }

    property int currentId: -1

    /* ACDsee 风格：分区可折叠 */
    property bool faceOpen: true
    property bool tagOpen: true
    property bool exifOpen: false
    property bool ocrOpen: false
    property bool fileOpen: false
    property bool faceExpanded: false
    signal tagPickerRequested()
    property string fullSource: ""
    property string currentName: ""
    /* 快速跳转（0.5.31）：当前照片的日期/文件夹/相机快照，供跳转链接用 */
    property string currentDate: ""
    property string currentFolder: ""
    property string currentCamera: ""
    property int currentRating: 0
    property string currentFlag: ""
    property bool currentArchived: false
    /* 0.5.44 视频字段 */
    property string currentMediaType: "photo"
    property real currentDuration: 0
    property string currentVideoCodec: ""
    property string currentPath: ""
    property var videoFrameUrls: []
    signal openPhoto(string fullUrl, string title, int photoId)
    signal toastRequested(string text, string kind)
    signal assignFaceRequested(int faceId)
    /* kind: date | folder | camera | tag（标签值由标签 chips 逐个发出） */
    signal jumpRequested(string kind, string value)

    /* 摘要/折叠区数据行（showDetail 填充） */
    property string takenAtLine: ""
    property string sizeLine: ""
    property string cameraLine: "-"
    property string lensLine: ""
    property string paramLine: ""
    property string posLine: ""
    property string folderLine: "-"
    /* 0.5.64：损坏文件警告（photos.decode_error，查看/深检写入） */
    property bool decodeWarn: false
    property string fileNameLine: "-"
    property string ocrText: ""
    property int faceCount: 0

    /* 标签/人脸数据：用 JS 数组整体替换（QML ListModel clear+append 与 Repeater
       重建存在非确定性空 delegate 问题，项目约定见 FolderPickerDialog 同类修复） */
    property var tagList: []
    property var faceList: []

    function refreshFaces(photoId) {
        var arr = []
        if (photoId >= 0) {
            var faces = LibraryBridge.photoFaces(photoId)
            for (var i = 0; i < faces.length; i++) {
                var f = faces[i]
                arr.push({
                    "faceId": f.id,
                    "crop": LibraryBridge.faceCropUrl(f.id),
                    "name": f.personName,
                    "personId": f.personId,
                    "blurIdx": (typeof f.blurIdx !== "undefined") ? f.blurIdx : -1
                })
            }
        }
        root.faceList = arr
    }

    function refreshTags(tags) {
        root.tagList = tags || []
    }

    function addTag() {
        if (currentId < 0) return
        var tag = tagField.text.trim()
        if (tag.length === 0) return
        if (LibraryBridge.addTag(currentId, tag)) {
            tagField.text = ""
            refreshTags(LibraryBridge.photoTags(currentId))
            root.toastRequested(I18n.tr("已添加标签「") + tag + "」", "success")
        } else {
            root.toastRequested(I18n.tr("添加标签失败"), "error")
        }
    }

    function removeTag(tag) {
        if (currentId < 0) return
        if (LibraryBridge.removeTag(currentId, tag)) {
            refreshTags(LibraryBridge.photoTags(currentId))
            root.toastRequested(I18n.tr("已移除标签「") + tag + "」", "success")
        } else {
            root.toastRequested(I18n.tr("移除标签失败"), "error")
        }
    }

    function setRating(r) {
        if (currentId < 0) return
        LibraryBridge.setRating(currentId, r)
        currentRating = r
        root.toastRequested(r > 0 ? I18n.tr("评级 ") + r + I18n.tr(" 星") : I18n.tr("已清除评级"), "success")
    }

    function setFlag(f) {
        if (currentId < 0) return
        LibraryBridge.setFlag(currentId, f)
        currentFlag = f
        root.toastRequested(f === "pick" ? I18n.tr("已标记精选") :
                           f === "reject" ? I18n.tr("已标记排除") : I18n.tr("已清除旗标"), "success")
    }

    /* 0.5.39：作废需确认——pendingArchived 暂存意图，弹窗说明作用后执行 */
    function setArchived(a) {
        if (currentId < 0) return
        pendingArchived = a
        archiveConfirm.open()
    }

    function _applyArchived(a) {
        if (currentId < 0) return
        LibraryBridge.setArchived(currentId, a)
        currentArchived = a
        root.toastRequested(a ? I18n.tr("已作废（不删除；可在左栏「作废」中恢复）")
                              : I18n.tr("已恢复显示"), "success")
    }

    Dialog {
        id: archiveConfirm
        objectName: "infoArchiveConfirm"
        modal: true
        width: 420
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        padding: 16

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusLarge
            border.width: 1
            border.color: Theme.divider
        }

        property bool pendingArchived: true

        contentItem: ColumnLayout {
            spacing: 10

            Text {
                text: archiveConfirm.pendingArchived
                      ? I18n.tr("作废这张照片？")
                      : I18n.tr("恢复显示这张照片？")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                text: archiveConfirm.pendingArchived
                      ? I18n.tr("「作废（不删除）」的作用：把照片从普通浏览、时间线、事件等视图中隐藏，用于整理掉不想再看到的照片。\n\n· 不会删除、移动或修改任何照片文件\n· 随时可在左侧栏「作废」页面找回并恢复")
                      : I18n.tr("照片将重新出现在普通浏览、时间线等视图中。")
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                lineHeight: 1.4
            }
            Row {
                spacing: Theme.spacingSmall
                layoutDirection: Qt.RightToLeft
                anchors.right: parent.right
                PMButton {
                    text: I18n.tr("取消")
                    height: 30
                    onClicked: archiveConfirm.close()
                }
                PMButton {
                    objectName: "infoArchiveConfirmYesBtn"
                    text: archiveConfirm.pendingArchived ? I18n.tr("作废（不删除）") : I18n.tr("恢复显示")
                    height: 30
                    emphasized: true
                    onClicked: {
                        archiveConfirm.close()
                        root._applyArchived(archiveConfirm.pendingArchived)
                    }
                }
            }
        }
    }

    /* 0.5.66：视频播放器懒加载（缺 QtMultimedia 时回退系统播放器，不再拖垮加载） */
    Loader {
        id: videoPlayerLoader
        active: false
        sourceComponent: VideoPlayerDialog { }
    }

    function _openVideo(path) {
        videoPlayerLoader.active = true
        if (videoPlayerLoader.item)
            videoPlayerLoader.item.openVideo(path)
        else if (LibraryBridge)
            LibraryBridge.openExternal(path)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingMedium
        spacing: Theme.spacingSmall

        Text {
            text: I18n.tr("照片信息")
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: Theme.text
        }

        /* 预览区：点击放大 */
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 200
            radius: Theme.radiusMedium
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider
            clip: true

            Image {
                id: previewImage
                objectName: "previewImage"
                anchors.fill: parent
                anchors.margins: 2
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: true
                visible: status === Image.Ready
                smooth: true
            }
            Text {
                anchors.centerIn: parent
                visible: previewImage.status !== Image.Ready
                text: I18n.tr("无预览")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            Text {
                id: previewHint
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.margins: 6
                visible: false
                text: I18n.tr("点击查看大图")
                font.family: Theme.fontFamily
                font.pixelSize: 10
                color: "white"
                style: Text.Outline
                styleColor: "black"
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    /* 0.5.51：RAW/HEIC/AVIF 等 Qt 解不了的格式经 photoViewUrl
                       走解码预览（原直传 fullUrl → 大图空白）；视频走播放器 */
                    if (root.currentMediaType === "video") {
                        root._openVideo(root.currentPath)
                        return
                    }
                    var url = LibraryBridge.photoViewUrl(root.currentId) || root.fullSource
                    if (url) root.openPhoto(url, currentName, currentId)
                }
            }
        }

        Column {
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 6
            Row {
                objectName: "ratingRow"
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.tr("评级")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                /* 可点击的 5 星评级（0.5.25 去掉了旁边冗余的只读星号文本） */
                Repeater {
                    model: [1, 2, 3, 4, 5]
                    delegate: Text {
                        objectName: "ratingStar_" + (index + 1)
                        anchors.verticalCenter: parent.verticalCenter
                        text: "★"
                        font.family: Theme.fontFamily
                        font.pixelSize: 15
                        color: index < currentRating ? "#f5c842" : "#3a4150"
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.setRating(index + 1 === currentRating ? 0 : index + 1)
                        }
                    }
                }
            }
            Row {
                spacing: 8
                PMButton {
                    objectName: "videoPlayBtn"
                    visible: currentMediaType === "video"
                    tooltip: I18n.tr("在内嵌播放器中播放该视频（加载失败时可改用系统播放器）")
                    text: I18n.tr("▶ 播放")
                    implicitWidth: Math.max(72, implicitContentWidth + leftPadding + rightPadding)
                    height: 24
                    onClicked: root._openVideo(currentPath)
                }
                PMButton {
                    objectName: "flagPickBtn"
                    tooltip: I18n.tr("给当前照片打「精选」旗标（快捷键 P）")
                    text: currentFlag === "pick" ? I18n.tr("精选 ✓") : I18n.tr("精选")
                    implicitWidth: Math.max(72, implicitContentWidth + leftPadding + rightPadding)
                    height: 24
                    onClicked: root.setFlag(currentFlag === "pick" ? "" : "pick")
                }
                PMButton {
                    objectName: "flagRejectBtn"
                    tooltip: I18n.tr("给当前照片打「排除」旗标（快捷键 X）")
                    text: currentFlag === "reject" ? I18n.tr("排除 ✕") : I18n.tr("排除")
                    implicitWidth: Math.max(72, implicitContentWidth + leftPadding + rightPadding)
                    height: 24
                    onClicked: root.setFlag(currentFlag === "reject" ? "" : "reject")
                }
                PMButton {
                    objectName: "flagArchiveBtn"
                    tooltip: I18n.tr("作废（不删除）：从普通浏览/时间线隐藏，左栏「作废」页可恢复；点击后需确认")
                    text: currentArchived ? I18n.tr("已作废 🗄") : I18n.tr("作废（不删除）")
                    implicitWidth: Math.max(72, implicitContentWidth + leftPadding + rightPadding)
                    height: 24
                    onClicked: root.setArchived(currentArchived ? false : true)
                }
            }
            /* 0.5.51：视频关键帧带（点击帧可放大查看该帧） */
            Row {
                objectName: "videoFrameStrip"
                visible: currentMediaType === "video" && root.videoFrameUrls.length > 0
                spacing: 4
                Repeater {
                    model: root.videoFrameUrls
                    delegate: Image {
                        width: 56
                        height: 40
                        source: modelData
                        fillMode: Image.PreserveAspectCrop
                        cache: true
                    }
                }
            }
        }

        /* ---- 滚动详情区：摘要 + 折叠分区 + 跳转 + 人脸 + 标签 ---- */
        Flickable {
            id: detailScroll
            objectName: "detailScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 40
            contentHeight: detailCol.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: PMScrollBar {
                policy: ScrollBar.AsNeeded
            }

            Column {
                id: detailCol
                objectName: "detailCol"
                width: detailScroll.width
                spacing: 10

                /* 无照片时的占位提示 */
                Text {
                    visible: root.currentId < 0
                    width: parent.width
                    text: I18n.tr("点击图库中的照片查看详情")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }

                /* ---- 摘要区：关键信息一眼可读，无 "--" 行 ---- */
                Column {
                    visible: root.currentId > 0
                    width: parent.width
                    spacing: 5

                    Row {
                        spacing: 8
                        Text {
                            text: I18n.tr("拍摄时间")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            width: detailCol.width - 64
                            text: root.takenAtLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: Theme.text
                            wrapMode: Text.Wrap
                        }
                    }
                    Row {
                        spacing: 8
                        Text {
                            text: I18n.tr("尺寸")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            text: root.sizeLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                    }
                    Row {
                        visible: root.faceCount > 0
                        spacing: 8
                        Text {
                            text: I18n.tr("人脸")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            text: root.faceCount + I18n.tr(" 张")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                    }
                }

                /* ---- 拍摄参数（折叠；相机恒有行，其余有值才显示） ---- */
                Text {
                    visible: root.currentId > 0
                    text: root._sec(I18n.tr("拍摄参数"), root.exifOpen,
                                    root.paramLine.length > 0 || root.lensLine.length > 0 ? "" : "")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.text
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.exifOpen = !root.exifOpen
                    }
                }
                Column {
                    visible: root.currentId > 0 && root.exifOpen
                    width: parent.width
                    spacing: 5
                    Row {
                        spacing: 8
                        Text {
                            text: I18n.tr("相机")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            width: detailCol.width - 52
                            text: root.cameraLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            wrapMode: Text.Wrap
                        }
                    }
                    Row {
                        visible: root.lensLine.length > 0
                        spacing: 8
                        Text {
                            text: I18n.tr("镜头")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            width: detailCol.width - 52
                            text: root.lensLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            wrapMode: Text.Wrap
                        }
                    }
                    Row {
                        visible: root.paramLine.length > 0
                        spacing: 8
                        Text {
                            text: I18n.tr("参数")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            text: root.paramLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                    }
                    Row {
                        visible: root.posLine.length > 0
                        spacing: 8
                        Text {
                            text: I18n.tr("位置")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            text: root.posLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                    }
                }

                /* ---- OCR 文字（有结果才显示；默认收起，标题带字数） ---- */
                Text {
                    visible: root.currentId > 0 && root.ocrText.length > 0
                    text: root._sec(I18n.tr("OCR 文字"), root.ocrOpen,
                                    root.ocrText.length + I18n.tr(" 字"))
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: root.ocrText.length > 0 ? Theme.primary : Theme.text
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.ocrOpen = !root.ocrOpen
                    }
                }
                Text {
                    visible: root.currentId > 0 && root.ocrOpen && root.ocrText.length > 0
                    width: parent.width
                    text: root.ocrText
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.text
                    lineHeight: 1.5
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }

                /* ---- 文件信息（折叠） ---- */
                Text {
                    visible: root.currentId > 0
                    text: root._sec(I18n.tr("文件信息"), root.fileOpen, "")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.text
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.fileOpen = !root.fileOpen
                    }
                }
                Column {
                    visible: root.currentId > 0 && root.fileOpen
                    width: parent.width
                    spacing: 5
                    /* 0.5.64：损坏文件警告行 */
                    Rectangle {
                        visible: root.decodeWarn
                        Layout.fillWidth: true
                        height: decWarnText.implicitHeight + 12
                        radius: Theme.radiusSmall
                        color: "#fff3e0"
                        border.width: 1
                        border.color: "#e65100"
                        Text {
                            id: decWarnText
                            anchors.verticalCenter: parent.verticalCenter
                            x: 8
                            width: parent.width - 16
                            text: I18n.tr("⚠ 文件数据不完整（可能传输中断/损坏）——预览为相机内嵌图，导出原图前请知悉")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: "#e65100"
                            wrapMode: Text.WordWrap
                        }
                    }
                    Row {
                        spacing: 8
                        Text {
                            text: I18n.tr("目录")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            width: detailCol.width - 52
                            text: root.folderLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            elide: Text.ElideMiddle
                        }
                    }
                    Row {
                        spacing: 8
                        Text {
                            text: I18n.tr("文件")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                        }
                        Text {
                            width: detailCol.width - 52
                            text: root.fileNameLine
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            elide: Text.ElideMiddle
                        }
                    }
                }

                /* ---- 快速跳转（chip 样式；同日/同文件夹/同相机，有数据才显示） ---- */
                Flow {
                    objectName: "jumpLinks"
                    visible: root.currentId > 0
                    width: parent.width
                    spacing: 6
                    Text {
                        objectName: "jumpLinksLabel"
                        text: I18n.tr("跳转")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: Theme.textDim
                        /* 注意：Flow 是 positioner，子项禁止 anchors（会导致布局紊乱互相叠压） */
                        topPadding: 5
                    }
                    Repeater {
                        model: [
                            { label: I18n.tr("📅 同日"), kind: "date", val: root.currentDate },
                            { label: I18n.tr("📁 同文件夹"), kind: "folder", val: root.currentFolder },
                            { label: I18n.tr("📷 同相机"), kind: "camera", val: root.currentCamera }
                        ]
                        delegate: Rectangle {
                            visible: model.modelData.val.length > 0
                            width: jfLabel.implicitWidth + 16
                            height: 22
                            radius: 11
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                            Text {
                                id: jfLabel
                                anchors.centerIn: parent
                                text: model.modelData.label
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.primary
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.jumpRequested(model.modelData.kind,
                                                              model.modelData.val)
                            }
                        }
                    }
                }

                /* ---- 人脸（默认展开；超过 4 张折叠，可展开全部） ---- */
                Text {
                    visible: faceList.length > 0
                    text: root._sec(I18n.tr("人脸（点击指派人物）"), root.faceOpen,
                                    faceList.length + I18n.tr(" 张"))
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.text
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.faceOpen = !root.faceOpen
                    }
                }
                Flow {
                    id: faceListView
                    objectName: "faceListView"
                    /* gui_check A61 依赖 count 属性（原为 ListView，0.5.34 改 Flow 换行布局） */
                    property int count: faceList.length
                    visible: faceList.length > 0 && root.faceOpen
                    width: parent.width
                    spacing: 8
                    Repeater {
                        /* int model + 索引绑定：JS 数组/ListaModel 作 Repeater model
                           在 positioner+Flickable 下存在非确定性空 delegate 问题（0.5.34 实测），
                           int model 是最稳定用法 */
                        model: faceList.length
                        delegate: Rectangle {
                            width: 92
                            height: 92
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                            /* 未展开时只显示前 4 张（positioner 跳过 invisible 子项） */
                            visible: root.faceExpanded || index < 4
                            Image {
                                anchors.top: parent.top
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.topMargin: 4
                                width: 56
                                height: 56
                                source: root.faceList[index].crop
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: true
                            }
                            Text {
                                id: faceName
                                anchors.bottom: parent.bottom
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 4
                                text: root.faceList[index].name
                                font.family: Theme.fontFamily
                                font.pixelSize: 10
                                color: Theme.text
                                elide: Text.ElideMiddle
                                horizontalAlignment: Text.AlignHCenter
                            }
                            /* 0.5.37：模糊角标（≥70 高亮，提示去清理弹窗处理） */
                            Rectangle {
                                visible: root.faceList[index].blurIdx >= 70
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 2
                                width: blurText.implicitWidth + 8
                                height: 14
                                radius: 7
                                color: root.faceList[index].blurIdx >= 85 ? "#b71c1c" : "#e65100"
                                Text {
                                    id: blurText
                                    anchors.centerIn: parent
                                    text: root.faceList[index].blurIdx
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                    color: "white"
                                }
                            }
                            MouseArea {
                                id: faceChipArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.assignFaceRequested(root.faceList[index].faceId)
                            }
                            /* 悬停出现的"取消误检"按钮：狗头/模糊块等非人脸可人工移除（0.5.25） */
                            Rectangle {
                                objectName: "faceDismissBtn_" + root.faceList[index].faceId
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 3
                                width: 20
                                height: 20
                                radius: 10
                                visible: faceChipArea.containsMouse
                                color: dismissArea.containsMouse ? Theme.danger : Qt.rgba(0, 0, 0, 0.45)
                                Text {
                                    anchors.centerIn: parent
                                    text: "✕"
                                    color: "white"
                                    font.pixelSize: 11
                                }
                                MouseArea {
                                    id: dismissArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (LibraryBridge.dismissFace(root.faceList[index].faceId)) {
                                            refreshFaces(root.currentId)
                                            root.toastRequested(I18n.tr("已取消该误检人脸"), "success")
                                        } else {
                                            root.toastRequested(I18n.tr("取消失败"), "error")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Text {
                    visible: faceList.length > 4 && root.faceOpen
                    text: root.faceExpanded ? I18n.tr("▴ 收起其余人脸")
                                            : I18n.tr("▾ 还有 ") + Math.max(0, faceList.length - 4) + I18n.tr(" 张，点击展开")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.primary
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.faceExpanded = !root.faceExpanded
                    }
                }
                Text {
                    visible: faceList.length === 0 && currentId >= 0
                    width: parent.width
                    text: I18n.tr("未检测到人脸")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }

                /* ---- 标签（单处呈现：点击 chip=跳转，悬停=移除） ---- */
                Text {
                    text: root._sec(I18n.tr("标签"), root.tagOpen,
                                    tagList.length > 0 ? tagList.length + I18n.tr(" 个") : "")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.text
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.tagOpen = !root.tagOpen
                    }
                }
                Flow {
                    objectName: "tagChipsFlow"
                    visible: root.tagOpen && tagList.length > 0
                    width: parent.width
                    spacing: 6
                    Repeater {
                        /* int model + 索引绑定（稳定性说明同人脸区） */
                        model: tagList.length
                        delegate: Rectangle {
                            id: chip
                            width: chipLabel.implicitWidth + 34
                            height: 24
                            radius: 12
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                            Text {
                                id: chipLabel
                                anchors.left: parent.left
                                anchors.leftMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.tagList[index]
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.primary
                            }
                            /* 悬停出现移除 ×（默认隐藏，避免视觉繁琐与误点） */
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 7
                                anchors.verticalCenter: parent.verticalCenter
                                visible: chipHover.containsMouse
                                text: "×"
                                font.pixelSize: 13
                                color: Theme.danger
                            }
                            MouseArea {
                                id: chipHover
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.jumpRequested("tag", root.tagList[index])
                            }
                            MouseArea {
                                anchors.right: parent.right
                                anchors.rightMargin: 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: 16
                                height: parent.height
                                visible: chipHover.containsMouse
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.removeTag(root.tagList[index])
                            }
                        }
                    }
                }
                Text {
                    visible: tagList.length === 0 && root.tagOpen
                    text: I18n.tr("暂无标签")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
                /* 标签文本镜像：Repeater 动态 delegate 的 QObject parent 为空，
                   Python 侧 findChildren 收集不到（gui_check A17 依赖），
                   用一个隐藏 Text 镜像全部标签文本（同旧版 tagsRow 语义） */
                Text {
                    objectName: "tagsRow"
                    visible: false
                    text: root.tagList.join("  ")
                }
            }
        }

        /* ---- 标签添加（固定底部，常驻可见，不随滚动） ---- */
        Row {
            Layout.fillWidth: true
            visible: root.currentId >= 0
            spacing: 6
            TextField {
                id: tagField
                objectName: "tagField"
                width: parent.width - 60
                height: 30
                placeholderText: I18n.tr("输入标签回车添加（层级用 / 分隔，如 旅行/北京）")
                placeholderTextColor: Theme.textDim
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.divider
                }
                onAccepted: addTag()
            }
            PMButton {
                text: I18n.tr("加")
                tooltip: I18n.tr("把输入框里的标签添加到当前照片")
                width: 48
                height: 30
                onClicked: addTag()
            }
        }
        Row {
            visible: root.currentId >= 0
            PMButton {
                objectName: "tagPickerBtn"
                tooltip: I18n.tr("从层级标签树中选择要添加的标签")
                text: I18n.tr("从标签树选择…")
                height: 26
                onClicked: root.tagPickerRequested()
            }
        }
    }
}
