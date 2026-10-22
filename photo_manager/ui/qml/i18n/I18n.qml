pragma Singleton
import QtQuick

// 多语言支持（0.5.66）：数据驱动的语言包架构。
// 加新语言 = 在本目录放入 <code>.json（键为中文源串，值为译文）并在
// availableLanguages 登记——无需改动其他代码。
// 缺词自动回退中文；tr() 保留原文首尾空白（拼接碎片友好）。
//
// 注意：本单例刻意不直接访问 LibraryBridge（单例作用域不保证可见上下文属性）。
// 上下文相关 I/O（读取设置、读语言包文件）由 main.qml 在调用点传入：
//   I18n.initFromSettings(LibraryBridge.uiLang(),
//                         LibraryBridge.i18nCatalog(LibraryBridge.uiLang()))
//   I18n.setLang(code, LibraryBridge.i18nCatalog(code))
QtObject {
    id: root

    property string lang: "zh"
    property var catalog: ({})
    property var availableLanguages: ["zh", "en"]
    property var languageNames: {"zh": "中文", "en": "English"}
    property string lastError: ""   // 诊断

    // 翻译查找：s 为源串（中文，可含首尾空白）；按 trim 后的键查，
    // 命中则保留原文首尾空白；未命中回退原文。
    function tr(s) {
        if (lang === "zh" || !s)
            return s
        if (!/[\u4e00-\u9fa5]/.test(s))
            return s
        var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s)
        var lead = m ? m[1] : ""
        var core = m ? m[2] : s
        var trail = m ? m[3] : ""
        if (!/[\u4e00-\u9fa5]/.test(core))
            return s
        var t = catalog[core]
        if (t === undefined)
            return s
        return lead + t + trail
    }

    function trFmt(s) {
        var t = tr(s)
        for (var i = 1; i < arguments.length; ++i)
            t = t.replace("%" + i, arguments[i])
        return t
    }

    function setLang(code, catalogText) {
        if (availableLanguages.indexOf(code) < 0) {
            lastError = "lang not available: " + code
            return
        }
        lang = code
        if (code === "zh" || !catalogText) {
            catalog = {}
            return
        }
        try {
            catalog = JSON.parse(catalogText)
            lastError = ""
        } catch (e) {
            catalog = {}
            lastError = "parse: " + e
        }
    }

    function initFromSettings(savedLang, catalogText) {
        if (availableLanguages.indexOf(savedLang) >= 0 && savedLang !== "zh")
            setLang(savedLang, catalogText)
    }
}
