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
import theme 1.0

/* 轻提示：底部居中浮层，短暂显示后自动淡出。
   用法：Toast { id: toastLayer }，show(text, kind) kind ∈ success / warning / error。
   0.6.24 补17（用户反馈：文字多时显示不全、固定 3.2s 看不完）：
   ① 时长随文字长度伸缩（3s 起步、每字 75ms、上限 12s）；
   ② 长文字自动折行（最多 4 行），高度自适应，不再截断；
   ③ 鼠标悬停暂停倒计时，移开继续；点击立即关闭。 */
Rectangle {
    id: root
    objectName: "toastLayer"

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 52
    width: Math.min(560, parent.width - 48)
    height: msgText.lineCount > 1
            ? Math.min(40 + (msgText.lineCount - 1) * 19, 96) : 40
    radius: 20
    visible: false
    opacity: 0
    z: 1000

    property string _kind: "success"

    function show(text, kind) {
        root._kind = kind || "success"
        if (root._kind === "error") root.color = Theme.danger
        else if (root._kind === "warning") root.color = Theme.warning
        else root.color = Theme.success
        msgText.text = text || ""
        /* 时长随文字长度伸缩：短提示 3s，长提示给足阅读时间 */
        hideTimer.interval = Math.min(12000, 3000 + (text || "").length * 75)
        root.visible = true
        animIn.restart()
        hideTimer.restart()
    }

    Text {
        id: msgText
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        maximumLineCount: 4
        elide: Text.ElideRight
        font.family: Theme.fontFamily
        font.pixelSize: 13
        color: "white"
    }

    /* 悬停暂停倒计时（看得慢可以慢慢看）；点击立即关闭 */
    MouseArea {
        id: toastHover
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onContainsMouseChanged: {
            if (!root.visible)
                return
            if (containsMouse)
                hideTimer.stop()
            else
                hideTimer.restart()
        }
        onClicked: {
            hideTimer.stop()
            animOut.start()
        }
    }

    NumberAnimation {
        id: animIn
        target: root
        property: "opacity"
        from: 0
        to: 1
        duration: 150
    }

    Timer {
        id: hideTimer
        interval: 3200
        repeat: false
        onTriggered: animOut.start()
    }

    NumberAnimation {
        id: animOut
        target: root
        property: "opacity"
        from: 1
        to: 0
        duration: 200
        onFinished: root.visible = false
    }
}
