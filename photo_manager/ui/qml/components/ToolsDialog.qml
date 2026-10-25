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

/* 工具中心（0.5.25 重设计）：
   - 分区折叠手风琴（同一时间只展开一个分区），默认展开I18n.tr("智能分析")
   - 底部固定I18n.tr("任务进度")区（不随内容滚动，修复旧版底部按钮/文字显示不全）
   - 内容区带可见滚动条 */
Popup {
    id: root

    objectName: "toolsDialog"

    signal backupRequested()    // 交由窗口级 backupPicker 处理
    signal restoreRequested()   // 交由窗口级 restorePicker 处理
    signal syncOutRequested()   // 交由窗口级 syncOutPicker 处理
    signal csvRequested()       // 交由窗口级 csvPicker 处理

    /* 当前展开的分区（手风琴；""=全部收起） */
    property string openSection: "analysis"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 620
    height: 620
    padding: 0

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    /* 场景建议行（0.5.27）：复选框 + 词名 + 照片数 */
    component SceneSugRow: Row {
        property string word: ""
        property int count: 0
        property bool picked: true
        spacing: 6
        CheckBox {
            checked: true
            onToggled: picked = checked
        }
        Text {
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: parent.word + I18n.tr("（约 ") + parent.count + I18n.tr(" 张）")
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.text
        }
    }

    /* 分区头（0.5.25）：点击展开该分区并收起其它分区 */
    component ToolSectionHeader: Rectangle {
        id: sectionHeader
        property string ident: ""
        property string title: ""
        objectName: "toolSecHead" + ident
        width: parent ? parent.width : 0
        height: 34
        radius: 6
        color: headArea.containsMouse || root.openSection === ident
               ? Theme.hover : Theme.surfaceAlt
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: (root.openSection === sectionHeader.ident ? "▾ " : "▸ ") + sectionHeader.title
            font.family: Theme.fontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: Theme.text
        }
        MouseArea {
            id: headArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.openSection = (root.openSection === sectionHeader.ident ? "" : sectionHeader.ident)
        }
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 52 }

            Column {
                spacing: 2
                Text {
                    text: I18n.tr("工具中心")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("智能分析与数据库维护（后台执行，底部显示进度）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("关闭")
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: Theme.spacingSmall
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            clip: true
            contentHeight: panelCol.height

            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }

            Column {
                id: panelCol
                width: root.width - Theme.spacingLarge * 2 - 10
                spacing: Theme.spacingSmall

                /* ---- 智能分析 ---- */
                ToolSectionHeader { ident: "analysis"; title: I18n.tr("智能分析（事件/重复/人脸/OCR/语义）") }
                Column {
                    width: parent.width
                    spacing: Theme.spacingSmall
                    visible: root.openSection === "analysis"

                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("自动分析")
                            objectName: "btnAutoAnalyze"
                            tooltip: I18n.tr("一键顺序执行全部自动分析（人脸→OCR→事件→哈希→聚类）")
                            onClicked: LibraryBridge.autoAnalyze()
                        }
                        PMButton {
                            text: I18n.tr("停止")
                            objectName: "btnStopAnalyze"
                            tooltip: I18n.tr("停止当前正在运行的分析任务")
                            onClicked: LibraryBridge.stopAnalysis()
                        }
                        Text {
                            id: autoStateText
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            width: 300
                            elide: Text.ElideRight
                            text: ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    Text {
                        width: parent.width
                        text: I18n.tr("入库后自动依次执行：事件聚类 → 重复检测 → 人脸识别（含自动聚类）→ 文字识别；可中断续跑。")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                        wrapMode: Text.Wrap
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("人脸识别")
                            objectName: "btnRunFaces"
                            tooltip: I18n.tr("对未处理照片运行人脸检测（YuNet），记录人脸位置与特征")
                            onClicked: LibraryBridge.runFaces(0)
                        }
                        PMButton {
                            text: I18n.tr("文字识别")
                            objectName: "btnRunOcr"
                            tooltip: I18n.tr("对未处理照片运行文字识别（RapidOCR），供全文搜索")
                            onClicked: LibraryBridge.runOcr(0)
                        }
                        PMButton {
                            text: I18n.tr("感知哈希")
                            objectName: "btnRunHashes"
                            tooltip: I18n.tr("计算感知哈希（dHash），供重复照片检测")
                            onClicked: LibraryBridge.runHashes(0)
                        }
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("事件聚类")
                            objectName: "btnRunEvents"
                            tooltip: I18n.tr("按拍摄时间与地点聚类生成事件")
                            onClicked: LibraryBridge.runEvents()
                        }
                        PMButton {
                            text: I18n.tr("人脸聚类")
                            objectName: "btnRunFaceCluster"
                            tooltip: I18n.tr("对人脸特征聚类分组，形成人物列表")
                            onClicked: LibraryBridge.runFaceCluster()
                        }
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("生成语义向量")
                            objectName: "btnRunClip"
                            tooltip: I18n.tr("生成语义向量（Chinese-CLIP），支持按自然语言搜图与以图搜图")
                            onClicked: LibraryBridge.runClip()
                        }
                        Text {
                            text: LibraryBridge ? (LibraryBridge.clipAvailable() ? I18n.tr("（CLIP 模型已就位）") : I18n.tr("（缺少 CLIP 模型：models/clip/）")) : ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    CheckBox {
                        id: clipAutoToolsChk
                        objectName: "clipAutoToolsChk"
                        text: I18n.tr("扫描入库后自动生成语义向量")
                        checked: LibraryBridge ? LibraryBridge.clipAutoIndexEnabled() : false
                        onClicked: LibraryBridge.setClipAutoIndexEnabled(checked)
                    }
                    Connections {
                        target: LibraryBridge
                        function onClipAutoIndexChanged(on) { clipAutoToolsChk.checked = on }
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("检测照片堆叠")
                            objectName: "btnRunStacks"
                            tooltip: I18n.tr("检测连拍组并合并为堆叠（按拍摄间隔与感知哈希）")
                            onClicked: LibraryBridge.detectStacks()
                        }
                        Text {
                            text: I18n.tr("（连拍 / RAW+JPG 合并浏览，不删不改原图）")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                }

                /* ---- 标签 ---- */
                ToolSectionHeader { ident: "tagging"; title: I18n.tr("标签（批量打标 / 场景自动打标）") }
                Column {
                    width: parent.width
                    spacing: Theme.spacingSmall
                    visible: root.openSection === "tagging"

                    Row {
                        spacing: Theme.spacingSmall
                        TextField {
                            id: tagMatchField
                            objectName: "tagMatchField"
                            width: 170
                            height: 30
                            placeholderText: I18n.tr("目录/文件名关键词")
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
                        TextField {
                            id: tagValueField
                            objectName: "tagValueField"
                            width: 150
                            height: 30
                            placeholderText: I18n.tr("标签名")
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
                        PMButton {
                            text: I18n.tr("批量打标签")
                            objectName: "btnBulkTag"
                            tooltip: I18n.tr("按已有标签批量核对：列出未打某标签的照片逐个确认")
                            onClicked: {
                                var n = LibraryBridge.bulkTag(tagMatchField.text, tagValueField.text)
                                taskText.text = I18n.tr("已为 ") + n + I18n.tr(" 张照片打标签 '")
                                                + tagValueField.text + "'"
                            }
                        }
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("自动打标签（按场景关键词）")
                            objectName: "btnAutoTag"
                            tooltip: I18n.tr("按场景词表自动为照片打场景标签（CLIP 零样本）")
                            onClicked: {
                                LibraryBridge.autoTagAll()
                                taskText.text = I18n.tr("正在按场景关键词自动打标签（后台运行，请稍候）…")
                            }
                        }
                    }
                }

                /* ---- 场景建议（0.5.27） ---- */
                ToolSectionHeader { ident: "scenesug"; title: I18n.tr("场景建议（发现词表未覆盖的照片簇）") }
                Column {
                    width: parent.width
                    spacing: Theme.spacingSmall
                    visible: root.openSection === "scenesug"

                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("分析未覆盖场景")
                            objectName: "btnSceneSuggest"
                            tooltip: I18n.tr("扫描未覆盖区域，建议可加入词表的新场景词")
                            onClicked: {
                                LibraryBridge.sceneSuggestions()
                                taskText.text = I18n.tr("正在分析未覆盖场景（后台运行，请稍候）…")
                            }
                        }
                        Text {
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            text: I18n.tr("（需要 CLIP 模型与语义向量；只读分析，不改任何数据）")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    Column {
                        id: sceneSugList
                        objectName: "sceneSugList"
                        width: parent.width
                        spacing: 4
                    }
                    Row {
                        spacing: Theme.spacingSmall
                        PMButton {
                            text: I18n.tr("加入词表")
                            objectName: "btnSceneSugApply"
                            tooltip: I18n.tr("把确认的场景建议词并入词表")
                            onClicked: {
                                var picked = []
                                for (var i = 0; i < sceneSugList.children.length; ++i) {
                                    var c = sceneSugList.children[i]
                                    if (c.picked && c.word) picked.push(c.word)
                                }
                                if (picked.length === 0) {
                                    taskText.text = I18n.tr("请先勾选要加入的场景词")
                                    return
                                }
                                var n = LibraryBridge.applySceneSuggestions(picked.join(","))
                                taskText.text = I18n.tr("已加入 ") + n + I18n.tr(" 个场景词；重跑「语义向量」或「自动打标签」后对照片生效")
                                for (var j = sceneSugList.children.length - 1; j >= 0; --j)
                                    if (sceneSugList.children[j].word)
                                        sceneSugList.children[j].destroy()
                            }
                        }
                        Text {
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            text: I18n.tr("（加入后为内置词表追加项，可在设置中查看或用 -词 排除）")
                            font.family: Theme.fontFamily
                            font.pixelSize: 11
                            color: Theme.textDim
                        }
                    }
                    Text {
                        width: parent.width
                        text: I18n.tr("原理：对已有语义向量做聚类，找出与当前词表都不相似的照片簇，")
                              + "从候选池为零样本挑名；建议仅代表\"这批照片还没有合适的场景词\"，"
                              + I18n.tr("采纳与否由你决定。")
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: Theme.textDim
                        wrapMode: Text.Wrap
                    }
                }

                /* ---- 时间校正 ---- */
                ToolSectionHeader { ident: "time"; title: I18n.tr("批量时间校正（相机时钟/时区偏差）") }
                Column {
                    width: parent.width
                    spacing: Theme.spacingSmall
                    visible: root.openSection === "time"

                    Row {
                        spacing: Theme.spacingSmall
                        TextField {
                            id: shiftField
                            objectName: "shiftField"
                            width: 130
                            height: 30
                            placeholderText: I18n.tr("偏移小时（±）")
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
                        PMButton {
                            text: I18n.tr("预览受影响")
                            objectName: "btnShiftPreview"
                            tooltip: I18n.tr("预览时间偏移结果（处理相机时区不准）")
                            onClicked: {
                                var h = parseFloat(shiftField.text)
                                if (isNaN(h)) { taskText.text = I18n.tr("请输入小时数（如 -8 或 +3）"); return }
                                var p = LibraryBridge.timeShiftPreview(h)
                                taskText.text = I18n.tr("将偏移 ") + h + I18n.tr(" 小时，影响 ") + p.affected + I18n.tr(" 张照片（仅预览，未修改）")
                            }
                        }
                        PMButton {
                            text: I18n.tr("执行偏移")
                            objectName: "btnShiftApply"
                            tooltip: I18n.tr("应用时间偏移到所选/全部照片的拍摄时间")
                            onClicked: {
                                var h = parseFloat(shiftField.text)
                                if (isNaN(h)) { taskText.text = I18n.tr("请输入小时数（如 -8 或 +3）"); return }
                                var n = LibraryBridge.timeShift(h)
                                taskText.text = I18n.tr("已偏移 ") + n + I18n.tr(" 张照片的拍摄时间 ") + h + I18n.tr(" 小时")
                            }
                        }
                        Text {
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            text: I18n.tr("（负值=向前，正值=向后；整库范围）")
                            font.family: Theme.fontFamily
                            font.pixelSize: 10
                            color: Theme.textDim
                        }
                    }
                }

            }
        }

        /* 底部固定进度区：不随内容滚动，任何分区展开时都完整可见（修复显示不全） */
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            Layout.topMargin: 6
            Layout.bottomMargin: 8
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSmall
                Text {
                    text: I18n.tr("任务进度")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
                ProgressBar {
                    id: taskBar
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: 0
                }
            }
            Text {
                id: taskText
                objectName: "taskText"
                Layout.fillWidth: true
                Layout.preferredHeight: 28
                text: ""
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                wrapMode: Text.Wrap
                elide: Text.ElideRight
                clip: true
                verticalAlignment: Text.AlignTop
            }
        }
    }

    function refreshAutoState() {
        var arr = LibraryBridge.analysisStatus()
        var parts = []
        for (var i = 0; i < arr.length; ++i)
            parts.push(arr[i].stage + (arr[i].done ? "✓" : "·"))
        autoStateText.text = I18n.tr("分析状态：") + parts.join(" ")
    }

    Connections {
        target: LibraryBridge
        function onMessage(msg) {
            taskText.text = msg
            taskBar.value = 0
            refreshAutoState()
        }
        function onTaskProgress(done, total, labelText) {
            taskBar.value = total > 0 ? done * 100 / total : 0
            /* labelText 可能带"|文件路径"，仅显示阶段名 */
            var sep = labelText.indexOf("|")
            var stage = sep >= 0 ? labelText.substring(0, sep) : labelText
            taskText.text = (stage ? stage + "：" : "") + done + " / " + total
        }
        function onSceneSuggestionsFinished(json) {
            var r = JSON.parse(json)
            for (var i = sceneSugList.children.length - 1; i >= 0; --i)
                if (sceneSugList.children[i].word)
                    sceneSugList.children[i].destroy()
            if (!r.ok) {
                var why = {model_missing: I18n.tr("缺少 CLIP 模型（models/clip/）"),
                           no_embeddings: I18n.tr("照片还没有语义向量，请先运行「语义向量」"),
                           no_tags: I18n.tr("场景词表为空")}[r.reason] || r.reason
                taskText.text = I18n.tr("场景建议不可用：") + why
                return
            }
            if (!r.suggestions || r.suggestions.length === 0) {
                taskText.text = I18n.tr("未发现未覆盖的场景簇：当前词表已覆盖全部照片")
                return
            }
            for (var k = 0; k < r.suggestions.length; ++k) {
                var s = r.suggestions[k]
                SceneSugRow.createObject(sceneSugList, {word: s.word, count: s.count})
            }
            taskText.text = I18n.tr("发现 ") + r.suggestions.length + I18n.tr(" 个候选场景词，请勾选后点「加入词表」")
        }
    }

    onOpened: refreshAutoState()
}
