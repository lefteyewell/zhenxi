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

/* 0.5.53：首次运行引导弹窗。
   注意事项 + 重要设置一览；「一键应用推荐设置」批量开启；勾选I18n.tr("不再显示")
   （默认勾选）后，点「开始使用」或关闭弹窗都会写入标记不再自动弹出；
   帮助菜单「首次使用引导…」可随时重开。 */
Popup {
    id: root
    objectName: "firstRunDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape
    width: Math.min(parent ? parent.width - 60 : 600, 580)
    height: contentCol.implicitHeight + padding * 2
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    /* 恢复各项勾选与根目录显示为当前设置状态。
       0.5.57：自动复制入库仅在已设置根目录时可用；未设置根目录时不默认任何库根。 */
    function refreshChecks() {
        if (!LibraryBridge) return
        autoStartChk.checked = LibraryBridge.autoStartEnabled()
        trayChk.checked = LibraryBridge.trayEnabled()
        var roots = LibraryBridge.libraryRoots().trim()
        rootDirText.text = roots || I18n.tr("（未设置）")
        copyChk.enabled = roots !== ""
        copyChk.checked = roots !== "" && LibraryBridge.copyToLibraryEnabled()
        if (roots === "")
            copyChk.text = I18n.tr("导入时自动复制入库（设置根目录后可用）")
        else
            copyChk.text = I18n.tr("导入时自动复制入库")
    }

    contentItem: ColumnLayout {
        id: contentCol
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 34 }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: I18n.tr("欢迎使用真昔")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Item { Layout.fillWidth: true }
            /* 0.5.66：移除头部"关闭"按钮（用户反馈：与"开始使用"重复。
               二者本有差异——I18n.tr("关闭")不写标记下次仍弹、ESC 同；现只留I18n.tr("开始使用")，
               ESC 仍可作为I18n.tr("暂不决定")的退出路径） */
        }

        Column {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: 4

            Text {
                width: parent.width
                text: I18n.tr("· <b>照片原图只读</b>：本软件绝不修改、移动或删除任何照片文件，所有整理信息保存在独立数据库中；")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
                wrapMode: Text.Wrap
            }
            Text {
                width: parent.width
                text: I18n.tr("· 分析（人脸 / 文字 / 重复检测 / 语义向量）在<b>后台自动进行</b>，期间可正常浏览与管理照片；")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
                wrapMode: Text.Wrap
            }
            Text {
                width: parent.width
                text: I18n.tr("· 关闭窗口默认<b>最小化到系统托盘</b>继续后台运行，右键托盘图标可退出。")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.text
                wrapMode: Text.Wrap
            }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1
                    Layout.leftMargin: Theme.spacingMedium
                    Layout.rightMargin: Theme.spacingMedium; color: Theme.divider }

        /* 0.5.56：照片库根目录配置（强烈建议） */
        Column {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: 4

            Text {
                width: parent.width
                text: I18n.tr("<b>照片库根目录（强烈建议现在设置）</b>")
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.weight: Font.DemiBold
                color: Theme.primary
                wrapMode: Text.Wrap
            }
            Text {
                width: parent.width
                text: I18n.tr("不设置的话，照片会散落在各个原始位置管理：<b>日后原文件被移动、改名或删除时，")
                      + I18n.tr("这些照片将被标记为「系统外删除」而不可见</b>，整理成果与照片本体分离，容易造成混乱。")
                      + I18n.tr("设置根目录并开启自动复制入库后，新导入的照片会集中收纳、统一管理。")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
            Row {
                width: parent.width
                spacing: Theme.spacingSmall

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - pickRootBtn.width - parent.spacing
                    text: I18n.tr("当前：") + rootDirText.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.text
                    elide: Text.ElideMiddle
                }
                PMButton {
                    id: pickRootBtn
                    objectName: "firstRunPickRootBtn"
                    text: I18n.tr("选择根目录…")
                    height: 26
                    onClicked: {
                        var cur = LibraryBridge.libraryRoots().split("\n")[0] || ""
                        var p = LibraryBridge.pickFolder(I18n.tr("选择照片库根目录"), cur)
                        if (!p) return
                        if (LibraryBridge.addLibraryRoot(p)) {
                            rootDirText.text = p
                            copyChk.enabled = true
                            copyChk.checked = true
                            LibraryBridge.setCopyToLibraryEnabled(true)
                            appliedText.text = I18n.tr("已设置照片库根目录：") + p
                                  + I18n.tr("（已默认开启导入时自动复制入库，可在下方取消勾选）")
                        } else {
                            appliedText.text = I18n.tr("设置失败：目录不存在或不可访问")
                        }
                    }
                }
            }
            Text {
                width: parent.width
                text: I18n.tr("可添加多个根目录；此后随时可在 设置 → 照片库根目录 中增删。")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                wrapMode: Text.Wrap
            }
            Text {
                id: rootDirText
                visible: false
                text: I18n.tr("（未设置）")
            }
            CheckBox {
                id: copyChk
                objectName: "firstRunCopyChk"
                text: I18n.tr("导入时自动复制入库（设置根目录后可用）")
                font.pixelSize: 12
                enabled: false
                onToggled: LibraryBridge.setCopyToLibraryEnabled(checked)
            }
        }

        /* 0.5.57：三个选项同一行；移除"一键应用推荐设置" */
        Row {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingMedium

            CheckBox {
                id: autoStartChk
                objectName: "firstRunAutoStartChk"
                text: I18n.tr("开机自启动")
                font.pixelSize: 12
                onToggled: LibraryBridge.setAutoStartEnabled(checked)
            }
            CheckBox {
                id: trayChk
                objectName: "firstRunTrayChk"
                text: I18n.tr("关闭时最小化到托盘")
                font.pixelSize: 12
                onToggled: LibraryBridge.setTrayEnabled(checked)
            }
            CheckBox {
                id: firstRunAgainChk
                objectName: "firstRunAgainChk"
                text: I18n.tr("不再显示此引导")
                font.pixelSize: 12
                checked: false
            }
        }

        Text {
            id: appliedText
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            text: ""
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.dark ? "#81C784" : "#2E7D32"
            wrapMode: Text.Wrap
        }

        Row {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            Item { Layout.fillWidth: true; width: 8 }
            PMButton {
                objectName: "firstRunStartBtn"
                text: I18n.tr("开始使用")
                height: 32
                emphasized: true
                onClicked: {
                    /* 明确点击「开始使用」= 结束引导（无论是否勾选"不再显示"） */
                    if (LibraryBridge) LibraryBridge.setFirstRunDone()
                    root.close()
                }
            }
        }
    }

    onOpened: root.refreshChecks()
    onClosed: {
        /* 0.5.57：默认不勾"不再显示"——直接关闭不写标记，下次启动仍弹出 */
        if (firstRunAgainChk.checked && LibraryBridge)
            LibraryBridge.setFirstRunDone()
    }
}
