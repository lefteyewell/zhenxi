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
pragma Singleton
import QtQuick
import i18n 1.0

QtObject {
    id: theme

    /* ---------- 配色方案 ----------
     * 每项字段：id / name / primary 主色 / accent 强调色
     *           lightBg lightFg 浅色模式 / darkBg darkFg 深色模式
     * name 顺序必须与 Python 端 ThemeController.SCHEME_NAMES 一致
     */
    property var schemes: [
        { id: "ocean",    name: I18n.tr("海洋蓝"), primary: "#1E88E5", accent: "#00BCD4", lightBg: "#F5F7FA", lightFg: "#1A2332", darkBg: "#0F1722", darkFg: "#E8EDF4" },
        { id: "forest",   name: I18n.tr("森林绿"), primary: "#2E7D32", accent: "#8BC34A", lightBg: "#F4F8F3", lightFg: "#14261B", darkBg: "#0E1A12", darkFg: "#E2F0E6" },
        { id: "sunset",   name: I18n.tr("落日橙"), primary: "#EF6C00", accent: "#FFB300", lightBg: "#FDF6EE", lightFg: "#2A1B0E", darkBg: "#1C130A", darkFg: "#F7E8D8" },
        { id: "rose",     name: I18n.tr("玫瑰粉"), primary: "#D81B60", accent: "#F06292", lightBg: "#FCF5F8", lightFg: "#2A1420", darkBg: "#1C0F16", darkFg: "#F6E3EC" },
        { id: "violet",   name: I18n.tr("紫罗兰"), primary: "#6A1B9A", accent: "#AB47BC", lightBg: "#F8F5FC", lightFg: "#1E1528", darkBg: "#130D1C", darkFg: "#EBE2F6" },
        { id: "graphite", name: I18n.tr("石墨灰"), primary: "#455A64", accent: "#90A4AE", lightBg: "#F4F6F7", lightFg: "#1C2428", darkBg: "#12181B", darkFg: "#E0E6E9" },
        { id: "nebula",   name: I18n.tr("星空紫"), primary: "#3949AB", accent: "#26C6DA", lightBg: "#F4F5FC", lightFg: "#151A33", darkBg: "#0D1020", darkFg: "#E3E6F8" },
        { id: "jade",     name: I18n.tr("翡翠绿"), primary: "#00695C", accent: "#4DB6AC", lightBg: "#F2F9F7", lightFg: "#0F2320", darkBg: "#0A1715", darkFg: "#DDF0EC" },
        /* ACDSee Photo Studio 风格：中性深灰 + 专业蓝，长时间修图不刺眼 */
        { id: "studio",   name: I18n.tr("影棚深灰"), primary: "#0078D4", accent: "#2AA9E0", lightBg: "#F2F2F2", lightFg: "#1F1F1F", darkBg: "#1F1F1F", darkFg: "#EDEDED" }
    ]

    property int schemeIndex: 0
    onSchemeIndexChanged: Qt.callLater(apply)
    property bool dark: false
    onDarkChanged: Qt.callLater(apply)

    property string fontFamily: Qt.platform.os === "windows" ? "Microsoft YaHei UI"
                              : (Qt.platform.os === "linux" ? "Noto Sans CJK SC" : "sans-serif")

    /* 运行时色调（apply 时由配色派生） */
    property color primary: "#1E88E5"
    property color primaryDark: "#1565C0"
    property color textOnPrimary: "#FFFFFF"
    property color accent: "#00BCD4"
    property color bg: "#F5F7FA"
    property color surface: "#FFFFFF"
    property color surfaceAlt: "#ECF0F5"
    property color text: "#1A2332"
    property color textDim: "#7A8699"
    property color divider: "#D9E0E8"
    property color hover: "#E4EAF2"
    property color success: "#43A047"
    property color warning: "#F9A825"
    property color danger: "#E53935"

    /* 尺寸与圆角 */
    property int radiusSmall: 4
    property int radiusMedium: 8
    property int radiusLarge: 14
    property int spacingTiny: 4
    property int spacingSmall: 8
    property int spacingMedium: 16
    property int spacingLarge: 24
    property int headerHeight: 56
    property int navWidth: 216
    property int infoWidth: 288

    function apply() {
        var s = schemes[Math.max(0, Math.min(schemes.length - 1, schemeIndex))]
        if (!s) return
        primary = s.primary
        accent = s.accent
        if (dark) {
            bg = s.darkBg
            surface = Qt.lighter(s.darkBg, 1.18)
            surfaceAlt = Qt.lighter(s.darkBg, 1.10)
            text = s.darkFg
            divider = Qt.rgba(1, 1, 1, 0.10)
            hover = Qt.rgba(1, 1, 1, 0.06)
            textDim = Qt.rgba(1, 1, 1, 0.55)
        } else {
            bg = s.lightBg
            surface = "#FFFFFF"
            surfaceAlt = Qt.lighter(s.lightBg, 0.96)
            text = s.lightFg
            divider = "#D9E0E8"
            hover = "#E4EAF2"
            textDim = "#7A8699"
        }
    }

    Component.onCompleted: apply()
}
