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

/* 0.6.21：随包文本查看器（帮助菜单「开源许可 / 第三方依赖」入口）。
   按需从安装目录读取 LICENSE / THIRD-PARTY-NOTICES.md 全文展示，
   只读、可滚动、可全选复制。
   0.7.3b：LICENSE 增加「中文参考版」页签（用户反馈：帮助理解）——
   内嵌简要中文导读，明确标注非官方翻译、以英文原文为准；
   英文原文一键切回。其他随包文档不显示页签。 */
Dialog {
    id: root
    objectName: "textDocDialog"

    modal: true
    width: Math.min(parent ? parent.width - 80 : 860, 820)
    height: Math.min(parent ? parent.height - 80 : 640, 620)
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 0

    title: ""

    /* 0.7.3b：页签状态——false 英文原文（默认，法律效力所在），
       true 中文参考版。仅打开 LICENSE 时可切换。 */
    property bool showZh: false
    property bool hasZhDoc: false

    /* GPLv3 简要中文参考（非官方翻译）。逐条概括核心条款，不覆盖全部
       细节；行文固定中文，不进 i18n（对英文用户无意义）。 */
    readonly property string zhLicenseText: [
        "【GPLv3 中文参考版 · 非官方翻译，仅供参考】",
        "",
        "本页帮助理解 GNU 通用公共许可证第 3 版的核心内容，不构成法律文本；",
        "权利与义务以英文原文（切「英文原文」页签）为准。",
        "",
        "一、你可以自由做的事",
        "· 任何目的运行本程序（个人、学习、商用均可，免授权费）；",
        "· 研究源码，并按自己的需要修改；",
        "· 复制、分发原程序；发布修改后的版本。",
        "",
        "二、分发时必须做到",
        "· 向接收者提供完整对应源码，或注明可免费获取源码的渠道；",
        "· 以 GPLv3（或兼容的后续版本）继续授权——接收者享有与你相同的",
        "  四项自由，不能把修改版改成专有软件闭源发行；",
        "· 保留版权声明、许可声明与「不提供担保」声明；",
        "· 对修改过的版本，须显著标注「已修改」及日期。",
        "",
        "三、不提供担保",
        "本程序按「现状」提供，在法律允许范围内不附带任何担保：不保证",
        "不出错、不保证适合特定用途、不保证性能无损。使用风险自行承担。",
        "",
        "四、责任限制",
        "除非法律另有强制规定或书面另行承诺，版权人与贡献者不对使用本",
        "程序造成的任何直接或间接损失承担责任。",
        "",
        "五、其他要点",
        "· 分发即授权：你分发程序时，自动向所有接收者授予其中所含专利的",
        "  使用许可；",
        "· 仅将程序作为网络服务提供（不向用户分发）不触发源码提供义务；",
        "· 本项目采用 GPLv3 与商业许可双授权：如需闭源商用集成，",
        "  请通过「关于」弹窗中的项目主页联系作者洽谈商业授权。",
        "",
        "（以上为通俗概括，条款适用与解释以英文原文为准。）"
    ].join("\n")

    function openDoc(docTitle, fileName) {
        root.title = docTitle
        root.hasZhDoc = (fileName === "LICENSE")
        root.showZh = false
        docText.text = I18n.tr("加载中…")
        root.open()
        /* open 后下一拍再读，避免阻塞打开动画（文本可达数十 KB） */
        Qt.callLater(function() {
            docText.text = LibraryBridge.readPackagedText(fileName)
        })
    }

    function _applyTab() {
        if (!root.hasZhDoc)
            return
        docText.text = root.showZh
            ? root.zhLicenseText
            : LibraryBridge.readPackagedText("LICENSE")
    }

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.width: 1
        border.color: Theme.divider
    }

    header: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 46
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingSmall
            spacing: Theme.spacingSmall

            Text {
                text: root.title
                Layout.fillWidth: true
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideRight
            }

            /* 0.7.3b：LICENSE 双页签（中文参考版 / 英文原文） */
            Row {
                visible: root.hasZhDoc
                spacing: 4

                PMButton {
                    text: I18n.tr("中文参考版")
                    height: 28
                    emphasized: root.showZh
                    tooltip: I18n.tr("非官方中文导读，仅供参考；法律效力以英文原文为准")
                    onClicked: {
                        if (!root.showZh) {
                            root.showZh = true
                            root._applyTab()
                        }
                    }
                }
                PMButton {
                    text: I18n.tr("英文原文")
                    height: 28
                    emphasized: !root.showZh
                    tooltip: I18n.tr("许可证官方全文（随包 LICENSE 文件）")
                    onClicked: {
                        if (root.showZh) {
                            root.showZh = false
                            root._applyTab()
                        }
                    }
                }
            }

            PMButton {
                tooltip: I18n.tr("关闭")
                text: "×"
                width: 32
                height: 28
                onClicked: root.close()
            }
        }
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }
    }

    ScrollView {
        anchors.fill: parent
        ScrollBar.horizontal.policy: ScrollBar.AsNeeded

        TextArea {
            id: docText
            readOnly: true
            wrapMode: TextArea.NoWrap
            selectByMouse: true
            persistentSelection: true
            color: Theme.text
            selectionColor: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: 12
            topPadding: 12
            bottomPadding: 12
            leftPadding: 16
            rightPadding: 16
            background: null
        }
    }
}
