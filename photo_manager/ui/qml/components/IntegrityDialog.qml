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

/* 库完整性校验报告（#7）。
   只读校验结果：缺失 / 被改动 / 缩略图丢失 / 分析失败 四类。
   其中「缺失」不提供自动修复——文件是否真丢由用户判断，程序不擅自清除记录
   （不删除红线），需到回收站的「缺失照片」区处理。
   其余三类可「重新分析」：把照片置为待分析并重跑派生数据（缩略图/元数据/向量），
   只重建库内数据，绝不动原图。 */
Dialog {
    id: root
    objectName: "integrityDialog"
    title: I18n.tr("库完整性校验")
    modal: true
    standardButtons: Dialog.Close
    /* 0.5.41：自定义可拖动标题栏 */
    header: RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Theme.spacingMedium
        Layout.rightMargin: Theme.spacingMedium
        Layout.preferredHeight: 40
        PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 40 }
        Text {
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Item { Layout.fillWidth: true }
    }
    width: 620
    /* 0.5.35：520 高时底部说明文字溢出 84px（内容总高>容器），加高到 640 */
    height: 640

    property string reportJson: ""
    property string currentKind: "missing"
    property var counts: ({})

    readonly property var kinds: [
        { key: "missing",      label: I18n.tr("文件缺失"),   desc: I18n.tr("磁盘上已找不到（系统外删除或外接盘未连接）"), fixable: false },
        { key: "changed",      label: I18n.tr("文件被改动"), desc: I18n.tr("大小/修改时间与库不符，索引的元数据可能已过期"), fixable: true },
        { key: "thumbMissing", label: I18n.tr("缩略图丢失"), desc: I18n.tr("原图在但缩略图没了，网格会显示空白"), fixable: true },
        { key: "error",        label: I18n.tr("分析失败"),   desc: I18n.tr("分析阶段出错，人脸/文字等结果缺失"), fixable: true },
        { key: "decodeError",  label: I18n.tr("无法解码"),   desc: I18n.tr("全图数据无法解码（截断/损坏），预览为相机内嵌图，导出原图前请知悉"), fixable: false }
    ]

    signal repairRequested(string kind)

    function showReport(js) {
        root.reportJson = js || ""
        var obj = {}
        try { obj = JSON.parse(root.reportJson) } catch (e) { obj = {} }
        root.counts = obj.counts || {}
        totalText.text = I18n.tr("共 ") + (obj.total || 0) + I18n.tr(" 张 · 正常 ") + (obj.ok || 0) + I18n.tr(" 张")
        // 默认落在第一个有问题的类别
        root.currentKind = "missing"
        for (var i = 0; i < root.kinds.length; ++i) {
            if ((root.counts[root.kinds[i].key] || 0) > 0) {
                root.currentKind = root.kinds[i].key
                break
            }
        }
        root.refreshIssues()
        root.open()
    }

    function refreshIssues() {
        issueModel.clear()
        var arr = LibraryBridge ? LibraryBridge.integrityIssues(root.currentKind, 0, 200) : []
        for (var i = 0; i < arr.length; ++i)
            issueModel.append(arr[i])
        emptyText.visible = issueModel.count === 0
    }

    function currentMeta() {
        for (var i = 0; i < root.kinds.length; ++i)
            if (root.kinds[i].key === root.currentKind) return root.kinds[i]
        return root.kinds[0]
    }

    ListModel { id: issueModel }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingMedium
        spacing: Theme.spacingSmall

        RowLayout {
            Layout.fillWidth: true
            Text {
                id: totalText
                Layout.fillWidth: true
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                text: I18n.tr("共 0 张 · 正常 0 张")
            }
            PMButton {
                objectName: "integrityDeepCheckBtn"
                tooltip: I18n.tr("对 RAW/HEIC 等非常规格式逐张试全图解码，主动发现损坏文件")
                        + I18n.tr("\n（约 0.2~0.4 秒/张，后台执行；完成后自动刷新本报告）")
                text: I18n.tr("深度解码检查")
                height: 28
                onClicked: {
                    if (LibraryBridge) LibraryBridge.deepDecodeCheck()
                }
            }
        }

        /* 四类问题：点击切换查看清单 */
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSmall
            Repeater {
                model: root.kinds
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 62
                    radius: Theme.radiusMedium
                    color: root.currentKind === modelData.key ? Theme.hover : Theme.surfaceAlt
                    border.width: root.currentKind === modelData.key ? 1 : 0
                    border.color: Theme.primary
                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.counts[modelData.key] || 0
                            font.family: Theme.fontFamily
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            color: (root.counts[modelData.key] || 0) > 0 ? Theme.danger : Theme.textDim
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.currentKind = modelData.key; root.refreshIssues() }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.currentMeta().desc
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
            PMButton {
                objectName: "integrityRepairBtn"
                tooltip: I18n.tr("自动修复发现的问题")
                text: I18n.tr("重新分析此类（") + (root.counts[root.currentKind] || 0) + "）"
                height: 28
                enabled: root.currentMeta().fixable && (root.counts[root.currentKind] || 0) > 0
                onClicked: root.repairRequested(root.currentKind)
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.surface
            radius: Theme.radiusMedium
            border.width: 1
            border.color: Theme.divider

            ListView {
                id: issueList
                objectName: "integrityIssueList"
                anchors.fill: parent
                anchors.margins: Theme.spacingSmall
                clip: true
                spacing: Theme.spacingTiny
                ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }
                model: issueModel
                delegate: RowLayout {
                    width: issueList.width
                    height: 40
                    spacing: Theme.spacingSmall
                    Rectangle {
                        width: 32; height: 32
                        radius: Theme.radiusSmall
                        color: Theme.surfaceAlt
                        Image {
                            anchors.fill: parent
                            source: model.thumb || ""
                            fillMode: Image.PreserveAspectCrop
                            visible: !!model.thumb
                        }
                    }
                    Column {
                        Layout.fillWidth: true
                        Text {
                            text: model.name
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                            elide: Text.ElideRight
                            width: parent.width
                        }
                        Text {
                            text: model.folder
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                            color: Theme.textDim
                            elide: Text.ElideRight
                            width: parent.width
                        }
                    }
                }
            }

            Text {
                id: emptyText
                anchors.centerIn: parent
                visible: false
                text: I18n.tr("这一类没有问题")
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textDim
            }
        }

        Text {
            Layout.fillWidth: true
            text: I18n.tr("说明：校验只读，不会改动或删除任何照片。「文件缺失」不自动清除——")
                  + I18n.tr("可到回收站的「缺失照片」区确认后处理；其余三类「重新分析」只重建库内缩略图与元数据，原图不受影响。")
            font.family: Theme.fontFamily
            font.pixelSize: 10
            color: Theme.textDim
            wrapMode: Text.Wrap
        }
    }
}
