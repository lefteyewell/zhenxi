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

/* 0.6.23：Canvas 手绘对勾——用户反馈 √ 是根号不是对勾、✓ 在麒麟精简
   系统缺字形显示方块；改为矢量绘制，双平台零字体依赖。
   用法：放在徽标圆内 anchors.fill: parent 即可。 */
Canvas {
    id: root

    property color markColor: "white"
    property real strokeWidth: 2

    onMarkColorChanged: requestPaint()
    onStrokeWidthChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onVisibleChanged: if (visible) requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        if (width <= 0 || height <= 0)
            return
        ctx.strokeStyle = String(markColor)
        ctx.lineWidth = strokeWidth
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        var w = width
        var h = height
        ctx.beginPath()
        ctx.moveTo(w * 0.20, h * 0.52)
        ctx.lineTo(w * 0.42, h * 0.74)
        ctx.lineTo(w * 0.80, h * 0.26)
        ctx.stroke()
    }
}
