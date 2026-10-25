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

/* 高级搜索面板：组合条件生成查询串（语法见 core/search.py） */
Popup {
    id: root

    objectName: "advancedSearch"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 520
    /* 0.5.67：高度自适应屏幕并加大——此前固定 560 而字段区不可滚动，
       底部按钮被挤出弹窗（用户反馈）。字段区包进 ScrollView 后不再溢出。 */
    height: Math.min(640, (parent ? parent.height : 600) - 40)
    padding: Theme.spacingMedium

    signal searchRequested(string query)

        function buildQuery() {
        var parts = []
        if (keywordField.text) parts.push(keywordField.text.trim())
        if (clipField.text.trim()) parts.push("clip:" + clipField.text.trim())
        if (dateFromField.text || dateToField.text)
            parts.push("dates:" + (dateFromField.text || "1970-01-01")
                       + ".." + (dateToField.text || "2999-12-31"))
        if (cameraField.text) parts.push("camera:" + cameraField.text.trim())
        if (tagField.text) parts.push("tag:" + tagField.text.trim())
        if (personField.text) parts.push("person:" + personField.text.trim())
        if (gpsField.text.trim()) parts.push("gps:" + gpsField.text.trim())
        if (facesField.text.trim()) parts.push("faces:" + facesField.text.trim())
        if (ratingField.text.trim()) parts.push("rating:" + ratingField.text.trim())
        if (flagBox.currentIndex > 0) parts.push("flag:" + flagBox.currentText)
        if (colorBox.currentIndex > 0) {
            var cv = ["", "red", "yellow", "green", "blue", "purple", "none"][colorBox.currentIndex]
            parts.push("color:" + cv)
        }
        if (typeBox.currentIndex > 0) {
            var t = typeBox.currentText.trim()
            // "raw" 是聚合项：展开为全部 RAW 扩展名的 OR 查询
            // （ext 字段存具体扩展名如 cr3/nef，ext:raw 用 LIKE 匹配不到任何记录）
            if (t === "raw") {
                var rawExts = ["cr2", "cr3", "nef", "arw", "dng",
                               "orf", "rw2", "pef", "raf", "srw"]
                parts.push(rawExts.map(e => "ext:" + e).join(" OR "))
            } else {
                parts.push("ext:" + t)
            }
        }
        return parts.join(" ")
    }

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: Column {
        spacing: Theme.spacingSmall

        RowLayout {
            width: parent.width
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 22 }

            Text {
                text: I18n.tr("高级搜索")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
            }
        }

        /* 0.5.67：字段区包进 ScrollView——字段行数多于弹窗高度时滚动查看，
           底部按钮固定在弹窗内不再被挤出 */
        ScrollView {
            width: parent.width
            height: root.height - 132
            contentWidth: width
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

            Column {
                width: parent.width
                spacing: Theme.spacingSmall

        Text {
            text: I18n.tr("关键词（文件名 / 相机 / OCR 文字）")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
        }
        TextField {
            id: keywordField
            objectName: "keywordField"
            width: parent.width
            height: 30
            placeholderText: I18n.tr("如：年会")
            color: Theme.text
            placeholderTextColor: Theme.textDim
            font.pixelSize: 12
            font.family: Theme.fontFamily
            background: Rectangle {
                radius: 6
                color: Theme.bg
                border.width: 1
                border.color: Theme.divider
            }
        }

        Text {
            text: I18n.tr("语义搜索（中文以文搜图，需先生成语义向量）")
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textDim
        }
        TextField {
            id: clipField
            objectName: "clipField"
            width: parent.width
            height: 30
            placeholderText: I18n.tr("如：一张海边日落的照片")
            color: Theme.text
            placeholderTextColor: Theme.textDim
            font.pixelSize: 12
            font.family: Theme.fontFamily
            background: Rectangle {
                radius: 6
                color: Theme.bg
                border.width: 1
                border.color: Theme.divider
            }
        }

        Grid {
            columns: 2
            spacing: 8
            columnSpacing: 16

            Text {
                text: I18n.tr("拍摄日期起")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: dateFromField
            objectName: "dateFromField"
                width: 150
                height: 28
                placeholderText: "2025-03-01"
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("拍摄日期止")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: dateToField
            objectName: "dateToField"
                width: 150
                height: 28
                placeholderText: "2025-12-31"
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("相机")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: cameraField
            objectName: "cameraField"
                width: 150
                height: 28
                placeholderText: I18n.tr("Canon（可 a,b）")
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("标签")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: tagField
            objectName: "tagField"
                width: 150
                height: 28
                placeholderText: I18n.tr("重要（可 a,b）")
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("人物")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: personField
            objectName: "personField"
                width: 150
                height: 28
                placeholderText: I18n.tr("王老师")
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("位置 (lat,lon,km)")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: gpsField
            objectName: "gpsField"
                width: 150
                height: 28
                placeholderText: "39.9,116.3,5"
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("人脸数")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: facesField
            objectName: "facesField"
                width: 150
                height: 28
                placeholderText: "2 / 0 / >2"
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("评级")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            TextField {
                id: ratingField
            objectName: "ratingField"
                width: 150
                height: 28
                placeholderText: ">=3 / 5 / 0"
                color: Theme.text
                font.pixelSize: 12
                font.family: Theme.fontFamily
                background: Rectangle {
                    radius: 6
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Text {
                text: I18n.tr("旗标")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            ComboBox {
                id: flagBox
                objectName: "flagBox"
                width: 150
                height: 28
                model: [I18n.tr("全部"), "pick", "reject", "none", "archive"]
            }

            Text {
                text: I18n.tr("类型")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            ComboBox {
                id: typeBox
                objectName: "typeBox"
                width: 150
                height: 28
                model: [I18n.tr("全部"), "jpg", "png", "cr3", "nef", "arw", "dng", "raw"]
            }

            Text {
                text: I18n.tr("色标")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                width: 90
            }
            ComboBox {
                id: colorBox
                objectName: "colorBox"
                width: 150
                height: 28
                model: [I18n.tr("全部"), I18n.tr("红"), I18n.tr("黄"), I18n.tr("绿"), I18n.tr("蓝"), I18n.tr("紫"), I18n.tr("无色标")]
            }
        }
        } /* 0.5.67 收口：字段 Column */
        } /* 0.5.67 收口：ScrollView */

        Row {
            width: parent.width
            spacing: Theme.spacingSmall
            layoutDirection: Qt.RightToLeft

            PMButton {
                objectName: "advSearchClose"
                text: I18n.tr("关闭")
                onClicked: root.close()
            }
            PMButton {
                objectName: "advSearchBtn"
                text: I18n.tr("搜索")
                onClicked: {
                    root.searchRequested(root.buildQuery())
                    root.close()
                }
            }
            PMButton {
                text: I18n.tr("清空")
                onClicked: {
                    keywordField.text = ""
                    clipField.text = ""
                    dateFromField.text = ""
                    dateToField.text = ""
                    cameraField.text = ""
                    tagField.text = ""
                    personField.text = ""
                    gpsField.text = ""
                    facesField.text = ""
                    ratingField.text = ""
                    flagBox.currentIndex = 0
                    typeBox.currentIndex = 0
                    colorBox.currentIndex = 0
                }
            }
        }

        Text {
            text: I18n.tr("提示：搜索框也支持语法，如 `-tag:草稿`、`dates:2025-01-01..2025-06-30`、`a OR b`")
            width: parent.width
            font.family: Theme.fontFamily
            font.pixelSize: 10
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
    }

}
