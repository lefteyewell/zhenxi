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
import QtMultimedia
import theme 1.0
import components 1.0
import i18n 1.0

/* 视频内嵌播放器（0.5.44 V2）：MediaPlayer + VideoOutput。
   打开失败（典型=麒麟缺 gstreamer 编解码）→ failed=true，显示兜底：
   「用系统默认播放器打开」（LibraryBridge.openExternal），不劣于 V1。 */
Popup {
    id: root
    objectName: "videoPlayer"
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 900
    height: 620
    padding: 0

    property string rawPath: ""
    property bool failed: false

    function _fmt(ms) {
        if (!ms || ms <= 0) return "00:00"
        var s = Math.floor(ms / 1000)
        var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60
        var mm = (m < 10 ? "0" : "") + m, sss = (ss < 10 ? "0" : "") + ss
        return h > 0 ? (h + ":" + mm + ":" + sss) : (mm + ":" + sss)
    }

    function openVideo(path) {
        if (!path || path.length === 0) return
        root.rawPath = path
        root.failed = false
        player.stop()
        // 本地文件转 file:// URL；encodeURI 处理空格与中文路径
        var p = path.replace(/\\/g, "/")
        player.source = "file:///" + encodeURI(p)
        root.open()
        player.play()
    }

    onClosed: player.stop()

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    MediaPlayer {
        id: player
        videoOutput: videoOut
        audioOutput: AudioOutput { id: audio; volume: 0.8 }
        onErrorOccurred: (error, errorString) => {
            if (error !== MediaPlayer.NoError) root.failed = true
        }
        onMediaStatusChanged: (status) => {
            if (status === MediaPlayer.InvalidMedia) root.failed = true
        }
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall
            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 44 }
            Text {
                text: root.rawPath ? root.rawPath.split(/[\\/]/).pop() : I18n.tr("视频播放")
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideMiddle
                Layout.maximumWidth: 420
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: "✕"
                width: 40
                height: 28
                tooltip: I18n.tr("关闭")
                onClicked: root.close()
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            VideoOutput {
                id: videoOut
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
            }
            Rectangle {
                anchors.fill: parent
                visible: root.failed
                color: Theme.bg
                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: Theme.spacingMedium
                    Text {
                        text: I18n.tr("⚠ 当前环境无法内嵌播放该视频")
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        color: Theme.text
                    }
                    Text {
                        text: I18n.tr("（可能缺少解码组件，如麒麟需安装 gstreamer）")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                    }
                    PMButton {
                        objectName: "vpFallbackOpen"
                        text: I18n.tr("用系统默认播放器打开")
                        onClicked: LibraryBridge.openExternal(root.rawPath)
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall
            PMButton {
                objectName: "vpPlayPause"
                text: player.playbackState === MediaPlayer.PlayingState ? "⏸" : "▶"
                width: 44
                height: 30
                onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
            }
            Text {
                text: root._fmt(player.position)
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            Slider {
                id: seek
                Layout.fillWidth: true
                from: 0
                to: player.duration > 0 ? player.duration : 1
                value: player.position
                onMoved: player.position = value
                enabled: player.seekable && player.duration > 0
            }
            Text {
                text: root._fmt(player.duration)
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            PMButton {
                text: audio.volume > 0 ? "🔊" : "🔇"
                width: 40
                height: 30
                onClicked: audio.volume = audio.volume > 0 ? 0 : 0.8
            }
        }
    }
}
