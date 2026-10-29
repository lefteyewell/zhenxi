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

/* 设置：偏好持久化到 QSettings（registry/ini），跨会话保留。
   0.5.49：改左侧分类导航 + 右侧分页，避免长滚动列表忽略下方设置项。 */
Dialog {
    id: root
    objectName: "settingsDialog"
    title: I18n.tr("设置")
    modal: true
    /* 0.5.57：关闭按钮中文化（standardButtons 的 Close 无法自定义文案） */
    footer: RowLayout {
        Layout.leftMargin: Theme.spacingMedium
        Layout.rightMargin: Theme.spacingMedium
        Layout.topMargin: Theme.spacingSmall
        Layout.bottomMargin: Theme.spacingSmall
        Item { Layout.fillWidth: true }
        PMButton {
            objectName: "settingsCloseBtn"
            text: I18n.tr("关闭")
            height: 30
            onClicked: root.close()
        }
    }
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
    width: 680
    height: 600

    property bool _clipAuto: false
    property bool _autoStart: false
    property bool _trayEnabled: true
    property bool _startMax: true   /* 0.5.67 启动窗口最大化 */
    property real _faceThr: 0.5   /* 0.5.67 人脸聚类相似度阈值 */
    property string _parMode: "auto"   /* 0.6.9 分析并行度 */
    property int _parCustom: 4

    function openSettings() {
        _clipAuto = LibraryBridge ? LibraryBridge.clipAutoIndexEnabled() : false
        _autoStart = LibraryBridge ? LibraryBridge.autoStartEnabled() : false
        _trayEnabled = LibraryBridge ? LibraryBridge.trayEnabled() : true
        _startMax = LibraryBridge ? LibraryBridge.startupMaximizedEnabled() : true
        _faceThr = LibraryBridge ? LibraryBridge.faceClusterThreshold() : 0.5
        _parMode = LibraryBridge ? LibraryBridge.analysisParallelMode() : "auto"
        _parCustom = LibraryBridge ? LibraryBridge.analysisParallelCustom() : 4
        darkChk.checked = (ThemeController ? ThemeController.dark : false)
        sceneTagsArea.text = LibraryBridge ? LibraryBridge.sceneTags() : ""
        copyLibChk.checked = LibraryBridge ? LibraryBridge.copyToLibraryEnabled() : false
        catNav.currentIndex = 0
        refreshRoots()
        root.open()
    }

    /* ---- 照片库根目录列表（0.5.49：多根 + 空间不足自动换根） ---- */
    /* 比较用归一化：bridge 存的原始文本可能是反斜杠/大小写差异，
       而列表模型路径是 abspath+正斜杠，直接比会永远不匹配（删除失效）。 */
    function _normPath(s) {
        return String(s).trim().replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase()
    }
    function refreshRoots() {
        rootsModel.clear()
        if (!LibraryBridge) return
        var infos = LibraryBridge.libraryRootsInfo()
        for (var i = 0; i < infos.length; ++i)
            rootsModel.append(infos[i])
    }
    function addRoot(path) {
        if (!path || !LibraryBridge) return
        var target = root._normPath(path)
        var lines = LibraryBridge.libraryRoots().split("\n")
        var out = []
        for (var i = 0; i < lines.length; ++i) {
            var l = lines[i].trim()
            if (l.length > 0 && root._normPath(l) !== target) out.push(l)
        }
        out.push(path)
        LibraryBridge.setLibraryRoots(out.join("\n"))
        refreshRoots()
    }
    function removeRoot(path) {
        if (!path || !LibraryBridge) return
        var target = root._normPath(path)
        var lines = LibraryBridge.libraryRoots().split("\n")
        var out = []
        for (var i = 0; i < lines.length; ++i) {
            var l = lines[i].trim()
            if (l.length > 0 && root._normPath(l) !== target) out.push(l)
        }
        LibraryBridge.setLibraryRoots(out.join("\n"))
        refreshRoots()
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingMedium
        spacing: Theme.spacingMedium

        /* 左：分类导航 */
        ListView {
            id: catNav
            objectName: "settingsCatNav"
            Layout.preferredWidth: 128
            Layout.fillHeight: true
            clip: true
            currentIndex: 0
            model: [I18n.tr("智能分析"), I18n.tr("照片库根目录"), I18n.tr("启动与常驻"), I18n.tr("界面"), I18n.tr("场景词表")]
            delegate: Rectangle {
                width: catNav.width
                height: 36
                radius: Theme.radiusMedium
                color: catNav.currentIndex === index ? Theme.primary : "transparent"
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: Theme.spacingMedium
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: catNav.currentIndex === index ? "white" : Theme.text
                    }
                MouseArea {
                    anchors.fill: parent
                    onClicked: catNav.currentIndex = index
                }
            }
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
        }

        /* 右：分页内容 */
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: catNav.currentIndex

            /* ========== 0 智能分析 ========== */
            ColumnLayout {
                spacing: Theme.spacingMedium
                Text {
                    text: I18n.tr("智能分析")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                CheckBox {
                    id: clipChk
                    objectName: "clipAutoChk"
                    text: I18n.tr("扫描入库后自动生成语义向量（CLIP）")
                    checked: root._clipAuto
                    onClicked: if (LibraryBridge) LibraryBridge.setClipAutoIndexEnabled(checked)
                }
                Connections {
                    target: LibraryBridge
                    function onClipAutoIndexChanged(on) { root._clipAuto = on }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("开启后，每次扫描入库会自动为还没有向量的照片生成 CLIP 向量；")
                          + I18n.tr("开启本开关也会立即为已有照片补跑（首次较慢，每张约几秒）。")
                          + I18n.tr("之后即可用「clip:文字」做中文语义搜索、场景标签与场景建议。")
                          + I18n.tr("需 Chinese-CLIP 模型就位（models/clip/）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }

                /* 0.5.67：人脸聚类相似度阈值（用户可调） */
                Text {
                    text: I18n.tr("人脸聚类")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                Row {
                    spacing: Theme.spacingMedium
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("相似度阈值")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                    }
                    Slider {
                        id: faceThrSlider
                        anchors.verticalCenter: parent.verticalCenter
                        from: 0.40
                        to: 0.70
                        stepSize: 0.01
                        value: root._faceThr
                        onMoved: {
                            root._faceThr = value
                            if (LibraryBridge) LibraryBridge.setFaceClusterThreshold(value)
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root._faceThr.toFixed(2)
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: Theme.primary
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("越大越严格：调高会把相像的人物拆开（宁分勿合，需手动合并），"
                                  + "调低合并更激进（误并风险增大）。"
                                  + "改动后需重新执行「人脸聚类」才生效（工具中心 → 人脸聚类）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Text {
                    text: I18n.tr("分析并行度")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                Row {
                    spacing: Theme.spacingMedium
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: I18n.tr("并行模式")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                    }
                    ComboBox {
                        id: parModeBox
                        anchors.verticalCenter: parent.verticalCenter
                        width: 220
                        model: [I18n.tr("自动（默认，留 2 核给界面）"),
                                I18n.tr("全速（占满核，界面可能卡）"),
                                I18n.tr("自定义进程数")]
                        currentIndex: root._parMode === "auto" ? 0
                                     : root._parMode === "full" ? 1 : 2
                        font.family: Theme.fontFamily
                        onActivated: {
                            var m = ["auto", "full", "custom"][currentIndex]
                            root._parMode = m
                            if (LibraryBridge) LibraryBridge.setAnalysisParallelMode(m)
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root._parMode === "custom"
                        text: I18n.tr("进程数")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.text
                    }
                    SpinBox {
                        id: parCustomBox
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root._parMode === "custom"
                        from: 1
                        to: 16
                        value: root._parCustom
                        font.family: Theme.fontFamily
                        onValueModified: {
                            root._parCustom = value
                            if (LibraryBridge) LibraryBridge.setAnalysisParallelCustom(value)
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("进程越多分析越快，但 CPU 与内存占用越高。"
                                  + "「自动」为界面响应与分析速度的平衡（弱机推荐）；"
                                  + "「全速」会占满 CPU 核，分析期间界面可能明显卡顿；"
                                  + "改动对下一次分析任务生效。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Item { Layout.fillHeight: true }
            }

            /* ========== 1 照片库根目录 ========== */
            ColumnLayout {
                spacing: Theme.spacingSmall
                Text {
                    text: I18n.tr("照片库根目录（可多个；导入时复制入库的目标）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Row {
                    spacing: Theme.spacingSmall
                    PMButton {
                        objectName: "libRootAddBtn"
                        text: I18n.tr("添加文件夹…")
                        onClicked: rootPicker.openDialog("")
                    }
                    PMButton {
                        objectName: "libRootRemoveBtn"
                        text: I18n.tr("删除所选")
                        enabled: rootsList.currentIndex >= 0
                        onClicked: root.removeRoot(rootsModel.get(rootsList.currentIndex).path)
                    }
                }
                /* 0.6.13：手动输入路径——系统文件夹对话框不可用/不合意时的备选 */
                Row {
                    spacing: Theme.spacingSmall
                    TextField {
                        id: rootManualInput
                        objectName: "libraryRootInput"
                        width: 300
                        placeholderText: I18n.tr("或直接输入文件夹路径")
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        onAccepted: rootAddManualBtn.clicked()
                    }
                    PMButton {
                        id: rootAddManualBtn
                        objectName: "libraryRootAddManualBtn"
                        text: I18n.tr("添加")
                        height: 30
                        onClicked: {
                            var p = rootManualInput.text.trim()
                            if (!p) return
                            if (LibraryBridge.addLibraryRoot(p)) {
                                rootManualInput.text = ""
                                root.refreshRoots()
                            }
                        }
                    }
                }
                ListView {
                    id: rootsList
                    objectName: "libraryRootsList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: ListModel { id: rootsModel }
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                    delegate: Rectangle {
                        width: rootsList.width
                        height: 34
                        radius: Theme.radiusMedium
                        color: rootsList.currentIndex === index
                               ? Qt.rgba(0, 0, 0, 0.08) : "transparent"
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.spacingSmall
                            anchors.rightMargin: Theme.spacingSmall
                            spacing: Theme.spacingSmall
                            Text {
                                text: model.primary ? "★ " + model.path : "  " + model.path
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: model.exists ? Theme.text : Theme.danger
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                            Text {
                                text: model.exists
                                      ? (I18n.tr("剩 ") + model.freeGB + "G / " + model.totalGB + "G")
                                      : I18n.tr("目录不存在")
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: model.exists ? Theme.textDim : Theme.danger
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: rootsList.currentIndex = index
                        }
                    }
                }
                CheckBox {
                    id: copyLibChk
                    objectName: "copyLibChk"
                    text: I18n.tr("导入时把照片库以外的照片复制入库")
                    checked: false
                    onCheckedChanged: {
                        if (root.visible && LibraryBridge)
                            LibraryBridge.setCopyToLibraryEnabled(checked)
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("开启后，导入/检查时不在任何照片库根目录下的照片会按「源文件夹名/子路径」")
                          + I18n.tr("整体复制入库（只复制照片文件，其余一律不复制），源照片保持原样不动。")
                          + I18n.tr("★ 为默认根；某个根磁盘空间不足时，自动改用其他有空间的根")
                          + I18n.tr("（按文件大小预留 256MB 余量挑选）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
            }

            /* ========== 2 启动与常驻 ========== */
            ColumnLayout {
                spacing: Theme.spacingMedium
                Text {
                    text: I18n.tr("启动与常驻")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                CheckBox {
                    id: autoStartChk
                    objectName: "autoStartChk"
                    text: I18n.tr("开机自动启动")
                    checked: root._autoStart
                    onClicked: if (LibraryBridge) LibraryBridge.setAutoStartEnabled(checked)
                }
                Connections {
                    target: LibraryBridge
                    function onAutoStartChanged(on) { root._autoStart = on }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("开机时自动运行本程序（绿色便携、无需安装、无需管理员权限）：")
                          + I18n.tr("Windows 写入当前用户注册表 Run 项，麒麟写入 ~/.config/autostart。")
                          + I18n.tr("启用后若移动程序文件夹，请取消勾选再重新勾选。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                CheckBox {
                    id: trayChk
                    objectName: "trayChk"
                    text: I18n.tr("关闭窗口时最小化到托盘继续运行")
                    checked: root._trayEnabled
                    onClicked: if (LibraryBridge) LibraryBridge.setTrayEnabled(checked)
                }
                CheckBox {
                    id: startMaxChk
                    objectName: "startMaxChk"
                    text: I18n.tr("启动时窗口最大化")
                    checked: root._startMax
                    onClicked: if (LibraryBridge) LibraryBridge.setStartupMaximizedEnabled(checked)
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("0.5.67 新增，默认开启：程序启动即最大化窗口（下次启动生效）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Connections {
                    target: LibraryBridge
                    function onTrayEnabledChanged(on) { root._trayEnabled = on }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("默认开启。开启后点窗口关闭按钮会隐藏到系统托盘（双击托盘图标恢复，")
                          + I18n.tr("右键可退出）；定时任务依赖程序运行，建议配合「开机自动启动」使用。")
                          + I18n.tr("系统不支持托盘时该选项自动失效，窗口照常关闭。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("定时任务已移至菜单栏「定时任务」（模式/时间/执行项），运行期间生效。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Item { Layout.fillHeight: true }
            }

            /* ========== 3 界面 ========== */
            ColumnLayout {
                spacing: Theme.spacingMedium
                Text {
                    text: I18n.tr("界面")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                CheckBox {
                    id: darkChk
                    objectName: "darkChk"
                    text: I18n.tr("深色模式")
                    onCheckedChanged: {
                        if (root.visible && ThemeController) ThemeController.dark = checked
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("缩略图大小可在菜单「视图」中切换（小/中/大/超大）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Item { Layout.fillHeight: true }
            }

            /* ========== 4 场景词表 ========== */
            ColumnLayout {
                spacing: Theme.spacingSmall
                Text {
                    text: I18n.tr("场景识别词表")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: Theme.textDim
                }
                TextArea {
                    id: sceneTagsArea
                    objectName: "sceneTagsField"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 200
                    placeholderText: I18n.tr("追加到内置词表；逗号或换行分隔，如：星空, 航拍。 -宠物 表示排除内置词「宠物」")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.text
                    wrapMode: TextArea.Wrap
                    onTextChanged: {
                        if (root.visible && LibraryBridge) LibraryBridge.setSceneTags(text)
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: I18n.tr("词表 = 内置 29 词 + 你追加的词（-词 可排除内置词）。导入照片后的自动分析")
                          + I18n.tr("与工具中心「自动打标签」都用这份词表；自动场景标签写在「场景/」层级下")
                          + I18n.tr("（如 场景/海边）。改动后需重跑一次打标才作用于已有照片（需要 CLIP 模型与语义向量）。")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    wrapMode: Text.Wrap
                }
                Item { Layout.fillHeight: true }
            }
        }
    }

    /* 添加照片库根目录用的文件夹选择器（Popup 需声明在窗口级，此处随设置框） */
    FolderPickerDialog {
        id: rootPicker
        onPathChosen: (path) => root.addRoot(path)
    }
}
