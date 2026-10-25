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
import QtQuick.Window
import theme 1.0
import components 1.0
import pages 1.0
import i18n 1.0

ApplicationWindow {
    id: window

    /* 0.6.2 多语言：可用语言清单（code → 显示名），由 _i18nRefreshLangs()
       从 LibraryBridge.i18nLanguages() 刷新（内置包 + 数据目录 i18n/ 用户包） */
    property var _langNames: ({ "zh": "中文" })

    /* 刷新可用语言并登记进 I18n；返回 [{code,name}] */
    function _i18nRefreshLangs() {
        var langs = []
        try { langs = JSON.parse(LibraryBridge.i18nLanguages()) } catch (e) { }
        var names = { "zh": "中文" }
        var codes = ["zh"]
        for (var i = 0; i < langs.length; ++i) {
            var it = langs[i]
            if (!it.code || names[it.code]) continue
            names[it.code] = it.name || it.code
            codes.push(it.code)
        }
        _langNames = names
        I18n.availableLanguages = codes
        return langs
    }

    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 700
    visible: true
    /* 0.5.67：启动窗口最大化在文件末尾既有的 Component.onCompleted 内处理
       （ApplicationWindow 只能有一个 onCompleted，重复声明会整页加载失败） */
    title: I18n.tr("真昔 · 照片管理系统")

    /* 主题与控制器联动 */
    Binding { target: Theme; property: "dark"; value: ThemeController ? ThemeController.dark : Theme.dark }
    Binding { target: Theme; property: "schemeIndex"; value: ThemeController ? ThemeController.schemeIndex : Theme.schemeIndex }

    color: Theme.bg

    /* 0.5.66：把窗口调色板绑到 Theme——Fusion 样式的 CheckBox/ComboBox 等控件
       标签取自 palette，默认黑色，深色模式下不可见（用户反馈：首启引导黑字）。
       绑定后全部样式控件随深浅色自动切换。 */
    palette.window: Theme.bg
    palette.windowText: Theme.text
    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.base: Theme.surface
    palette.button: Theme.surfaceAlt
    palette.placeholderText: Theme.textDim

    background: Rectangle {
        color: Theme.bg
    }

    /* ===== 菜单栏：功能按钮全部归类到下拉菜单，窗口缩小也可用 ===== */
    menuBar: MenuBar {
        id: mainMenuBar
        objectName: "mainMenuBar"

        Menu {
            id: fileMenu
            objectName: "fileMenu"
            title: I18n.tr("文件(&F)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnScan"
                text: I18n.tr("添加照片文件夹…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把一个文件夹（含子文件夹）里的照片与视频导入库")
                onTriggered: {
                    statusText.text = I18n.tr("正在打开文件夹选择…")
                    scanPicker.openDialog()
                }
            }
            MenuItem {
                objectName: "btnPaths"
                text: I18n.tr("管理路径…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("查看、增加或移除库的扫描根目录")
                onTriggered: pathsDialog.open()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnExport"
                text: I18n.tr("导出所选…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把选中的照片/视频导出为指定格式与分辨率")
                onTriggered: exportDialog.open()
            }
            MenuItem {
                objectName: "btnMoveOut"
                text: I18n.tr("移出管理…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("记录从库中移出的照片（移出记录，不删除原文件）")
                onTriggered: moveOutPicker.openDialog()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnExportCsv"
                text: I18n.tr("导出元数据 CSV…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把库内照片清单（含标签/评分等）导出为 CSV 表格")
                onTriggered: csvPicker.openDialog()
            }
            MenuItem {
                objectName: "btnSyncOut"
                text: I18n.tr("导出元数据到 XMP…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把标签、评级等元数据写入照片的 XMP 边车文件（不改原图像素）")
                onTriggered: syncOutPicker.openDialog()
            }
            MenuItem {
                objectName: "btnSyncIn"
                text: I18n.tr("导入元数据…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("从 XMP 边车文件把标签、评级等元数据读回库")
                onTriggered: syncInPicker.openDialog()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnSettings"
                text: I18n.tr("设置…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("打开设置（主题、智能分析、启动行为等）")
                onTriggered: settingsDialog.openSettings()
            }
            MenuSeparator {}
            MenuItem {
                text: I18n.tr("退出")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("彻底退出程序（后台任务完成后再退出更安全）")
                onTriggered: window.close()
            }
        }

        Menu {
            id: searchMenu
            objectName: "searchMenu"
            title: I18n.tr("搜索(&S)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnAdvancedSearch"
                text: I18n.tr("高级搜索…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("按关键词、日期、相机、人物、评分等多条件组合搜索")
                onTriggered: advancedSearch.open()
            }
            MenuSeparator {}
            MenuItem {
                text: I18n.tr("今天拍摄的照片")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("筛出今天拍摄的照片")
                onTriggered: {
                    var d = new Date()
                    var y = d.getFullYear()
                    var m = ("0" + (d.getMonth() + 1)).slice(-2)
                    var dd = ("0" + d.getDate()).slice(-2)
                    mainContent.loadSearch("dates:" + y + "-" + m + "-" + dd + ".." + y + "-" + m + "-" + dd)
                }
            }
            MenuItem {
                text: I18n.tr("X 年前的今天")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("回看往年同一天拍摄的照片（年份可选）")
                onTriggered: { navState.current = 15; mainContent.showOnThisDay() }
            }
            MenuItem {
                text: I18n.tr("本周拍摄的照片")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("筛出本周（周一起）拍摄的照片")
                onTriggered: {
                    var now = new Date()
                    var start = new Date(now)
                    start.setDate(now.getDate() - now.getDay())
                    var fmt = function (dt) {
                        return dt.getFullYear() + "-" + ("0" + (dt.getMonth() + 1)).slice(-2) + "-" + ("0" + dt.getDate()).slice(-2)
                    }
                    mainContent.loadSearch("dates:" + fmt(start) + ".." + fmt(now))
                }
            }
            MenuItem {
                text: I18n.tr("带文字的照片（OCR）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("离线 OCR 已识别出文字的照片")
                onTriggered: mainContent.loadSearch("text:")
            }
            MenuItem {
                text: I18n.tr("带人脸的照片")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("检出过人脸的照片")
                onTriggered: mainContent.loadSearch("faces:1")
            }
            MenuItem {
                objectName: "btnFaceSearchUpload"
                text: I18n.tr("上传人脸搜图…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("用一张人脸照片在库内找相似人物")
                onTriggered: faceSearchPicker.openDialog()
            }
            MenuSeparator {}
            MenuItem {
                text: I18n.tr("精选照片")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("按图像质量评分挑出的高质量照片")
                onTriggered: { navState.current = 0; gallery.loadFlag("pick") }
            }
            MenuItem {
                text: I18n.tr("已评级（≥1★）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("你给过 1 星及以上评级的照片")
                onTriggered: { navState.current = 0; gallery.loadRated(1) }
            }
            MenuItem {
                text: I18n.tr("高评分（≥4★）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("4 星及以上的高分照片")
                onTriggered: { navState.current = 0; gallery.loadRated(4) }
            }
        }

        Menu {
            id: viewMenu
            objectName: "viewMenu"
            title: I18n.tr("视图(&V)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnThumbSmall"
                text: I18n.tr("缩略图 · 小")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("每格更小，一屏显示更多")
                onTriggered: if (ThemeController) ThemeController.thumbSize = 110
            }
            MenuItem {
                objectName: "btnThumbMedium"
                text: I18n.tr("缩略图 · 中")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("默认缩略图大小")
                onTriggered: if (ThemeController) ThemeController.thumbSize = 160
            }
            MenuItem {
                objectName: "btnThumbLarge"
                text: I18n.tr("缩略图 · 大")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("更大缩略图，看得更清楚")
                onTriggered: if (ThemeController) ThemeController.thumbSize = 220
            }
            MenuItem {
                objectName: "btnThumbXL"
                text: I18n.tr("缩略图 · 超大")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("最大缩略图，适合逐张浏览")
                onTriggered: if (ThemeController) ThemeController.thumbSize = 300
            }
        }

        /* 0.5.48：定时任务独立菜单（运行期间生效）。
           0.5.51：加「执行方式」——程序内计时（需程序在跑）/ 系统任务计划
           （Windows 任务计划 / 麒麟 systemd --user，关机不错过，跑完即退）。 */
        Menu {
            id: scheduleMenu
            objectName: "scheduleMenu"
            title: I18n.tr("定时任务(&S)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item

            property bool modeOff: true
            property bool modeOnce: false
            property bool modeDaily: false
            property bool chkCheck: false
            property bool chkAnalyze: false
            property string statusLine: I18n.tr("状态：已关闭")
            property bool engineInternal: true
            property bool osRegistered: false

            function statusText() {
                if (!LibraryBridge) return I18n.tr("状态：已关闭")
                var eng = scheduleMenu.engineInternal
                    ? I18n.tr("程序内计时")
                    : (scheduleMenu.osRegistered ? I18n.tr("系统任务计划（已注册）")
                                                 : I18n.tr("系统任务计划（未注册）"))
                var m = LibraryBridge.scheduleMode()
                if (m === "off") return I18n.tr("状态：已关闭 · ") + eng
                var when = m === "daily"
                    ? (I18n.tr("每日 ") + (LibraryBridge.scheduleTime() || "09:00"))
                    : (I18n.tr("一次性 ") + (LibraryBridge.scheduleOnceAt() || I18n.tr("未设置时间")))
                var what = []
                if (LibraryBridge.scheduleCheckEnabled()) what.push(I18n.tr("检查文件夹"))
                if (LibraryBridge.scheduleAnalyzeEnabled()) what.push(I18n.tr("智能分析"))
                if (what.length === 0) what.push(I18n.tr("未勾选任务"))
                return I18n.tr("状态：") + when + " · " + what.join(" + ") + " · " + eng
            }

            /* 每次打开菜单刷新勾选态/状态行（Menu 项可能被缓存，不能只依赖一次性绑定） */
            function refresh() {
                if (!LibraryBridge) return
                var m = LibraryBridge.scheduleMode()
                scheduleMenu.modeOff = (m === "off")
                scheduleMenu.modeOnce = (m === "once")
                scheduleMenu.modeDaily = (m === "daily")
                scheduleMenu.chkCheck = LibraryBridge.scheduleCheckEnabled()
                scheduleMenu.chkAnalyze = LibraryBridge.scheduleAnalyzeEnabled()
                scheduleMenu.engineInternal = (LibraryBridge.scheduleEngine() !== "os")
                scheduleMenu.osRegistered = LibraryBridge.scheduleOsRegistered()
                scheduleMenu.statusLine = scheduleMenu.statusText()
            }
            onAboutToShow: scheduleMenu.refresh()

            Text {
                text: I18n.tr("执行方式")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                leftPadding: 12
                topPadding: 4
            }
            MenuItem {
                objectName: "schedEngineInternal"
                text: I18n.tr("程序内计时（需程序在跑）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("由真昔自己计时触发；程序退出时定时任务暂停")
                checkable: true
                checked: scheduleMenu.engineInternal
                onTriggered: statusText.text = LibraryBridge.setScheduleEngine("internal")
            }
            MenuItem {
                objectName: "schedEngineOs"
                text: I18n.tr("系统任务计划（关机不错过）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("交给操作系统计划任务触发，关机错过的时间点开机后补执行")
                checkable: true
                checked: !scheduleMenu.engineInternal
                onTriggered: statusText.text = LibraryBridge.setScheduleEngine("os")
            }
            MenuSeparator {}
            MenuItem {
                objectName: "schedModeOff"
                text: I18n.tr("已关闭")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("关闭定时任务")
                checkable: true
                checked: scheduleMenu.modeOff
                onTriggered: { LibraryBridge.setScheduleMode("off"); scheduleMenu.refresh() }
            }
            MenuItem {
                objectName: "schedModeOnce"
                text: I18n.tr("仅一次…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("设置某个时刻只执行一次")
                checkable: true
                checked: scheduleMenu.modeOnce
                onTriggered: { LibraryBridge.setScheduleMode("once"); scheduleMenu.refresh() }
            }
            MenuItem {
                objectName: "schedModeDaily"
                text: I18n.tr("每日执行")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("每天定点自动执行所选任务")
                checkable: true
                checked: scheduleMenu.modeDaily
                onTriggered: { LibraryBridge.setScheduleMode("daily"); scheduleMenu.refresh() }
            }
            MenuSeparator {}
            MenuItem {
                objectName: "schedTimeItem"
                text: I18n.tr("每日执行时间…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("设置每日执行的具体时刻")
                enabled: scheduleMenu.modeDaily
                onTriggered: schedTimeDialog.openFor("daily")
            }
            MenuItem {
                objectName: "schedOnceItem"
                text: I18n.tr("一次性时间…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("设置一次性任务的具体时刻")
                enabled: scheduleMenu.modeOnce
                onTriggered: schedTimeDialog.openFor("once")
            }
            MenuSeparator {}
            MenuItem {
                objectName: "schedCheckItem"
                text: I18n.tr("定时执行：检查照片文件夹")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("定时自动发现新增/有变更的照片文件并入库")
                checkable: true
                checked: scheduleMenu.chkCheck
                onTriggered: { LibraryBridge.setScheduleCheckEnabled(checked); scheduleMenu.refresh() }
            }
            MenuItem {
                objectName: "schedAnalyzeItem"
                text: I18n.tr("定时执行：智能分析（事件/重复/人脸/文字）")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("定时自动做事件聚类、查重、人脸识别与文字识别")
                checkable: true
                checked: scheduleMenu.chkAnalyze
                onTriggered: { LibraryBridge.setScheduleAnalyzeEnabled(checked); scheduleMenu.refresh() }
            }
            MenuSeparator {}
            MenuItem {
                objectName: "schedStatusItem"
                text: scheduleMenu.statusLine
                enabled: false
            }
        }

        Menu {
            id: toolsMenu
            objectName: "toolsMenu"
            title: I18n.tr("工具(&T)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnTools"
                text: I18n.tr("工具中心…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("打开工具中心（查重、人脸聚类、深度解码检查等全部工具）")
                onTriggered: toolsDialog.open()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnQuickAnalyze"
                text: I18n.tr("自动分析…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("手动触发一轮事件/重复/人脸/文字的完整分析")
                onTriggered: {
                    statusText.text = I18n.tr("自动分析已启动（状态栏显示进度）")
                    LibraryBridge.autoAnalyze()
                }
            }
            MenuItem {
                objectName: "btnFaceClean"
                text: I18n.tr("低质量人脸清理…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("批量隐藏或删除误检、模糊的低质量人脸标注")
                onTriggered: faceCleanDialog.open()
            }
        }

        Menu {
            id: libraryMenu
            objectName: "libraryMenu"
            title: I18n.tr("库与备份(&L)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnBackup"
                text: I18n.tr("立即备份")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把数据库与配置备份到默认备份目录")
                onTriggered: statusText.text = I18n.tr("备份中… ") + LibraryBridge.backupNow()
            }
            MenuItem {
                objectName: "btnBackupTo"
                text: I18n.tr("备份到…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("把库备份到你指定的位置")
                onTriggered: backupPicker.openDialog()
            }
            MenuItem {
                objectName: "btnRestore"
                text: I18n.tr("从备份恢复…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("用备份文件把库恢复到备份时点")
                onTriggered: restorePicker.openDialog()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnLockReadOnly"
                text: I18n.tr("锁定只读…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("临时把库设为只读（防误改，可随时解锁）")
                onTriggered: readOnlyDialog.open()
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnReindex"
                text: I18n.tr("重建索引")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("重建全文检索与缩略图索引（不改动任何照片）")
                onTriggered: LibraryBridge.reindexCheck()
            }
            MenuItem {
                objectName: "btnIntegrity"
                text: I18n.tr("完整性校验")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("比对库记录与磁盘文件，发现缺失、被改动、缩略图丢失等")
                onTriggered: LibraryBridge.integrityCheck()
            }
            MenuItem {
                objectName: "btnFolderCheck"
                text: I18n.tr("检查照片文件夹")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("扫描已登记的文件夹，发现新增或变更的照片")
                onTriggered: LibraryBridge.folderCheck(false)
            }
            MenuItem {
                objectName: "btnDbDetail"
                text: I18n.tr("详细统计")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("查看照片数量、存储占用等详细统计")
                onTriggered: {
                    var d = LibraryBridge.dbDetail()
                    var s = I18n.tr("照片 ") + d.photos + I18n.tr("（索引 ") + d.indexed + I18n.tr(" · 失败 ")
                            + d.failed + I18n.tr(" · 缺失 ") + d.missing + I18n.tr("）· 人脸 ") + d.faces
                            + I18n.tr(" · 人物 ") + d.persons + I18n.tr(" · 事件 ") + d.events + I18n.tr(" · 标签 ")
                            + d.tags + I18n.tr(" · 根目录 ") + d.roots.length
                    toastLayer.show(s, "info")
                }
            }
            MenuSeparator {}
            MenuItem {
                objectName: "btnInitDatabase"
                text: I18n.tr("初始化数据库…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("新建一个空库（当前库与照片不受影响）")
                onTriggered: initDbConfirm.open()
            }
        }

        Menu {
            id: helpMenu
            objectName: "helpMenu"
            title: I18n.tr("帮助(&H)")
            /* 0.5.63：菜单弹窗改场景内 Item（默认 Popup.Window 顶层窗口，
               Windows 上切换菜单时窗口显隐+重挂载会偶发白闪） */
            popupType: Popup.Item
            MenuItem {
                objectName: "btnHelp"
                text: I18n.tr("使用说明…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("查看完整使用说明")
                onTriggered: helpDialog.open()
            }
            MenuItem {
                objectName: "btnFirstRunGuide"
                text: I18n.tr("首次使用引导…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("重新打开首次使用引导")
                onTriggered: firstRunDialog.open()
            }
            MenuItem {
                objectName: "btnAbout"
                text: I18n.tr("关于…")
                hoverEnabled: true
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: I18n.tr("版本、许可与开源信息")
                onTriggered: aboutDialog.open()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        /* ===== 顶部栏 ===== */
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.headerHeight
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMedium
                anchors.rightMargin: Theme.spacingMedium
                spacing: Theme.spacingMedium

                Rectangle {
                    width: 38
                    height: 38
                    radius: Theme.radiusMedium
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.primary }
                        GradientStop { position: 1.0; color: Theme.accent }
                    }
                    Text {
                        anchors.centerIn: parent
                        text: I18n.tr("照")
                        font.family: Theme.fontFamily
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        color: "white"
                    }
                }

                Column {
                    spacing: 1
                    Text {
                        text: "真昔"
                        font.family: Theme.fontFamily
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: Theme.text
                    }
                    Text {
                        text: I18n.tr("离线照片管理")
                        font.family: Theme.fontFamily
                        font.pixelSize: 10
                        color: Theme.textDim
                    }
                }

                /* ACDsee 风格常驻工具按钮：高频操作不再翻菜单 */
                Row {
                    spacing: 4
                    Layout.alignment: Qt.AlignVCenter
                    PMButton {
                        objectName: "tbImport"
                        tooltip: I18n.tr("选择照片文件夹加入管理（就地登记索引，不复制不移动文件）")
                        text: I18n.tr("＋ 导入")
                        width: 78
                        height: 30
                        onClicked: {
                            statusText.text = I18n.tr("正在打开文件夹选择…")
                            scanPicker.openDialog()
                        }
                    }
                    PMButton {
                        objectName: "tbExport"
                        tooltip: I18n.tr("导出所选照片，可选格式与分辨率")
                        text: I18n.tr("↗ 导出")
                        width: 78
                        height: 30
                        enabled: gallery.selectedIds.length > 0
                        onClicked: exportDialog.open()
                    }
                    PMButton {
                        objectName: "tbTag"
                        tooltip: I18n.tr("给所选照片批量添加标签")
                        text: I18n.tr("🏷 标签")
                        width: 78
                        height: 30
                        enabled: gallery.selectedIds.length > 0
                        onClicked: {
                            batchTagDialog.label =
                                I18n.tr("为所选 ") + gallery.selectedIds.length + I18n.tr(" 张照片添加标签：")
                            batchTagDialog.open()
                        }
                    }
                    PMButton {
                        objectName: "tbTools"
                        tooltip: I18n.tr("打开工具中心（分析、标签、备份、维护）")
                        text: I18n.tr("⚙ 工具")
                        width: 78
                        height: 30
                        onClicked: toolsDialog.open()
                    }
                }

                Item { Layout.fillWidth: true }

                /* 搜索框 + 联想 */
                Rectangle {
                    Layout.preferredWidth: 300
                    Layout.maximumWidth: 340
                    Layout.minimumWidth: 180
                    height: 34
                    radius: 17
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.divider

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 6

                        TextField {
                            id: searchField
                            objectName: "searchField"
                            Layout.fillWidth: true
                            placeholderText: I18n.tr("搜索照片（文件名 / 相机 / 文字）")
                            color: Theme.text
                            placeholderTextColor: Theme.textDim
                            background: Rectangle { color: "transparent" }
                            font.pixelSize: 12
                            font.family: Theme.fontFamily
                            onTextEdited: {
                                suggestTimer.restart()
                            }
                            onAccepted: {
                                if (text.length > 0) {
                                    suggestTimer.stop()
                                    mainContent.loadSearch(text)
                                    suggestPopup.close()
                                }
                            }
                        }
                        Timer {
                            id: suggestTimer
                            interval: 250
                            repeat: false
                            onTriggered: {
                                if (searchField.text.length >= 1) {
                                    suggestList.model = LibraryBridge.suggest(searchField.text)
                                    if (suggestList.count > 0)
                                        suggestPopup.open()
                                    else
                                        suggestPopup.close()
                                } else {
                                    suggestList.model = []
                                    suggestPopup.close()
                                }
                            }
                        }
                        Text {
                            id: searchGoBtn
                            objectName: "searchGoBtn"
                            text: "⏎"
                            font.pixelSize: 14
                            color: searchField.text.length > 0 ? Theme.primary : Theme.textDim
                            /* 0.5.28：回车图标可点击（此前是纯 Text，点击无反应） */
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: searchField.accepted()
                            }
                        }
                    }

                    Popup {
                        id: suggestPopup
                        parent: searchField
                        x: 0
                        y: searchField.height + 4
                        width: searchField.width
                        height: Math.min(180, suggestList.count * 28)
                        padding: 0
                        background: Rectangle {
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.divider
                        }
                        ListView {
                            id: suggestList
                            anchors.fill: parent
                            model: []
                            clip: true
                            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                            delegate: ItemDelegate {
                                width: suggestList.width
                                height: 28
                                text: modelData
                                font.pixelSize: 12
                                font.family: Theme.fontFamily
                                onClicked: {
                                    searchField.text = modelData
                                    mainContent.loadSearch(modelData)
                                    suggestPopup.close()
                                }
                            }
                        }
                    }
                }

                Text {
                    text: I18n.tr("配色")
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textDim
                }

                ComboBox {
                    id: schemeBox
                    model: ThemeController ? ThemeController.schemeNames : []
                    currentIndex: ThemeController ? ThemeController.schemeIndex : 0
                    onActivated: ThemeController.setScheme(currentIndex)
                    width: 96   /* 最长项"影棚深灰"4 字 + 指示箭头可完整显示（用户反馈原 110 太宽） */
                    height: 32
                }

                PMButton {
                    text: Theme.dark ? I18n.tr("浅色") : I18n.tr("深色")
                    onClicked: ThemeController.toggleDark()
                }

                /* 0.5.66：界面语言切换（多语言架构——语言包为数据文件，
                   新增语言只需在 i18n/ 放 <code>.json 并登记 availableLanguages）
                   0.5.67：显示"中/EN"，当前语言加粗（用户反馈）。
                   0.6.3 回退：语言菜单方案（Instantiator）在真机上体验不佳
                   （点击不灵/切换残留英文），按用户要求恢复一键切换按钮。
                   availableLanguages 仍含用户自装语言（启动时刷新），循环切换可用。 */
                Button {
                    id: tbLang
                    objectName: "tbLang"
                    width: 64
                    height: 32
                    ToolTip.visible: hovered
                    ToolTip.delay: 550
                    ToolTip.text: I18n.tr("切换界面语言 / Switch language")
                    onClicked: {
                        var langs = I18n.availableLanguages
                        var i = langs.indexOf(I18n.lang)
                        var next = langs[(i + 1) % langs.length]
                        I18n.setLang(next, LibraryBridge.i18nCatalog(next))
                        LibraryBridge.setUiLang(next)
                    }
                    contentItem: Row {
                        spacing: 2
                        anchors.centerIn: parent
                        Text {
                            text: "中"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: I18n.lang !== "en"
                            color: I18n.lang !== "en" ? Theme.text : Theme.textDim
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "/"
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.textDim
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "EN"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            font.bold: I18n.lang === "en"
                            color: I18n.lang === "en" ? Theme.text : Theme.textDim
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: tbLang.enabled ? (tbLang.hovered ? Theme.hover : Theme.surface) : Theme.surfaceAlt
                        border.width: 1
                        border.color: Theme.divider
                    }
                }
            }
        }

        /* 侧栏手风琴分组头（0.5.25）：点击展开该组并收起其它组 */
    component NavGroupHeader: Rectangle {
        id: groupHeader
        property string title: ""
        property string ident: ""
        objectName: "navGroup" + ident
        Layout.fillWidth: true
        Layout.leftMargin: 8
        Layout.rightMargin: 8
        height: 28
        radius: 6
        color: groupArea.containsMouse || navState.navGroup === ident ? Theme.hover : "transparent"
        Text {
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: (navState.navGroup === groupHeader.ident ? "▾ " : "▸ ") + groupHeader.title
            font.family: Theme.fontFamily
            font.pixelSize: 12
            font.weight: Font.DemiBold
            color: Theme.text
        }
        MouseArea {
            id: groupArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: navState.navGroup = (navState.navGroup === groupHeader.ident ? "" : groupHeader.ident)
        }
    }

    /* ===== 主体三栏 ===== */
        RowLayout {
            id: mainRow
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            /* 左：导航 */
            Rectangle {
                objectName: "navPanel"
                Layout.preferredWidth: ThemeController ? ThemeController.navWidth : Theme.navWidth
                Layout.minimumWidth: 140
                Layout.fillHeight: true
                color: Theme.surface
                border.width: 1
                border.color: Theme.divider

                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: Theme.spacingSmall
                    anchors.bottomMargin: Theme.spacingMedium
                    spacing: 0

                    /* 导航内容整体可滚动：矮窗口（含高 DPI 缩放）下"按文件夹"树也能展开
                       （旧实现树面板靠 fillHeight 抢剩余空间，默认 900px 窗口仅分到 20px，
                       700px 以下为 0，表现为点击I18n.tr("按文件夹")无任何可见效果——0.5.22 修复） */
                    ScrollView {
                        id: navScroll
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ColumnLayout {
                            id: navCol
                            width: navScroll.availableWidth
                            spacing: Theme.spacingTiny

                    NavGroupHeader { title: I18n.tr("图库"); ident: "gallery" }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingTiny
                        visible: navState.navGroup === "gallery"

                    NavItem {
                        objectName: "navAll"
                        label: I18n.tr("全部照片")
                        active: navState.current === 0
                        onClicked: {
                            // 只显示全部照片；不切换文件夹树（避免误触展开/收起）
                            navState.current = 0
                            mainContent.showAll()
                        }
                    }

                    /* "按文件夹"折叠按钮：独立控制目录树展开/收起 */
                    Rectangle {
                        id: treeToggleBtn
                        objectName: "treeToggleBtn"
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        Layout.topMargin: 2
                        height: 26
                        radius: 6
                        color: treeToggleBtnArea.hovered ? Theme.hover : "transparent"
                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: I18n.tr("按文件夹 ") + (folderTreeArea.expanded ? "▴" : "▾")
                            font.family: Theme.fontFamily
                            font.pixelSize: 12
                            color: Theme.text
                        }
                        MouseArea {
                            id: treeToggleBtnArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                folderTreeArea.expanded = !folderTreeArea.expanded
                                if (folderTreeArea.expanded)
                                    folderTreeArea.refresh()
                            }
                        }
                    }

                    /* 文件夹树面板（"全部照片"下拉展开，占满剩余高度，超高滚动） */
                    Item {
                        id: folderTreeArea
                        objectName: "folderTreeArea"
                        Layout.fillWidth: true
                        /* 展开时固定可见高度（树内部自带滚动条），不再依赖剩余空间抢高度 */
                        Layout.preferredHeight: folderTreeArea.expanded ? 340 : 0
                        visible: folderTreeArea.expanded
                        clip: true
                        property bool expanded: false
                        function refresh() { folderTree.refresh() }

                        FolderTree {
                            id: folderTree
                            objectName: "folderTree"
                            anchors.fill: parent
                            anchors.topMargin: 2
                            onFolderChosen: (path, count) => {
                                navState.current = 0
                                gallery.loadDir(path)
                                statusText.text = I18n.tr("文件夹：") + path + "（" + count + I18n.tr(" 张）")
                            }
                            /* "添加到图库"：与文件菜单"添加照片文件夹"完全一致 */
                            /* 实际导入由 Python 侧 attachQmlSignals 直连（同上） */
                            onIngestRequested: (path) => {
                                statusText.text = I18n.tr("正在扫描 ") + path + " …"
                            }
                            onIngestMany: (paths) => {
                                statusText.text = I18n.tr("正在扫描 ") + paths.length + I18n.tr(" 个文件夹 …")
                            }
                        }
                    }
                    }

                    NavGroupHeader { title: I18n.tr("整理"); ident: "organize" }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingTiny
                        visible: navState.navGroup === "organize"

                    NavItem {
                        objectName: "navEvents"
                        label: I18n.tr("事件"); active: navState.current === 1
                        onClicked: { navState.current = 1; mainContent.showEvents() }
                    }
                    NavItem {
                        objectName: "navDuplicates"
                        label: I18n.tr("重复"); active: navState.current === 7
                        onClicked: { navState.current = 7; mainContent.showDuplicates() }
                    }
                    }

                    NavGroupHeader { title: I18n.tr("分类浏览"); ident: "category" }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingTiny
                        visible: navState.navGroup === "category"

                    NavItem {
                        objectName: "navPeople"
                        label: I18n.tr("人物"); active: navState.current === 3
                        onClicked: { navState.current = 3; mainContent.showCategory("people") }
                    }
                    NavItem {
                        objectName: "navLocations"
                        label: I18n.tr("地点"); active: navState.current === 4
                        onClicked: { navState.current = 4; mainContent.showCategory("locations") }
                    }
                    NavItem {
                        objectName: "navDevices"
                        label: I18n.tr("设备"); active: navState.current === 5
                        onClicked: { navState.current = 5; mainContent.showCategory("devices") }
                    }
                    NavItem {
                        objectName: "navTags"
                        label: I18n.tr("标签"); active: navState.current === 6
                        onClicked: { navState.current = 6; mainContent.showCategory("tags") }
                    }
                    }

                    NavGroupHeader { title: I18n.tr("时间与统计"); ident: "time" }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.spacingTiny
                        visible: navState.navGroup === "time"

                    /* 0.5.39：导出历史（此前为预留占位，点击无反应） */
                    NavItem {
                        objectName: "navExport"
                        label: I18n.tr("已导出")
                        active: navState.current === 18
                        onClicked: mainContent.showExportHistory()
                    }
                    NavItem {
                        objectName: "navTimeline"
                        label: I18n.tr("时间线"); active: navState.current === 11
                        onClicked: { navState.current = 11; mainContent.showTimeline() }
                    }
                    NavItem {
                        objectName: "navMemory"
                        label: I18n.tr("回忆"); active: navState.current === 15
                        onClicked: { navState.current = 15; mainContent.showOnThisDay() }
                    }
                    NavItem {
                        objectName: "navArchive"
                        label: I18n.tr("作废"); active: navState.current === 16
                        onClicked: { navState.current = 16; mainContent.showArchive() }
                    }
                    NavItem {
                        objectName: "navAlbums"
                        label: I18n.tr("相册"); active: navState.current === 17
                        onClicked: { navState.current = 17; mainContent.showAlbums() }
                    }
                    NavItem {
                        objectName: "navStats"
                        label: I18n.tr("统计"); active: navState.current === 12
                        onClicked: { navState.current = 12; mainContent.showStats() }
                    }
                    NavItem {
                        objectName: "navMap"
                        label: I18n.tr("地图"); active: navState.current === 14
                        onClicked: { navState.current = 14; mainContent.showMap() }
                    }
                    NavItem {
                        objectName: "navTrash"
                        label: I18n.tr("回收站"); active: navState.current === 13
                        onClicked: { navState.current = 13; mainContent.showTrash() }
                    }
                    }
                        }
                    }
                }
            }

            /* 左|中 分隔条：拖动调整左栏（导航/目录树）宽度 */
            Rectangle {
                Layout.fillHeight: true
                width: 5
                color: lSplit.hovered || lSplit.pressed ? Theme.primary : "transparent"
                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 2
                    anchors.rightMargin: 2
                    color: lSplit.hovered || lSplit.pressed ? Theme.primary : Theme.divider
                }
                MouseArea {
                    id: lSplit
                    objectName: "leftSplitter"
                    anchors.fill: parent
                    anchors.margins: -2
                    hoverEnabled: true
                    cursorShape: Qt.SplitHCursor
                    onPositionChanged: (mouse) => {
                        if (mouse.buttons & Qt.LeftButton)
                            ThemeController.navWidth =
                                lSplit.mapToItem(mainRow, mouse.x, 0).x
                    }
                }
            }

            /* 中：图库 / 事件 */
            Item {
                id: mainContent
                objectName: "mainContent"
                Layout.fillWidth: true
                Layout.fillHeight: true

                GalleryPage {
                    id: gallery
                    objectName: "gallery"
                    anchors.fill: parent
                    visible: navState.current === 0 || navState.current === 2
                             || navState.current === 8 || navState.current === 9
                             || navState.current === 10
                    onPhotoClicked: (photoId) => {
                        if (photoId < 0) { infoPanel.showDetail({}); return }
                        infoPanel.showDetail(LibraryBridge.photoDetail(photoId))
                    }
                    onPhotoContextRequested: (ids, index) => {
                        photoViewer.setContext(ids, index)
                    }
                    onContextMenuRequested: (gx, gy) => {
                        var pt = window.contentItem.mapFromGlobal(gx, gy)
                        galleryMenu.popup(window.contentItem, pt.x, pt.y)
                    }
                    onPersonFacesRequested: (personId) => {
                        personFacesDialog.openFor(personId)
                    }
                    onBatchTagRequested: {
                        batchTagDialog.label = I18n.tr("为所选 ") + gallery.selectedIds.length + I18n.tr(" 张照片添加标签：")
                        batchTagDialog.open()
                    }
                    onBatchExportRequested: exportDialog.open()
                    onBatchMoveOutRequested: moveOutPicker.openDialog()
                    onBatchCopyRequested: (paths) => {
                        LibraryBridge.setClipboard(paths)
                        toastLayer.show(I18n.tr("已复制 ") + gallery.selectedIds.length + I18n.tr(" 条路径到剪贴板"), "success")
                    }
                    onMoveOutOfPersonRequested: {
                        personMoveDialog.targetPhotos = gallery.selectedIds
                        personMoveDialog.currentPersonId = parseInt(gallery._filterValue)
                        personMoveDialog.open()
                    }
                    onBackRequested: mainContent.navBack()
                }

                EventsPage {
                    id: eventsPage
                    objectName: "eventsPage"
                    anchors.fill: parent
                    visible: navState.current === 1
                    onEventClicked: (eventId) => {
                        gallery.loadEvent(eventId)
                        navState.current = 2
                    }
                }

                DuplicatesPage {
                    id: duplicatesPage
                    objectName: "duplicatesPage"
                    anchors.fill: parent
                    visible: navState.current === 7
                    onPhotoClicked: (photoId, ids) => {
                        if (photoId < 0) { infoPanel.showDetail({}); return }
                        infoPanel.showDetail(LibraryBridge.photoDetail(photoId))
                        /* 0.5.28：以组内照片为上下文直接打开大图（此前点击无反应） */
                        if (ids && ids.length > 0) {
                            photoViewer.setContext(ids, Math.max(0, ids.indexOf(photoId)))
                            photoViewer.showCurrent()
                        }
                    }
                }

                CategoryPage {
                    id: peoplePage
                    objectName: "peoplePage"
                    anchors.fill: parent
                    visible: navState.current === 3
                    kind: "people"
                    title: I18n.tr("人物")
                    hint: I18n.tr("按人脸聚类结果查看某位人物出现的照片")
                    onItemClicked: (item) => {
                        gallery.loadPerson(item.id)
                        navState.current = 8
                    }
                    onRenameRequested: (pid, name) => {
                        renameDialog.title = I18n.tr("重命名人物")
                        renameDialog.context = "person"
                        renameDialog.personId = pid
                        renameDialog.initialValue = name
                        renameDialog.open()
                    }
                    onMergeRequested: (pid, name) => {
                        mergePickerDialog.title = I18n.tr("合并人物")
                        mergePickerDialog.mode = "person"
                        mergePickerDialog.sourceId = pid
                        mergePickerDialog.hint = "「" + name + I18n.tr("」的照片将并入所选人物，源人物将被移除。")
                        mergePickerDialog.open()
                    }
                    onBatchMergeRequested: (ids) => {
                        var n = LibraryBridge.mergePeople(ids)
                        toastLayer.show(I18n.tr("已合并 ") + n + I18n.tr(" 个人物"), n > 0 ? "success" : "error")
                        peoplePage.refresh()
                        peoplePage.selectedIds = []
                        peoplePage.updateBatchBar()
                    }
                }

                CategoryPage {
                    id: locationsPage
                    objectName: "locationsPage"
                    anchors.fill: parent
                    visible: navState.current === 4
                    kind: "locations"
                    title: I18n.tr("地点")
                    hint: I18n.tr("按 GPS 坐标聚合地点")
                    onItemClicked: (item) => {
                        gallery.loadLocation(item.lat, item.lon)
                        navState.current = 9
                    }
                }

                CategoryPage {
                    id: devicesPage
                    objectName: "devicesPage"
                    anchors.fill: parent
                    visible: navState.current === 5
                    kind: "devices"
                    title: I18n.tr("设备")
                    hint: I18n.tr("按相机型号查看照片")
                    onItemClicked: (item) => {
                        gallery.loadDevice(item.cameraModel)
                        navState.current = 10
                    }
                }

                TagTreePage {
                    id: tagsPage
                    objectName: "tagsPage"
                    anchors.fill: parent
                    visible: navState.current === 6
                    onItemClicked: (item) => {
                        gallery.loadTag(item.path)
                        navState.current = 8
                    }
                    onRenameRequested: (path) => {
                        renameDialog.title = I18n.tr("重命名标签")
                        renameDialog.context = "tag"
                        renameDialog.personId = 0
                        renameDialog.initialValue = path
                        renameDialog.open()
                    }
                    onMergeRequested: (path) => {
                        mergePickerDialog.title = I18n.tr("合并标签")
                        mergePickerDialog.mode = "tag"
                        mergePickerDialog.sourceTag = path
                        mergePickerDialog.hint = "「" + path + I18n.tr("」将合并进所选标签，合并后该标签及其子孙消失。")
                        mergePickerDialog.open()
                    }
                    // 移动层级：paths 末位为指令——__pick__(弹窗选父) / __top__(移到顶层) / 具体父路径
                    onMoveRequested: (paths) => {
                        if (!paths || paths.length < 2) return
                        var mark = paths[paths.length - 1]
                        var srcs = paths.slice(0, -1)
                        if (mark === "__pick__") {
                            tagPicker.pendingPaths = srcs
                            tagPicker.pickOnly = true
                            tagPicker.openPicker()
                            return
                        }
                        var dst = (mark === "__top__") ? "" : mark
                        var n = LibraryBridge.moveTagsBatch(srcs, dst)
                        tagsPage.refresh()
                        toastLayer.show(n > 0 ? (I18n.tr("已移动 ") + n + I18n.tr(" 条标签记录"))
                                             : I18n.tr("没有可移动的标签（可能目标非法）"),
                                       n > 0 ? "success" : "warning")
                    }
                }

                TimelinePage {
                    id: timelinePage
                    objectName: "timelinePage"
                    anchors.fill: parent
                    visible: navState.current === 11
                    onMonthClicked: (ym) => {
                        gallery.loadDateMonth(ym)
                        navState.current = 0
                    }
                    onDayClicked: (day) => {
                        gallery.loadDateDay(day)
                        navState.current = 0
                    }
                }

                StatsPage {
                    id: statsPage
                    objectName: "statsPage"
                    anchors.fill: parent
                    visible: navState.current === 12
                }

                MapPage {
                    id: mapPage
                    objectName: "mapPage"
                    anchors.fill: parent
                    visible: navState.current === 14
                    onLocationClicked: (lat, lon) => {
                        gallery.loadLocation(lat, lon)
                        navState.current = 9
                    }
                }

                TrashPage {
                    id: trashPage
                    objectName: "trashPage"
                    anchors.fill: parent
                    visible: navState.current === 13
                    onRestoreRequested: (folder) => {
                        var n = LibraryBridge.reimportMovedOut(folder)
                        if (n > 0) {
                            toastLayer.show(I18n.tr("已重新导入 ") + n + I18n.tr(" 张照片"), "success")
                            trashPage.refresh()
                        } else {
                            toastLayer.show(I18n.tr("没有找到可重新导入的照片"), "warning")
                        }
                    }
                    onRestoreAllRequested: {
                        var dirs = LibraryBridge.restoreAllMovedOut()
                        if (dirs.length > 0) {
                            toastLayer.show(I18n.tr("已恢复 ") + dirs.length + I18n.tr(" 个目录的照片"), "success")
                            trashPage.refresh()
                        } else {
                            toastLayer.show(I18n.tr("没有可恢复的记录"), "warning")
                        }
                    }
                    /* 回收站内操作（移入待删除 / 恢复 / 彻底删除）的反馈提示。
                       此前该信号未接线，导致操作成功后界面毫无提示。 */
                    onMessageRequested: (msg) => {
                        toastLayer.show(msg, (msg.indexOf(I18n.tr("未选择")) >= 0 || msg.indexOf(I18n.tr("没有")) >= 0)
                                        ? "warning" : "success")
                    }
                }

                OnThisDayPage {
                    id: memoryPage
                    objectName: "memoryPage"
                    anchors.fill: parent
                    visible: navState.current === 15
                    onPhotoClicked: (photoId) => {
                        if (photoId < 0) { infoPanel.showDetail({}); return }
                        infoPanel.showDetail(LibraryBridge.photoDetail(photoId))
                    }
                }

                ArchivePage {
                    id: archivePage
                    objectName: "archivePage"
                    anchors.fill: parent
                    visible: navState.current === 16
                    onPhotoClicked: (photoId) => {
                        if (photoId < 0) { infoPanel.showDetail({}); return }
                        infoPanel.showDetail(LibraryBridge.photoDetail(photoId))
                    }
                }

                /* 0.5.39：导出历史（左栏「已导出」） */
                ExportHistoryPage {
                    id: exportHistoryPage
                    objectName: "exportHistoryPage"
                    anchors.fill: parent
                    visible: navState.current === 18
                }

                AlbumsPage {
                    id: albumsPage
                    objectName: "albumsPage"
                    anchors.fill: parent
                    visible: navState.current === 17
                    onAlbumClicked: (albumId, name) => {
                        gallery.loadAlbum(albumId, name)
                        navState.current = 2
                    }
                    onCreateRequested: {
                        renameDialog.title = I18n.tr("新建相册")
                        renameDialog.context = "album_new"
                        renameDialog.personId = 0
                        renameDialog.initialValue = ""
                        renameDialog.open()
                    }
                    onRenameRequested: (albumId, name) => {
                        renameDialog.title = I18n.tr("重命名相册")
                        renameDialog.context = "album_rename"
                        renameDialog.personId = albumId
                        renameDialog.initialValue = name
                        renameDialog.open()
                    }
                    onDeleteRequested: (albumId, name) => {
                        albumDeleteConfirm.albumId = albumId
                        albumDeleteConfirm.albumName = name
                        albumDeleteConfirm.open()
                    }
                }

                function showAll() { navState.current = 0; gallery.loadAll(); eventsPage.refresh() }
                function showEvents() { navState.current = 1; eventsPage.refresh() }
                function showDuplicates() { navState.current = 7; duplicatesPage.refresh() }
                function showCategory(kind) {
                    if (kind === "people") peoplePage.refresh()
                    else if (kind === "locations") locationsPage.refresh()
                    else if (kind === "devices") devicesPage.refresh()
                    else if (kind === "tags") tagsPage.refresh()
                }
                function showTimeline() { navState.current = 11; timelinePage.refresh() }
                function showOnThisDay() { navState.current = 15; memoryPage.refresh() }
                function showArchive() { navState.current = 16; archivePage.refresh() }
                function showExportHistory() { navState.current = 18; exportHistoryPage.refresh() }
                function showAlbums() { navState.current = 17; albumsPage.refresh() }
                function showSimilar() { navState.current = 0; gallery.loadSimilar() }
                function showFaceSearch() { navState.current = 0; gallery.loadFaceSearch() }
                function showStats() { navState.current = 12; statsPage.refresh() }
                function showMap() { navState.current = 14; mapPage.refresh() }
                function showTrash() { navState.current = 13; trashPage.refresh() }
                function loadSearch(q) { navState.current = 0; gallery.search(q) }

                /* 返回键：按图库当前 backTarget 回到来源页（无来源则回全部） */
                function navBack() {
                    var t = gallery.backTarget
                    if (t === 1) showEvents()
                    else if (t === 3) { navState.current = 3; showCategory("people") }
                    else if (t === 4) { navState.current = 4; showCategory("locations") }
                    else if (t === 5) { navState.current = 5; showCategory("devices") }
                    else if (t === 6) { navState.current = 6; showCategory("tags") }
                    else if (t === 11) showTimeline()
                    else if (t === 17) showAlbums()
                    else showAll()
                }
            }

            /* 中|右 分隔条：拖动调整右栏（信息面板）宽度 */
            Rectangle {
                Layout.fillHeight: true
                width: 5
                color: rSplit.hovered || rSplit.pressed ? Theme.primary : "transparent"
                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 2
                    anchors.rightMargin: 2
                    color: rSplit.hovered || rSplit.pressed ? Theme.primary : Theme.divider
                }
                MouseArea {
                    id: rSplit
                    objectName: "rightSplitter"
                    anchors.fill: parent
                    anchors.margins: -2
                    hoverEnabled: true
                    cursorShape: Qt.SplitHCursor
                    onPositionChanged: (mouse) => {
                        if (mouse.buttons & Qt.LeftButton)
                            ThemeController.infoWidth =
                                mainRow.width - rSplit.mapToItem(mainRow, mouse.x, 0).x
                    }
                }
            }

            /* 右：信息面板 */
            InfoPanel {
                id: infoPanel
                objectName: "infoPanel"
                Layout.preferredWidth: ThemeController ? ThemeController.infoWidth : Theme.infoWidth
                Layout.minimumWidth: 220
                Layout.fillHeight: true
                Layout.topMargin: Theme.spacingSmall
                Layout.bottomMargin: Theme.spacingSmall
                Layout.rightMargin: Theme.spacingSmall
                onOpenPhoto: (url, title, photoId) => photoViewer.showPhoto(url, title, photoId)
                onToastRequested: (text, kind) => toastLayer.show(text, kind)
                onTagPickerRequested: tagPicker.openPicker()
                onAssignFaceRequested: (faceId) => {
                    personMoveDialog.faceMode = true
                    personMoveDialog.faceId = faceId
                    personMoveDialog.currentPersonId = 0
                    personMoveDialog.open()
                }
                /* 0.5.31：右栏快速跳转（同日/同文件夹/同相机/同标签） */
                onJumpRequested: (kind, value) => {
                    if (!value || value.length === 0)
                        return
                    if (kind === "date")
                        gallery.loadDateDay(value)
                    else if (kind === "folder")
                        gallery.loadFolder(value)
                    else if (kind === "camera")
                        gallery.loadDevice(value)
                    else if (kind === "tag")
                        gallery.loadTag(value)
                    navState.current = 0
                }
            }
        }

        /* ===== 状态栏 ===== */
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            color: Theme.surfaceAlt
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingMedium
                anchors.rightMargin: Theme.spacingMedium
                Text {
                    id: statusText
                    objectName: "statusText"
                    text: LibraryBridge ? LibraryBridge.statsText() : ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                    elide: Text.ElideRight
                    Layout.maximumWidth: 420
                }
                Text {
                    id: selCountText
                    objectName: "selCountText"
                    text: gallery.selectedIds.length > 0
                          ? (I18n.tr("已选 ") + gallery.selectedIds.length + I18n.tr(" 张")) : ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.primary
                }
                /* 0.6.3：状态栏居中提示——后台任务运行期间部分功能受限
                   （任务互斥会让手动操作被拒，用户不明就里以为功能坏了） */
                Item { Layout.fillWidth: true }
                Text {
                    id: busyHint
                    objectName: "busyHint"
                    visible: false
                    text: I18n.tr("有后台任务运行期间，部分功能可能受限")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.italic: true
                    color: Theme.primary
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: I18n.tr("缩略图")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
                Slider {
                    id: thumbSlider
                    objectName: "thumbSizeSlider"
                    from: 110
                    to: 340
                    stepSize: 10
                    Layout.preferredWidth: 110
                    value: ThemeController ? ThemeController.thumbSize : 160
                    onMoved: if (ThemeController) ThemeController.thumbSize = value
                }
                Item { width: 8 }
                Text {
                    id: taskLabel
                    visible: taskBar.visible
                    text: ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim

                    /* 0.5.67：点状态栏任务文字/进度条重新打开进度弹窗
                       （此前"隐藏"后无入口可再调出，用户反馈） */
                    MouseArea {
                        anchors.fill: parent
                        visible: taskBar.visible
                        cursorShape: Qt.PointingHandCursor
                        onClicked: analysisProgress.reopen()
                    }
                }
                ProgressBar {
                    id: taskBar
                    visible: false
                    width: 130
                    from: 0
                    to: 100
                    value: 0

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: analysisProgress.reopen()
                    }
                }
            }
        }
    }

    QtObject {
        id: navState
        property int current: 0
        /* 侧栏手风琴：当前展开的分组（同一时间只显示一个下拉详单，0.5.25） */
        property string navGroup: "gallery"
        /* 图库页状态集合：离开这些页面时必须清空选择，
           否则导出/移出所选会操作不可见的照片 */
        property var galleryStates: [0, 2, 8, 9, 10]
        onCurrentChanged: {
            if (galleryStates.indexOf(current) < 0) {
                gallery.clearSelection()
                infoPanel.showDetail({})
            }
        }
    }

    Connections {
        target: LibraryBridge
        function onMessage(msg) {
            statusText.text = msg
            taskBar.visible = false
        }
        function onToast(text, kind) {
            toastLayer.show(text, kind)
        }
        /* 0.6.3：后台任务忙/闲切换状态栏居中提示（busyChanged 在任务起止时发射） */
        function onBusyChanged() {
            busyHint.visible = LibraryBridge.busyCount() > 0
        }
        function onTaskProgress(done, total, labelText) {
            taskBar.visible = total > 0
            if (total > 0) {
                taskBar.value = done * 100 / total
                /* labelText 可能带"|文件路径"，状态栏只显示阶段名 */
                var sep = labelText.indexOf("|")
                var stage = sep >= 0 ? labelText.substring(0, sep) : labelText
                taskLabel.text = (stage ? stage + " " : "") + done + " / " + total
            }
        }
        function onPhotosChanged() {
            mainContent.showAll()
            gallery.clearSelection()
        }
        function onStacksDetected(count) {
            /* 0.5.32：堆叠检测出栈后图库自动切到堆叠视图（不强制跳转页面，
               用户当前在工具中心仍停留在原地，回到图库即是合并视图） */
            gallery.loadStacks()
            toastLayer.show(I18n.tr("已合并 ") + count + I18n.tr(" 组连拍，图库已切换到堆叠视图，可随时切回"), "success")
        }
        function onSimilarFinished(js) {
            try {
                var r = JSON.parse(js)
                if (r.count > 0) {
                    if (r.kind === "face") mainContent.showFaceSearch()
                    else mainContent.showSimilar()
                }
            } catch (e) { }
        }
    }

    /* 帮助中心（Popup 需声明在窗口级） */
    HelpDialog {
        id: helpDialog
    }

    /* 关于（Popup 需声明在窗口级） */
    AboutDialog {
        id: aboutDialog
    }

    /* 设置（Dialog 需声明在窗口级） */
    SettingsDialog {
        id: settingsDialog
    }

    /* 层级标签选择器（窗口级）：信息面板「从标签树选择…」拉起 */
    TagPickerDialog {
        id: tagPicker
        onTagPicked: (path) => {
            // 模式一：标签树「归入…」选目标父节点 → 批量移动层级
            if (tagPicker.pickOnly) {
                var n = LibraryBridge.moveTagsBatch(tagPicker.pendingPaths, path)
                tagPicker.pickOnly = false
                tagPicker.pendingPaths = []
                tagsPage.refresh()
                toastLayer.show(n > 0 ? (I18n.tr("已移动 ") + n + I18n.tr(" 条标签记录")) : I18n.tr("没有可移动的标签"),
                               n > 0 ? "success" : "warning")
                return
            }
            // 模式二：给当前照片打标签
            if (infoPanel.currentId < 0) return
            if (LibraryBridge.addTag(infoPanel.currentId, path)) {
                infoPanel.refreshTags(LibraryBridge.photoTags(infoPanel.currentId))
                toastLayer.show(I18n.tr("已添加标签「") + path + "」", "success")
            } else {
                toastLayer.show(I18n.tr("添加标签失败"), "error")
            }
        }
    }

    /* 库完整性校验报告（校验完成后由 LibraryBridge.integrityFinished 拉起） */
    IntegrityDialog {
        id: integrityDialog
        onCheckRequested: (folder) => LibraryBridge.integrityCheck(folder)
        onRepairRequested: (kind) => {
            var n = LibraryBridge.integrityRepair(kind)
            if (n > 0) {
                toastLayer.show(I18n.tr("已置 ") + n + I18n.tr(" 张为待分析，正在后台重新分析"), "success")
                integrityDialog.refreshIssues()
            } else {
                toastLayer.show(I18n.tr("没有需要重新分析的照片"), "warning")
            }
        }
        Connections {
            target: LibraryBridge
            function onIntegrityFinished(js) { integrityDialog.showReport(js) }
        }
    }

    /* 工具中心（Popup 需声明在窗口级） */
    ToolsDialog {
        id: toolsDialog
        onRestoreRequested: restorePicker.openDialog()
        onBackupRequested: backupPicker.openDialog()
        onSyncOutRequested: syncOutPicker.openDialog()
        onCsvRequested: csvPicker.openDialog()
    }

    /* 0.5.48：定时任务时间输入（Popup 需声明在窗口级） */
    ScheduleTimeDialog {
        id: schedTimeDialog
    }

    /* 管理路径（Popup 需声明在窗口级） */
    PathsDialog {
        id: pathsDialog
    }

    /* 分析/任务进度弹窗（醒目显示后台任务，避免只在左下角一闪而过） */
    AnalysisProgressDialog {
        id: analysisProgress
    }

    /* 高级搜索面板（Popup 需声明在窗口级，避免被布局接管） */
    AdvancedSearchPanel {
        id: advancedSearch
        onSearchRequested: (query) => {
            mainContent.loadSearch(query)
        }
    }

    /* 文件/文件夹选择器（自绘 Popup，不依赖系统对话框，弹出行为稳定） */
    FolderPickerDialog {
        id: scanPicker
        objectName: "scanPicker"
        dialogTitle: I18n.tr("选择照片所在文件夹")
        showRecursiveOption: true
        /* 实际导入由 Python 侧 attachQmlSignals 把 pathChosen/pathsChosen
           直连到 LibraryBridge.ingest/ingestMany（QML→Python 方法调用会被
           PySide 静默丢弃，见 library_bridge.attachQmlSignals 注释） */
        onPathChosen: (folder) => {
            statusText.text = I18n.tr("正在扫描 ") + folder + " …"
        }
        onPathsChosen: (paths) => {
            statusText.text = I18n.tr("正在扫描 ") + paths.length + I18n.tr(" 个文件夹 …")
        }
    }

    FolderPickerDialog {
        id: moveOutPicker
        objectName: "moveOutPicker"
        dialogTitle: I18n.tr("选择移出目标文件夹（照片将移到此处并从索引清除）")
        multiSelect: false
        property string pendingFolder: ""
        onPathChosen: (folder) => {
            pendingFolder = folder
            if (gallery.selectedIds.length > 0)
                moveOutConfirm.open()
            else
                statusText.text = I18n.tr("移出未开始：请先选择照片")
        }
    }

    Dialog {
        id: moveOutConfirm
        modal: true
        title: I18n.tr("确认移出")
        standardButtons: Dialog.Yes | Dialog.No
        width: 420
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        contentItem: Label {
            text: I18n.tr("将所选照片移动到新文件夹并从索引中移出，\n文件不会删除。确定继续吗？")
            font.family: Theme.fontFamily
            wrapMode: Text.Wrap
        }
        onAccepted: {
            var n = gallery.moveOutSelected(moveOutPicker.pendingFolder)
            if (n > 0)
                statusText.text = I18n.tr("正在移出 ") + n + I18n.tr(" 张 → ") + moveOutPicker.pendingFolder
            else
                statusText.text = I18n.tr("移出未开始：请先选择照片")
        }
    }

    Dialog {
        id: initDbConfirm
        objectName: "initDbConfirm"
        modal: true
        title: I18n.tr("初始化数据库")
        standardButtons: Dialog.Yes | Dialog.No
        width: 470
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        contentItem: Label {
            text: I18n.tr("将先<b>按当前时间备份</b>数据库，然后清空全部索引记录：\n")
                + I18n.tr("照片、人脸、OCR 文字、事件、人物、标签、语义向量、扫描路径。\n\n")
                + I18n.tr("<b>不会删除你的原始照片文件</b>，缩略图缓存也保留。\n")
                + I18n.tr("清空后重新扫描文件夹即可再次入库。确定继续吗？")
            font.family: Theme.fontFamily
            wrapMode: Text.Wrap
            textFormat: Text.RichText
        }
        onAccepted: {
            var res = JSON.parse(LibraryBridge.initDatabase())
            if (res.ok)
                statusText.text = I18n.tr("数据库已初始化（清空 ") + res.photos + I18n.tr(" 条记录），备份：") + res.backup
            else
                statusText.text = I18n.tr("初始化失败：") + res.error
        }
    }

    FolderPickerDialog {
        id: exportPicker
        objectName: "exportPicker"
        dialogTitle: I18n.tr("选择导出目录")
        multiSelect: false
        onPathChosen: (folder) => {
            var n = gallery.exportSelected(folder)
            if (n > 0)
                statusText.text = I18n.tr("正在导出 ") + n + I18n.tr(" 张 → ") + folder
            else
                statusText.text = I18n.tr("导出未开始：请先选择照片")
        }
    }

    /* 0.5.38：导出目录选择（供导出设置弹窗调用） */
    FolderPickerDialog {
        id: exportDirPicker
        objectName: "exportDirPicker"
        dialogTitle: I18n.tr("选择导出目录")
        multiSelect: false
        onPathChosen: (folder) => {
            exportDialog.destDir = folder
            exportDialog.open()
        }
    }

    /* 0.5.38：导出设置——格式（原始/JPG/PNG/WebP/TIFF）+ 分辨率
       （原始/短边1080/800/640，只缩小不放大） */
    Dialog {
        id: exportDialog
        objectName: "exportDialog"
        modal: true
        width: 520
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        padding: 16

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusLarge
            border.width: 1
            border.color: Theme.divider
        }

        property string destDir: ""
        readonly property var fmtKeys: ["original", "jpg", "png", "webp", "tiff"]
        readonly property var resKeys: ["original", "s1080", "s800", "s640"]

        function _apply() {
            var fmt = fmtKeys[formatBox.currentIndex]
            var res = resKeys[resBox.currentIndex]
            var n = gallery.exportSelectedEx(destDir, fmt, res)
            if (n > 0)
                statusText.text = I18n.tr("正在导出 ") + n + I18n.tr(" 张 → ") + destDir
            close()
        }

        onOpened: {
            ro_note.text = destDir.length > 0
                    ? I18n.tr("目标目录：") + destDir : I18n.tr("尚未选择目录，请先点「选择目录…」")
        }

        contentItem: ColumnLayout {
            spacing: 10

            Text {
                text: I18n.tr("导出照片")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
            }

            Row {
                spacing: Theme.spacingSmall
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.tr("目标目录")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
                PMButton {
                    objectName: "exportBrowseBtn"
                    text: I18n.tr("选择目录…")
                    height: 30
                    tooltip: I18n.tr("选择导出照片保存到哪个文件夹")
                    onClicked: exportDirPicker.openDialog()
                }
            }

            Text {
                id: ro_note
                Layout.fillWidth: true
                text: ""
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                elide: Text.ElideMiddle
            }

            Row {
                spacing: Theme.spacingSmall
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.tr("格式")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
                ComboBox {
                    id: formatBox
                    objectName: "exportFormatBox"
                    width: 160
                    model: [I18n.tr("保持原始格式"), "JPG", "PNG", "WebP", "TIFF"]
                    font.family: Theme.fontFamily
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.tr("分辨率")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textDim
                }
                ComboBox {
                    id: resBox
                    objectName: "exportResBox"
                    width: 160
                    model: [I18n.tr("原始分辨率"), I18n.tr("短边 1080"), I18n.tr("短边 800"), I18n.tr("短边 640")]
                    font.family: Theme.fontFamily
                }
            }

            Text {
                Layout.fillWidth: true
                text: I18n.tr("分辨率按短边缩放，只缩小不放大（不会超过原始分辨率）；转码统一按拍摄方向摆正。「保持原始格式 + 原始分辨率」为直接复制原图，不重新编码。")
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
                lineHeight: 1.4
            }

            Row {
                spacing: Theme.spacingSmall
                layoutDirection: Qt.RightToLeft
                anchors.right: parent.right
                PMButton {
                    text: I18n.tr("取消")
                    height: 30
                    onClicked: exportDialog.close()
                }
                PMButton {
                    objectName: "exportGoBtn"
                    text: I18n.tr("开始导出")
                    height: 30
                    emphasized: true
                    tooltip: I18n.tr("把所选 ") + gallery.selectedIds.length + I18n.tr(" 张照片按上方设置导出")
                    enabled: exportDialog.destDir.length > 0
                             && gallery.selectedIds.length > 0
                    onClicked: exportDialog._apply()
                }
            }
        }
    }

    FolderPickerDialog {
        id: backupPicker
        objectName: "backupPicker"
        dialogTitle: I18n.tr("选择备份保存位置（生成 library_日期.db 备份文件）")
        multiSelect: false
        /* backupTo 由 Python 侧 attachQmlSignals 直连（QML→Python 方法调用
           会间歇性被 PySide 静默丢弃，见 library_bridge.attachQmlSignals 注释） */
        onPathChosen: (folder) => {
            statusText.text = I18n.tr("正在备份到 ") + folder + I18n.tr(" …（完成后提示）")
        }
    }

    FilePickerDialog {
        id: restorePicker
        objectName: "restorePicker"
        dialogTitle: I18n.tr("选择要恢复的备份文件")
        mode: "open"
        /* restoreBackup 由 Python 侧 attachQmlSignals 直连 */
        onFileChosen: (path) => {
            statusText.text = I18n.tr("正在从备份恢复 …（完成后提示）")
        }
    }

    FilePickerDialog {
        id: syncOutPicker
        objectName: "syncOutPicker"
        dialogTitle: I18n.tr("选择元数据导出位置")
        mode: "save"
        defaultSuffix: "meta.db"
        /* syncExport 由 Python 侧 attachQmlSignals 直连 */
        onFileChosen: (path) => {
        }
    }

    FilePickerDialog {
        id: syncInPicker
        objectName: "syncInPicker"
        dialogTitle: I18n.tr("选择元数据包导入")
        mode: "open"
        /* syncImport 由 Python 侧 attachQmlSignals 直连 */
        onFileChosen: (path) => {
        }
    }

    FilePickerDialog {
        id: csvPicker
        objectName: "csvPicker"
        dialogTitle: I18n.tr("选择 CSV 导出位置")
        mode: "save"
        defaultSuffix: "csv"
        onFileChosen: (path) => {
            var r = LibraryBridge.exportCsv(path)
            if (r.startsWith("CSV")) statusText.text = r
            else {
                statusText.text = I18n.tr("CSV 已导出 → ") + r
                toastLayer.show(I18n.tr("元数据 CSV 已导出"), "success")
            }
        }
    }

    /* 0.5.37：上传人脸搜图——选一张含人脸的图片，与库内人脸向量比对 */
    FilePickerDialog {
        id: faceSearchPicker
        objectName: "faceSearchPicker"
        dialogTitle: I18n.tr("选择含人脸的图片用于搜索")
        mode: "open"
        onFileChosen: (path) => {
            statusText.text = I18n.tr("正在按人脸搜索照片 …（完成后自动跳转）")
            LibraryBridge.searchByFace(path)
        }
    }

    /* 0.5.37：低质量人脸清理（隐藏/删除人脸标签，照片不动） */
    FaceCleanDialog {
        id: faceCleanDialog
        onMessageRequested: (msg, kind) => toastLayer.show(msg, kind)
    }

    /* 0.5.67：人物头像批量管理（分拆误并的聚类：归为新人物/并入其他人物） */
    PersonFacesDialog {
        id: personFacesDialog
        onMessageRequested: (msg, kind) => toastLayer.show(msg, kind)
    }

    /* 0.5.53：首次运行引导（注意事项 + 一键设置；帮助菜单可重开） */
    FirstRunDialog {
        id: firstRunDialog
    }
    Timer {
        interval: 900
        running: true
        repeat: false
        onTriggered: {
            if (LibraryBridge && !LibraryBridge.firstRunDone())
                firstRunDialog.open()
        }
    }

    /* 0.5.39：作废确认——说明按钮作用，确认后才生效 */
    Dialog {
        id: archiveConfirm
        objectName: "archiveConfirm"
        modal: true
        width: 480
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        padding: 16

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusLarge
            border.width: 1
            border.color: Theme.divider
        }

        property int pendingCount: 0

        contentItem: ColumnLayout {
            spacing: 10

            Text {
                text: I18n.tr("作废这 ") + archiveConfirm.pendingCount + I18n.tr(" 张照片？")
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                text: I18n.tr("「作废（不删除）」的作用：把这些照片从普通浏览、时间线、事件等视图中隐藏，")
                      + I18n.tr("用于整理掉不想再看到的照片。\n\n")
                      + I18n.tr("· 不会删除、移动或修改任何照片文件\n")
                      + I18n.tr("· 随时可在左侧栏「作废」页面找回并恢复显示\n")
                      + I18n.tr("· 已导出的副本不受影响")
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                lineHeight: 1.4
            }
            Row {
                spacing: Theme.spacingSmall
                layoutDirection: Qt.RightToLeft
                anchors.right: parent.right
                PMButton {
                    text: I18n.tr("取消")
                    height: 30
                    onClicked: archiveConfirm.close()
                }
                PMButton {
                    objectName: "archiveConfirmYesBtn"
                    text: I18n.tr("作废（不删除）")
                    height: 30
                    emphasized: true
                    onClicked: {
                        archiveConfirm.close()
                        var n = LibraryBridge.setArchivedBatch(gallery.selectedIds, true)
                        if (n > 0) {
                            toastLayer.show(I18n.tr("已作废 ") + n + I18n.tr(" 张（可在左栏「作废」中恢复）"), "success")
                            gallery.reloadCurrent()
                        } else {
                            toastLayer.show(I18n.tr("没有可作废的照片"), "warning")
                        }
                    }
                }
            }
        }
    }

    /* 0.5.37：锁定只读——只改文件系统只读属性（防误删/误剪切），
       不写库、不动照片内容；「解除只读」随时可逆 */
    Dialog {
        id: readOnlyDialog
        objectName: "readOnlyDialog"
        modal: true
        width: 560
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        padding: 16

        background: Rectangle {
            color: Theme.surface
            radius: Theme.radiusLarge
            border.width: 1
            border.color: Theme.divider
        }

        property int scope: 0
        property string folderPath: ""

        function _apply(lock) {
            var r
            if (roScopeSelected.checked && gallery.selectedIds.length > 0)
                r = LibraryBridge.lockReadOnlyIds(gallery.selectedIds, lock)
            else if (roScopeFolder.checked && folderPath.length > 0)
                r = LibraryBridge.lockReadOnlyFolder(folderPath, lock)
            else
                r = LibraryBridge.lockReadOnlyAll(lock)
            roNote.text = r
            toastLayer.show(r, "success")
        }

        onOpened: {
            folderPath = ""
            roScopeSelected.checked = gallery.selectedIds.length > 0
            roScopeAll.checked = gallery.selectedIds.length === 0
            roNote.text = ""
        }

        contentItem: ColumnLayout {
            spacing: 10

            Text {
                text: I18n.tr("锁定只读（防误删、误剪切）")
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                text: I18n.tr("只修改文件的只读属性，不改动照片内容与库内数据；资源管理器中删除/剪切只读文件会被系统拦截。随时可点「解除只读」恢复。")
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                lineHeight: 1.4
            }

            RadioButton {
                id: roScopeSelected
                objectName: "roScopeSelected"
                text: I18n.tr("当前所选照片（") + gallery.selectedIds.length + I18n.tr(" 张）")
                enabled: gallery.selectedIds.length > 0
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }
            Row {
                spacing: Theme.spacingSmall
                RadioButton {
                    id: roScopeFolder
                    objectName: "roScopeFolder"
                    text: readOnlyDialog.folderPath.length > 0
                          ? I18n.tr("文件夹：") + readOnlyDialog.folderPath : I18n.tr("指定文件夹…")
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                }
                PMButton {
                    text: I18n.tr("浏览…")
                    height: 26
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: readOnlyFolderPicker.openDialog()
                }
            }
            RadioButton {
                id: roScopeAll
                objectName: "roScopeAll"
                text: I18n.tr("全部在本软件管理范围内的照片")
                font.family: Theme.fontFamily
                font.pixelSize: 13
            }

            Text {
                id: roNote
                Layout.fillWidth: true
                text: ""
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.primary
            }

            Row {
                spacing: Theme.spacingSmall
                layoutDirection: Qt.RightToLeft
                anchors.right: parent.right
                PMButton {
                    text: I18n.tr("关闭")
                    height: 30
                    onClicked: readOnlyDialog.close()
                }
                PMButton {
                    objectName: "roUnlockBtn"
                    text: I18n.tr("解除只读")
                    height: 30
                    onClicked: readOnlyDialog._apply(false)
                }
                PMButton {
                    objectName: "roLockBtn"
                    text: I18n.tr("锁定只读")
                    height: 30
                    emphasized: true
                    onClicked: readOnlyDialog._apply(true)
                }
            }
        }
    }

    FolderPickerDialog {
        id: readOnlyFolderPicker
        objectName: "readOnlyFolderPicker"
        dialogTitle: I18n.tr("选择要锁定只读的文件夹（含子文件夹）")
        multiSelect: false
        onPathChosen: (folder) => {
            readOnlyDialog.folderPath = folder
            roScopeFolder.checked = true
        }
    }

    /* 批量打标签（窗口级弹窗） */
    BatchTagDialog {
        id: batchTagDialog
        onTagRequested: (tag) => {
            var n = LibraryBridge.batchTag(gallery.selectedIds, tag)
            if (n > 0)
                toastLayer.show(I18n.tr("已为 ") + n + I18n.tr(" 张照片添加标签「") + tag + "」", "success")
            else
                toastLayer.show(I18n.tr("添加标签失败"), "error")
        }
    }

    /* 重命名（人物/标签共用） */
    RenameDialog {
        id: renameDialog
        onAccepted: (value) => {
            if (renameDialog.context === "person") {
                var ok = LibraryBridge.renamePerson(renameDialog.personId, value)
                if (ok)
                    toastLayer.show(I18n.tr("已重命名人物为「") + value + "」", "success")
                else
                    toastLayer.show(I18n.tr("重命名失败：名称可能已存在"), "error")
                peoplePage.refresh()
            } else if (renameDialog.context === "album_new") {
                var aid = LibraryBridge.albumCreate(value)
                if (aid > 0) {
                    var n3 = gallery.selectedIds.length > 0
                             ? LibraryBridge.albumAddPhotos(aid, gallery.selectedIds) : 0
                    toastLayer.show(n3 > 0
                        ? (I18n.tr("已创建相册「") + value + I18n.tr("」并加入 ") + n3 + I18n.tr(" 张照片"))
                        : (I18n.tr("已创建相册「") + value + "」"), "success")
                    albumsPage.refresh()
                } else {
                    toastLayer.show(I18n.tr("创建失败：相册名可能已存在"), "error")
                }
            } else if (renameDialog.context === "album_rename") {
                var okR = LibraryBridge.albumRename(renameDialog.personId, value)
                if (okR) {
                    toastLayer.show(I18n.tr("相册已重命名为「") + value + "」", "success")
                    albumsPage.refresh()
                } else {
                    toastLayer.show(I18n.tr("重命名失败：名称可能已存在"), "error")
                }
            } else {
                var n = LibraryBridge.renameTag(renameDialog.initialValue, value)
                if (n > 0)
                    toastLayer.show(I18n.tr("标签已重命名为「") + value + "」", "success")
                else
                    toastLayer.show(I18n.tr("重命名失败：标签可能不存在或已存在同名"), "error")
                tagsPage.refresh()
            }
        }
    }

    /* 删除相册确认（只删分组与关联，照片文件不受影响） */
    Dialog {
        id: albumDeleteConfirm
        objectName: "albumDeleteConfirm"
        modal: true
        title: I18n.tr("删除相册")
        standardButtons: Dialog.Yes | Dialog.No
        width: 420
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        property int albumId: 0
        property string albumName: ""
        contentItem: Label {
            text: I18n.tr("删除相册「") + albumDeleteConfirm.albumName + "」？\n\n"
                + I18n.tr("只移除该分组及其照片关联，<b>不会删除任何照片文件</b>，")
                + I18n.tr("照片仍保留在库中。")
            font.family: Theme.fontFamily
            wrapMode: Text.Wrap
            textFormat: Text.RichText
        }
        onAccepted: {
            var ok = LibraryBridge.albumDelete(albumDeleteConfirm.albumId)
            if (ok) {
                toastLayer.show(I18n.tr("相册已删除（照片文件不受影响）"), "success")
                albumsPage.refresh()
            } else {
                toastLayer.show(I18n.tr("删除失败"), "error")
            }
        }
    }

    /* 合并（人物/标签共用） */
    MergePickerDialog {
        id: mergePickerDialog
        onPicked: (item) => {
            if (mergePickerDialog.mode === "person") {
                var ok = LibraryBridge.mergePersons(mergePickerDialog.sourceId, item.id)
                if (ok)
                    toastLayer.show(I18n.tr("人物已合并"), "success")
                else
                    toastLayer.show(I18n.tr("合并失败"), "error")
                peoplePage.refresh()
            } else {
                var n = LibraryBridge.mergeTags(mergePickerDialog.sourceTag, item.name)
                if (n > 0)
                    toastLayer.show(I18n.tr("标签已合并"), "success")
                else
                    toastLayer.show(I18n.tr("合并失败"), "error")
                tagsPage.refresh()
            }
        }
    }

    /* 拆分照片到其他人物/新建人物 */
    PersonMoveDialog {
        id: personMoveDialog
        onPicked: (personId) => {
            var ok
            if (personMoveDialog.faceMode) {
                var newId = personId
                if (personId === -1)
                    newId = LibraryBridge.newPerson("")
                ok = LibraryBridge.assignFace(personMoveDialog.faceId, newId)
                toastLayer.show(I18n.tr("人脸已指派") + (ok ? I18n.tr("成功") : I18n.tr("失败")), ok ? "success" : "error")
                if (ok) {
                    infoPanel.refreshFaces(infoPanel.currentId)
                    gallery.refreshMeta(infoPanel.currentId)
                    photoViewer._loadFaces()
                }
                return
            }
            if (personId === -1) {
                var newId2 = LibraryBridge.newPerson("")
                ok = LibraryBridge.movePhotosToPerson(personMoveDialog.targetPhotos, newId2)
                toastLayer.show(I18n.tr("已移出为新建人物"), ok ? "success" : "error")
            } else {
                ok = LibraryBridge.movePhotosToPerson(personMoveDialog.targetPhotos, personId)
                toastLayer.show(I18n.tr("照片已移出到该人物"), ok ? "success" : "error")
            }
            var pid = parseInt(gallery._filterValue)
            if (pid > 0)
                gallery.loadPerson(pid)
            else
                gallery.loadAll()
        }
    }

    /* 图库右键上下文菜单（窗口级，坐标经 popup 相对父项换算） */
    Menu {
        id: galleryMenu
        objectName: "galleryMenu"
        title: I18n.tr("照片操作")

        function applyColorLabel(c) {
            var n = LibraryBridge.setColorLabel(gallery.selectedIds, c)
            if (n > 0) {
                toastLayer.show(c === "" ? I18n.tr("已清除色标") : (I18n.tr("已为 ") + n + I18n.tr(" 张照片设置色标")), "success")
                gallery.refreshColorLabels()
            } else {
                toastLayer.show(I18n.tr("没有可设置的照片"), "warning")
            }
        }

        MenuItem {
            objectName: "ctxOpen"
            text: I18n.tr("打开大图")
            onTriggered: {
                var i = gallery.firstSelectedIndex()
                if (i >= 0) {
                    photoViewer.setContext(gallery.gridIds, i)
                    photoViewer.showCurrent()
                }
            }
        }
        MenuItem {
            objectName: "ctxOpenFolder"
            text: I18n.tr("打开所在文件夹")
            onTriggered: {
                var i = gallery.firstSelectedIndex()
                if (i >= 0)
                    LibraryBridge.openFolder(gallery.gridIds[i])
            }
        }
        MenuItem {
            objectName: "ctxFindSimilar"
            text: I18n.tr("查找相似照片")
            onTriggered: {
                var i = gallery.firstSelectedIndex()
                if (i >= 0)
                    LibraryBridge.findSimilar(gallery.gridIds[i])
            }
        }
        MenuSeparator {}
        MenuItem {
            objectName: "ctxBatchTag"
            text: I18n.tr("批量打标签…")
            onTriggered: {
                batchTagDialog.label = I18n.tr("为所选 ") + gallery.selectedIds.length + I18n.tr(" 张照片添加标签：")
                batchTagDialog.open()
            }
        }
        Menu {
            id: ctxAddToAlbum
            objectName: "ctxAddToAlbum"
            title: I18n.tr("添加到相册…")
            property var albumList: []
            onAboutToShow: ctxAddToAlbum.albumList = LibraryBridge.albums()
            Instantiator {
                model: ctxAddToAlbum.albumList
                delegate: MenuItem {
                    required property var modelData
                    text: modelData.name + "（" + modelData.photoCount + "）"
                    onTriggered: {
                        var n = LibraryBridge.albumAddPhotos(modelData.id, gallery.selectedIds)
                        if (n > 0)
                            toastLayer.show(I18n.tr("已把 ") + n + I18n.tr(" 张照片加入「") + modelData.name + "」", "success")
                        else
                            toastLayer.show(I18n.tr("所选照片已在该相册中"), "warning")
                    }
                }
                onObjectAdded: (index, object) => ctxAddToAlbum.insertItem(index, object)
                onObjectRemoved: (index, object) => ctxAddToAlbum.removeItem(object)
            }
            MenuSeparator {}
            MenuItem {
                objectName: "ctxAlbumNew"
                text: I18n.tr("新建相册并加入…")
                onTriggered: {
                    renameDialog.title = I18n.tr("新建相册")
                    renameDialog.context = "album_new"
                    renameDialog.personId = 0
                    renameDialog.initialValue = ""
                    renameDialog.open()
                }
            }
        }
        MenuItem {
            objectName: "ctxRemoveFromAlbum"
            text: I18n.tr("从相册移出")
            visible: gallery._mode === "album"
            onTriggered: {
                var n = LibraryBridge.albumRemovePhotos(gallery._filterValue, gallery.selectedIds)
                if (n > 0) {
                    toastLayer.show(I18n.tr("已从相册移出 ") + n + I18n.tr(" 张（照片本身不受影响）"), "success")
                    gallery.reloadCurrent()
                } else {
                    toastLayer.show(I18n.tr("没有可移出的照片"), "warning")
                }
            }
        }
        Menu {
            id: ctxColorMenu
            objectName: "ctxColorMenu"
            title: I18n.tr("色标")
            MenuItem { text: I18n.tr("🔴 红"); onTriggered: galleryMenu.applyColorLabel("red") }
            MenuItem { text: I18n.tr("🟡 黄"); onTriggered: galleryMenu.applyColorLabel("yellow") }
            MenuItem { text: I18n.tr("🟢 绿"); onTriggered: galleryMenu.applyColorLabel("green") }
            MenuItem { text: I18n.tr("🔵 蓝"); onTriggered: galleryMenu.applyColorLabel("blue") }
            MenuItem { text: I18n.tr("🟣 紫"); onTriggered: galleryMenu.applyColorLabel("purple") }
            MenuSeparator {}
            MenuItem { text: I18n.tr("清除色标"); onTriggered: galleryMenu.applyColorLabel("") }
        }
        MenuItem {
            objectName: "ctxExport"
            text: I18n.tr("导出所选…")
            onTriggered: exportDialog.open()
        }
        MenuItem {
            objectName: "ctxMoveOut"
            text: I18n.tr("移出所选…")
            onTriggered: moveOutPicker.openDialog()
        }
        MenuSeparator {}
        MenuItem {
            objectName: "ctxArchive"
            text: I18n.tr("作废所选（不删除）")
            onTriggered: {
                archiveConfirm.pendingCount = gallery.selectedIds.length
                archiveConfirm.open()
            }
        }
        MenuItem {
            objectName: "ctxRestore"
            text: I18n.tr("恢复所选（取消作废）")
            onTriggered: {
                var n = LibraryBridge.setArchivedBatch(gallery.selectedIds, false)
                if (n > 0) {
                    toastLayer.show(I18n.tr("已恢复 ") + n + I18n.tr(" 张到普通浏览"), "success")
                    gallery.reloadCurrent()
                } else {
                    toastLayer.show(I18n.tr("所选照片都未作废"), "warning")
                }
            }
        }
        MenuSeparator {}
        MenuItem {
            objectName: "ctxCopyPath"
            text: I18n.tr("复制所选路径")
            onTriggered: {
                LibraryBridge.setClipboard(gallery.selectedPathsText())
                toastLayer.show(I18n.tr("已复制 ") + gallery.selectedIds.length + I18n.tr(" 条路径到剪贴板"), "success")
            }
        }
    }

    /* 键盘快捷键 */
    Shortcut {
        id: scCtrlF
        objectName: "scCtrlF"
        sequence: "Ctrl+F"
        onActivated: searchField.forceActiveFocus()
    }
    Shortcut {
        id: scCtrlA
        objectName: "scCtrlA"
        sequence: "Ctrl+A"
        onActivated: gallery.selectAllLoaded()
    }
    /* 0.5.35：常见快捷操作（Lightroom/ACDSee 习惯） */
    Shortcut {
        id: scF5
        objectName: "scF5"
        sequence: "F5"
        enabled: !popupGate.isOpen()
        onActivated: gallery.reloadCurrent()
    }
    Shortcut {
        id: scSpace
        objectName: "scSpace"
        sequence: "Space"
        /* 有选中且在图库页时接管空格开大图；无选择时空格仍用于网格滚动 */
        enabled: !popupGate.isOpen() && gallery.visible && gallery.selectedIds.length > 0
        onActivated: {
            var ids = gallery.selectedIds.slice()
            photoViewer.setContext(ids, 0)
            photoViewer.showCurrent()
        }
    }
    Shortcut {
        id: scReturn
        objectName: "scReturn"
        sequence: "Return"
        enabled: !popupGate.isOpen() && gallery.visible && gallery.selectedIds.length > 0
        onActivated: {
            var ids = gallery.selectedIds.slice()
            photoViewer.setContext(ids, 0)
            photoViewer.showCurrent()
        }
    }
    Shortcut {
        id: scCtrlComma
        objectName: "scCtrlComma"
        sequence: "Ctrl+,"
        enabled: !popupGate.isOpen()
        onActivated: settingsDialog.openSettings()
    }

    /* 弹窗门卫：聚合窗口级所有可关闭弹窗，Esc 统一收起 */
    QtObject {
        id: popupGate
        objectName: "popupGate"
        property var popups: [helpDialog, aboutDialog, toolsDialog, pathsDialog, analysisProgress,
            advancedSearch, scanPicker, moveOutPicker, moveOutConfirm, exportPicker,
            backupPicker, restorePicker, syncOutPicker, syncInPicker, batchTagDialog,
            renameDialog, mergePickerDialog, personMoveDialog, csvPicker,
            suggestPopup, galleryMenu]
        function isOpen() {
            for (var i = 0; i < popups.length; ++i)
                if (popups[i].opened) return true
            return false
        }
        function closeAll() {
            for (var i = 0; i < popups.length; ++i)
                if (popups[i].opened) popups[i].close()
        }
    }

    Shortcut {
        id: scEsc
        objectName: "scEsc"
        sequence: "Esc"
        enabled: popupGate.isOpen()
        onActivated: popupGate.closeAll()
    }

    /* 0.6.2/0.6.3：语言选择菜单（语言按钮弹出；列出全部内置/用户语言包）。
       用 Instantiator + ListModel 声明式构建——Menu 的 clear()/takeItem()
       等从 JS 调用受限（clear 非 Q_INVOKABLE、takeItem 参数桥接报错），
       ListModel.clear()/append() 是项目里久经考验的安全路径。 */
    Component.onCompleted: {
            // 0.5.66：界面语言初始化（单例不碰 LibraryBridge，由本文件传入）
            // 0.6.2：先刷新语言清单（含用户包），否则已保存的自装语言会被拒
            window._i18nRefreshLangs()
            var _savedLang = LibraryBridge.uiLang()
            I18n.initFromSettings(_savedLang,
                         LibraryBridge.i18nCatalog(_savedLang))
        mainContent.showAll()
        /* 0.5.67：启动窗口最大化（设置 → 启动与常驻，默认开）。
           Qt.callLater 延迟到绑定求值/窗口显示流程之后，直接置可能被
           visible 绑定覆盖而不生效（用户实测）。 */
        if (LibraryBridge.startupMaximizedEnabled())
            Qt.callLater(function () { window.visibility = Window.Maximized })
    }

    onClosing: (close) => {
        /* 0.5.48：关闭窗口→最小化到托盘继续后台运行（设置默认开；系统托盘
           不可用或正在退出时自动失效，绝不把用户关进「隐形应用」） */
        if (typeof TrayHelper !== "undefined" && TrayHelper
                && TrayHelper.trayActive() && !TrayHelper.quitting()) {
            close.accepted = false
            window.hide()
            TrayHelper.notifyHidden()
            return
        }
        /* 正常退出时自动备份（保留最近 10 份），防止崩溃/误操作丢失人工标注 */
        var r = LibraryBridge.backupOnExit()
        if (r.length > 0 && r.charAt(0) !== I18n.tr("备")) {
            console.log(I18n.tr("退出自动备份：") + r)
        }
    }

    /* 大图查看独立窗口（屏幕居中，可调大小） */
    PhotoViewer {
        id: photoViewer
        onAssignFaceRequested: (faceId) => {
            personMoveDialog.faceMode = true
            personMoveDialog.faceId = faceId
            personMoveDialog.currentPersonId = 0
            personMoveDialog.open()
        }
        /* 0.5.29：查看器翻页/评级/旗标时右栏自动跟随（含首次打开同步） */
        onCurrentChanged: (photoId) => {
            if (photoId > 0)
                infoPanel.showDetail(LibraryBridge.photoDetail(photoId))
        }
    }

    /* 启动预热（0.5.29）：空闲 2.5 秒后预解码一张缩略图，把图像管线
       （解码线程池/着色器编译/首次纹理上传）的一次性成本消化在启动阶段，
       消除I18n.tr("第一次点击照片右栏要等一会")的冷启动延迟 */
    Timer {
        id: warmupTimer
        interval: 2500
        running: true
        repeat: false
        onTriggered: {
            var ids = gallery.gridIds
            if (ids && ids.length > 0) {
                var d = LibraryBridge.photoDetail(ids[0])
                if (d && d.thumb)
                    warmImage.source = d.thumb
            }
        }
    }
    Image {
        id: warmImage
        source: ""
        width: 1
        height: 1
        opacity: 0
        cache: true
        asynchronous: true
    }

    /* 轻提示浮层（窗口级，置于最上层） */
    Toast {
        id: toastLayer
    }
}
