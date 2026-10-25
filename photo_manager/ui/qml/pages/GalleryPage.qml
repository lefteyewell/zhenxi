import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import components 1.0
import i18n 1.0

/* 中央图库：真实缩略图网格（全部照片 / 事件 / 搜索结果），支持选择与详情联动，
   滚动到底自动加载更多（分页 500/批），缩略图异步解码。 */
Item {
    id: root
    objectName: "galleryPage"

    property string pageTitle: I18n.tr("全部照片")
    /* 0.6.6：标题语种跟随——pageTitle 此前在加载函数里一次性赋值（绑定
       断裂），切语言后不重译（用户反馈"偶尔未跟随切换"）。改为记录
       种类+参数，语言切换时 _applyTitle() 重算。 */
    property string _titleKind: "all"
    property string _titleArg: ""
    function _setTitle(kind, arg) {
        _titleKind = kind
        _titleArg = arg || ""
        _applyTitle()
    }
    function _applyTitle() {
        var k = _titleKind, a = _titleArg
        if (k === "all") pageTitle = I18n.tr("全部照片")
        else if (k === "event") pageTitle = I18n.tr("事件照片")
        else if (k === "folder") pageTitle = I18n.tr("文件夹：") + a
        else if (k === "person") pageTitle = I18n.tr("人物")
        else if (k === "place") pageTitle = I18n.tr("地点：") + a
        else if (k === "device") pageTitle = I18n.tr("设备：") + a
        else if (k === "tag") pageTitle = I18n.tr("标签：") + a
        else if (k === "search") pageTitle = I18n.tr("搜索：") + a
        else if (k === "taken") pageTitle = I18n.tr("拍摄：") + a
        else if (k === "rating") pageTitle = (parseFloat(a) > 0)
            ? (I18n.tr("评级 ≥ ") + a + " ★") : I18n.tr("已评级")
        else if (k === "flag") pageTitle = a === "pick" ? I18n.tr("精选照片")
            : a === "reject" ? I18n.tr("排除照片") : I18n.tr("未标记")
        else if (k === "stack") pageTitle = I18n.tr("堆叠照片")
        else if (k === "album") pageTitle = I18n.tr("相册：") + a
        else if (k === "similar") pageTitle = I18n.tr("相似照片")
        else if (k === "facesearch") pageTitle = I18n.tr("人脸搜索结果")
        else pageTitle = I18n.tr("全部照片")
    }
    Connections {
        target: I18n
        function onLangChanged() { root._applyTitle() }
    }
    property int currentEventId: -1
    property var selectedIds: []
    property int totalCount: 0
    property var gridIds: []

    signal photoClicked(int photoId)
    signal photoContextRequested(var ids, int index)
    signal contextMenuRequested(int gx, int gy)
    signal batchTagRequested()
    signal batchExportRequested()
    signal batchMoveOutRequested()
    signal batchCopyRequested(string paths)
    signal moveOutOfPersonRequested()
    signal personFacesRequested(int personId)
    signal backRequested()

    property string _mode: "all"
    property int _loaded: 0
    property var _seenIds: ({})   /* 0.5.67 已加载照片 id 去重表（防分页重叠重复显示） */
    /* 0.5.64 分段重构：分组模式的分组存储。
       _groupStore: [{dir, model(ListModel)}]，dir 唯一、按文件夹序追加；
       groupSectionsModel: 外层分段 ListView 的模型（dir/name 两列）。
       折叠只是 UI 状态（collapsedFolders），成员始终留在组模型里。 */
    property int _curGroupCount: 0
    property var _groupStore: []
    property var _cellRegistry: []   /* 分组模式可见卡片注册表（圈选几何命中用） */
    /* 圈选/落点的坐标系：平铺=gridView，分组=groupList（卡片 mapToItem 目标） */
    property Item _viewport: null
    property bool _busy: false
    property bool stackMode: false
    property var _filterValue: ""
    property real _filterLat: 0
    property real _filterLon: 0
    property int backTarget: 0

    /* 缩略图单元格尺寸：由 ThemeController.thumbSize 持久化控制（ACDsee 风格的可调缩略图） */
    property int cellSize: ThemeController ? ThemeController.thumbSize : 160

    /* Shift 范围选择的锚点：上次点击的索引；换页/重新加载时重置为 -1 */
    property int _anchorIndex: -1

    /* ---- 拖动圈选（0.5.30） ---- */
    property bool _rubberActive: false
    property point _rubberStart
    property point _rubberCur
    /* replace=普通拖动（圈中即全部所选）；add=Ctrl/Shift+拖动（在原选择上追加） */
    property string _rubberMode: "replace"
    property var _rubberBaseSel: []
    property bool _suppressClick: false
    /* 按下手势状态放在根部（单手势全局唯一；放 MouseArea 上会让它变成
       合成子类 QQuickMouseArea_QML_n，破坏 gui_check 的 className 精确匹配） */
    property point _pressPos
    property bool _cellLeftPressed: false

    /* 0.5.36：图库排序（桥接层持久化；列表端只存键，换视图后仍生效） */
    property string sortKey: "time_desc"
    readonly property var _sortLabels: [
        {"key": "time_desc", "label": I18n.tr("拍摄时间 新→旧")},
        {"key": "time_asc",  "label": I18n.tr("拍摄时间 旧→新")},
        {"key": "name",      "label": I18n.tr("文件名 A→Z")},
        {"key": "folder",    "label": I18n.tr("文件夹/路径")},
        {"key": "camera",    "label": I18n.tr("相机型号")},
        {"key": "rating",    "label": I18n.tr("评级 高→低")},
        {"key": "size",      "label": I18n.tr("文件大小 大→小")}
    ]
    function _sortLabel(key) {
        for (var i = 0; i < _sortLabels.length; ++i)
            if (_sortLabels[i].key === key) return _sortLabels[i].label
        return key
    }
    function _applySort(key) {
        sortKey = key
        LibraryBridge.setGallerySort(key)
        reloadCurrent()
    }
    Component.onCompleted: {
        var k = LibraryBridge.gallerySort()
        if (k && k.length > 0) sortKey = k
    }

    /* 拖动结束：按圈选矩形命中格子。
       平铺模式：网格等距，索引可反算（原有路径）。
       分组模式（0.5.64 分段重构）：Flow 布局行高不定，改为对可见格子
       注册表做几何相交判定。 */
    function _finishRubber() {
        if (root._inGroupMode()) { _finishRubberGroup(); return }
        var pitch = gridView.cellWidth
        var cols = Math.max(1, Math.floor(gridView.width / pitch))
        var x1 = Math.min(_rubberStart.x, _rubberCur.x) + gridView.contentX
        var x2 = Math.max(_rubberStart.x, _rubberCur.x) + gridView.contentX
        var y1 = Math.min(_rubberStart.y, _rubberCur.y) + gridView.contentY
        var y2 = Math.max(_rubberStart.y, _rubberCur.y) + gridView.contentY
        var c1 = Math.max(0, Math.floor(x1 / pitch))
        var c2 = Math.floor(x2 / pitch)
        var r1 = Math.max(0, Math.floor(y1 / pitch))
        var r2 = Math.floor(y2 / pitch)
        if (_rubberMode === "replace") {
            for (var i = 0; i < gridModel.count; ++i)
                gridModel.setProperty(i, "selected", false)
        }
        var sel = (_rubberMode === "add") ? _rubberBaseSel.slice() : []
        var lastIdx = -1
        for (var r = r1; r <= r2; ++r) {
            for (var c = c1; c <= c2; ++c) {
                var idx = r * cols + c
                if (idx >= gridModel.count)
                    break
                var dg = gridModel.get(idx)
                if (dg.type)
                    continue   /* 组头/占位行不参与圈选 */
                gridModel.setProperty(idx, "selected", true)
                sel.push(dg.id)
                lastIdx = idx
            }
        }
        var uniq = []
        for (var k = 0; k < sel.length; ++k)
            if (uniq.indexOf(sel[k]) < 0)
                uniq.push(sel[k])
        root.selectedIds = uniq
        if (lastIdx >= 0)
            root._anchorIndex = lastIdx
    }

    function _finishRubberGroup() {
        /* 0.5.67：改用 _viewportItem()——此前用 root._viewport 属性，
           该属性声明后从未赋值（恒 null），导致分组模式圈选只画框、
           不选中（早期 return），用户实测复现。 */
        var vp = root._viewportItem()
        if (!vp) return
        var x1 = Math.min(_rubberStart.x, _rubberCur.x)
        var x2 = Math.max(_rubberStart.x, _rubberCur.x)
        var y1 = Math.min(_rubberStart.y, _rubberCur.y)
        var y2 = Math.max(_rubberStart.y, _rubberCur.y)
        if (_rubberMode === "replace")
            _clearAllSelections()
        var sel = (_rubberMode === "add") ? _rubberBaseSel.slice() : []
        var lastPid = -1
        for (var i = 0; i < root._cellRegistry.length; ++i) {
            var cell = root._cellRegistry[i]
            var p = cell.mapToItem(vp, 0, 0)
            if (p.x < x2 && p.x + cell.width > x1 &&
                    p.y < y2 && p.y + cell.height > y1) {
                _setSelectedByPid(cell.thePid, true)
                sel.push(cell.thePid)
                lastPid = cell.thePid
            }
        }
        var uniq = []
        for (var k = 0; k < sel.length; ++k)
            if (uniq.indexOf(sel[k]) < 0)
                uniq.push(sel[k])
        root.selectedIds = uniq
        root._anchorIndex = lastPid >= 0 ? _visibleIndexOfPid(lastPid) : -1
    }

    function _reset() {
        gridModel.clear()
        gridIds = []
        _seenIds = ({})
        _loaded = 0
        _busy = false
        _anchorIndex = -1
        _lastGroupDir = ""
        _curGroupCount = 0
        /* 0.5.64 分段重构：分组存储一并清空 */
        _groupStore = []
        groupSectionsModel.clear()
        collapsedFolders = ({})
        clearSelection()
    }

    function _append(arr) {
        for (var i = 0; i < arr.length; ++i) {
            /* 0.5.67：按 id 去重——后端分页若因排序并列/语义回退出现重叠页，
               不再重复显示同一张缩略图（_seenIds 对象查找 O(1)）。 */
            if (_seenIds[arr[i].id])
                continue
            _seenIds[arr[i].id] = true
            /* 后端 _pack 不返回 selected 字段，若不初始化，delegate 里的
               model.selected 会是 undefined（选中态绑定不可靠）。 */
            arr[i].selected = false
            /* 0.5.64 分组模式改为分段列表存储：每组一个 ListModel，
               组头行高 32px（原 GridView 独占整行方案组头行高=格子边长，
               上下大片空白——用户反馈「空白位置太多」后重构）。
               折叠仅是 UI 状态（成员留在组模型里，Flow 隐藏），不再搬行。 */
            if (root._inGroupMode()) {
                var dir = _dirOf(arr[i].path)
                var gi = _groupStoreIndexOf(dir)
                if (gi < 0) {
                    var lm = Qt.createQmlObject(
                        "import QtQuick; ListModel { }", root,
                        "GroupModel_" + _groupStore.length)
                    _groupStore.push({ dir: dir, model: lm })
                    /* 外层分段模型追加一行（dir 唯一，组按文件夹序到达） */
                    var parts = dir.split("/")
                    groupSectionsModel.append(
                        { dir: dir, name: parts[parts.length - 1] || dir })
                    gi = _groupStore.length - 1
                }
                _groupStore[gi].model.append(arr[i])
                _curGroupCount += 1
            } else {
                gridModel.append(arr[i])
                gridIds.push(arr[i].id)
            }
        }
        _loaded += arr.length
        _busy = false
        var label = _mode === "all" && totalCount > 0
                    ? _loaded + " / " + totalCount + I18n.tr(" 张")
                    : _loaded + I18n.tr(" 张")
        var more = _mode === "all" && totalCount > 0 ? _loaded < totalCount : true
        if (more) label += I18n.tr("（滚动加载更多）")
        countText.text = label
    }

    function _fetchMore() {
        if (_busy) return
        _busy = true
        var arr
        if (_mode === "all")
            arr = root.groupMode
                  ? LibraryBridge.photosByFolder(_loaded, 500)
                  : LibraryBridge.photos(_loaded, 500)
        else if (_mode === "event")
            arr = LibraryBridge.eventPhotos(currentEventId, _loaded, 500)
        else if (_mode === "folder")
            arr = LibraryBridge.folderPhotos(_filterValue, _loaded, 500)
        else if (_mode === "dir")
            arr = LibraryBridge.dirPhotos(_filterValue, _loaded, 500)
        else if (_mode === "person")
            arr = LibraryBridge.personPhotos(_filterValue, _loaded, 500)
        else if (_mode === "location")
            arr = LibraryBridge.locationPhotos(_filterLat, _filterLon, _loaded, 500)
        else if (_mode === "device")
            arr = LibraryBridge.devicePhotos(_filterValue, _loaded, 500)
        else if (_mode === "tag")
            arr = LibraryBridge.tagPhotos(_filterValue, _loaded, 500)
        else if (_mode === "month")
            arr = LibraryBridge.dateMonthPhotos(_filterValue, _loaded, 500)
        else if (_mode === "day")
            arr = LibraryBridge.datePhotos(_filterValue, _loaded, 500)
        else if (_mode === "rated")
            arr = LibraryBridge.ratedPhotos(_filterValue, _loaded, 500)
        else if (_mode === "flag")
            arr = LibraryBridge.flagPhotos(_filterValue, _loaded, 500)
        else if (_mode === "stacks")
            arr = LibraryBridge.galleryStacks(_loaded, 500)
        else if (_mode === "album")
            arr = LibraryBridge.albumPhotos(_filterValue, _loaded, 500)
        else if (_mode === "similar")
            arr = LibraryBridge.similarPhotos(_loaded, 500)
        else if (_mode === "facesearch")
            arr = LibraryBridge.faceSearchPhotos(_loaded, 500)
        else
            arr = LibraryBridge.searchPhotos(pageTitle.slice(3), _loaded, 500)
        _append(arr)
    }

    function loadAll() {
        root._setTitle("all", "")
        currentEventId = -1
        totalCount = LibraryBridge.totalPhotos()
        _mode = "all"
        _reset()
        _fetchMore()
    }

    /* 刷新单张照片元数据（评分/旗标/人脸/色标被改后调用） */
    function refreshMeta(photoId) {
        /* 0.5.64：两种模式的存储都查（分组模式含折叠组的成员） */
        var models = _inGroupMode() ? _allGroupModels() : [gridModel]
        for (var m = 0; m < models.length; ++m) {
            var mm = models[m]
            for (var i = 0; i < mm.count; ++i) {
                var it = mm.get(i)
                if (it.id === photoId) {
                    var d = LibraryBridge.photoDetail(photoId)
                    mm.setProperty(i, "rating", d.rating || 0)
                    mm.setProperty(i, "flag", d.flag || "")
                    mm.setProperty(i, "faceCount", d.faces || 0)
                    mm.setProperty(i, "colorLabel", d.colorLabel || "")
                    return
                }
            }
        }
    }

    /* 批量刷新所选照片的色标（右键菜单改色标后调用，避免整页重载） */
    function refreshColorLabels() {
        for (var s = 0; s < selectedIds.length; ++s) {
            refreshMeta(selectedIds[s])
        }
    }

    function loadEvent(eventId) {
        root._setTitle("event", "")
        currentEventId = eventId
        _mode = "event"
        backTarget = 1
        _reset()
        _fetchMore()
    }

    function loadFolder(folder) {
        root._setTitle("folder", folder)
        _mode = "folder"
        _filterValue = folder
        currentEventId = -1
        totalCount = LibraryBridge.folderCount(folder)
        backTarget = 0
        _reset()
        _fetchMore()
    }

    function loadDir(dir) {
        root._setTitle("folder", dir)
        _mode = "dir"
        _filterValue = dir
        currentEventId = -1
        totalCount = LibraryBridge.dirCount(dir)
        backTarget = 0
        _reset()
        _fetchMore()
    }

    function loadPerson(personId) {
        root._setTitle("person", "")
        _mode = "person"
        _filterValue = personId
        currentEventId = -1
        totalCount = LibraryBridge.personCount(personId)
        backTarget = 3
        _reset()
        _fetchMore()
    }

    function loadLocation(lat, lon) {
        root._setTitle("place", lat.toFixed(2) + ", " + lon.toFixed(2))
        _mode = "location"
        _filterLat = lat
        _filterLon = lon
        currentEventId = -1
        totalCount = LibraryBridge.locationCount(lat, lon)
        backTarget = 4
        _reset()
        _fetchMore()
    }

    function loadDevice(model) {
        root._setTitle("device", model)
        _mode = "device"
        _filterValue = model
        currentEventId = -1
        totalCount = LibraryBridge.deviceCount(model)
        backTarget = 5
        _reset()
        _fetchMore()
    }

    function loadTag(tag) {
        root._setTitle("tag", tag)
        _mode = "tag"
        _filterValue = tag
        currentEventId = -1
        totalCount = LibraryBridge.tagCount(tag)
        backTarget = 6
        _reset()
        _fetchMore()
    }

    function search(q) {
        root._setTitle("search", q)
        currentEventId = -1
        _mode = "search"
        totalCount = 0   /* 搜索结果总数未知：0 可避免 atYEnd 用旧 totalCount 反复拉取 */
        backTarget = 0
        _reset()
        _fetchMore()
    }

    function loadDateMonth(ym) {
        root._setTitle("taken", ym)
        _mode = "month"
        _filterValue = ym
        currentEventId = -1
        totalCount = LibraryBridge.dateMonthCount(ym)
        backTarget = 11
        _reset()
        _fetchMore()
    }

    function loadDateDay(day) {
        root._setTitle("taken", day)
        _mode = "day"
        _filterValue = day
        currentEventId = -1
        totalCount = LibraryBridge.dateCount(day)
        backTarget = 11
        _reset()
        _fetchMore()
    }

    /* 快速筛选：按评级/旗标 */
    function loadRated(min) {
        root._setTitle("rating", String(min))
        _mode = "rated"
        _filterValue = min
        currentEventId = -1
        totalCount = LibraryBridge.ratedCount(min)
        backTarget = 0
        _reset()
        _fetchMore()
    }

    function loadFlag(f) {
        root._setTitle("flag", f)
        _mode = "flag"
        _filterValue = f
        currentEventId = -1
        totalCount = LibraryBridge.flagCount(f)
        backTarget = 0
        _reset()
        _fetchMore()
    }

    function loadStacks() {
        root._setTitle("stack", "")
        _mode = "stacks"
        currentEventId = -1
        totalCount = LibraryBridge.stackCount()
        backTarget = 0
        stackMode = true
        _reset()
        _fetchMore()
    }

    function loadAlbum(albumId, albumName) {
        root._setTitle("album", albumName)
        _mode = "album"
        _filterValue = albumId
        currentEventId = -1
        totalCount = LibraryBridge.albumPhotoCount(albumId)
        backTarget = 17
        stackMode = false
        _reset()
        _fetchMore()
    }

    function loadSimilar() {
        root._setTitle("similar", "")
        _mode = "similar"
        currentEventId = -1
        totalCount = LibraryBridge.similarCount()
        backTarget = 0
        stackMode = false
        _reset()
        _fetchMore()
    }

    /* 0.5.37：上传人脸搜图结果（相似度降序，附 score） */
    function loadFaceSearch() {
        root._setTitle("facesearch", "")
        _mode = "facesearch"
        currentEventId = -1
        totalCount = LibraryBridge.faceSearchCount()
        backTarget = 0
        stackMode = false
        _reset()
        _fetchMore()
    }

    /* 重新加载当前视图（归档/取消归档后刷新网格，使隐藏/恢复立即生效） */
    function reloadCurrent() {
        if (_mode === "all") loadAll()
        else if (_mode === "event") loadEvent(currentEventId)
        else if (_mode === "folder") loadFolder(_filterValue)
        else if (_mode === "dir") loadDir(_filterValue)
        else if (_mode === "person") loadPerson(_filterValue)
        else if (_mode === "location") loadLocation(_filterLat, _filterLon)
        else if (_mode === "device") loadDevice(_filterValue)
        else if (_mode === "tag") loadTag(_filterValue)
        else if (_mode === "month") loadDateMonth(_filterValue)
        else if (_mode === "day") loadDateDay(_filterValue)
        else if (_mode === "rated") loadRated(_filterValue)
        else if (_mode === "flag") loadFlag(_filterValue)
        else if (_mode === "stacks") loadStacks()
        else if (_mode === "album") loadAlbum(_filterValue, pageTitle.slice(3))
        else if (_mode === "similar") loadSimilar()
        else if (_mode === "facesearch") loadFaceSearch()
        else search(pageTitle.slice(3))
    }

    function clearSelection() {
        _clearAllSelections()
        selectedIds = []
    }

    function exportSelected(folder) {
        if (selectedIds.length === 0) return 0
        var n = LibraryBridge.exportPhotos(selectedIds, folder)
        return n
    }

    /* 0.5.38：按格式/分辨率导出 */
    function exportSelectedEx(folder, fmt, resKey) {
        if (selectedIds.length === 0) return 0
        return LibraryBridge.exportProcessed(selectedIds, folder, fmt, resKey)
    }

    function moveOutSelected(folder) {
        if (selectedIds.length === 0) return 0
        return LibraryBridge.moveOut(selectedIds, folder)
    }

    function selectAllLoaded() {
        var models = _inGroupMode() ? _visibleCellModels() : [gridModel]
        var sel = []
        for (var m = 0; m < models.length; ++m)
            for (var i = 0; i < models[m].count; ++i) {
                if (models[m].get(i).type) continue
                models[m].setProperty(i, "selected", true)
                sel.push(models[m].get(i).id)
            }
        selectedIds = sel
    }

    /* 0.5.52：反选——把当前已加载列表里的选中/未选中状态整体翻转
       （与「全选」同口径：只作用于已加载的照片，滚动加载更多后对新加载项无效） */
    function invertSelection() {
        var models = _inGroupMode() ? _visibleCellModels() : [gridModel]
        var sel = []
        for (var m = 0; m < models.length; ++m)
            for (var i = 0; i < models[m].count; ++i) {
                if (models[m].get(i).type) continue
                var on = !models[m].get(i).selected
                models[m].setProperty(i, "selected", on)
                if (on) sel.push(models[m].get(i).id)
            }
        selectedIds = sel
    }

    /* ---------- 0.5.53：文件夹分组（排序=文件夹/路径 时） ---------- */

    /* 折叠状态：dirKey -> {rows:[成员行]}（整体替换触发绑定，勿就地改） */
    property var collapsedFolders: ({})
    /* 增量加载时的上一个分组目录（同目录跨批次不重复插组头） */
    property string _lastGroupDir: ""
    /* 0.5.55：分组视图独立开关（与排序解耦；仅"全部照片"视图生效） */
    property bool groupMode: LibraryBridge ? LibraryBridge.galleryGroupView() : false

    function toggleGroupMode() {
        groupMode = !groupMode
        if (LibraryBridge) LibraryBridge.setGalleryGroupView(groupMode)
        if (_mode === "all") loadAll()
        else reloadCurrent()
    }

    /* 0.5.64：窗口宽度变化不再需要重建——分段 Flow 自适应重排 */

    function _dirOf(p) {
        if (!p) return ""
        var s = String(p).replace(/\\/g, "/")
        var i = s.lastIndexOf("/")
        return i > 0 ? s.substring(0, i) : s
    }

    /* ---------- 0.5.64 分组模式分段重构：辅助函数 ---------- */

    function _inGroupMode() {
        return root.groupMode && root._mode === "all" && !root.stackMode
    }

    /* 圈选/落点的坐标系：平铺=gridView，分组=groupList */
    function _viewportItem() {
        return _inGroupMode() ? groupList : gridView
    }

    /* 0.5.66：打开内嵌视频播放器（懒加载；QtMultimedia 不可用时回退系统播放器） */
    function _openVideo(path) {
        videoPlayerLoader.active = true
        if (videoPlayerLoader.item)
            videoPlayerLoader.item.openVideo(path)
        else if (LibraryBridge)
            LibraryBridge.openExternal(path)
    }

    function _groupStoreIndexOf(dir) {
        for (var g = 0; g < _groupStore.length; ++g)
            if (_groupStore[g].dir === dir) return g
        return -1
    }

    function _groupModelOf(dir) {
        var g = _groupStoreIndexOf(dir)
        return g >= 0 ? _groupStore[g].model : null
    }

    /* 可见格子的模型清单（折叠组隐藏其成员，选择类操作均只作用于可见格） */
    function _visibleCellModels() {
        var out = []
        for (var g = 0; g < _groupStore.length; ++g)
            if (!collapsedFolders[_groupStore[g].dir])
                out.push(_groupStore[g].model)
        return out
    }

    /* 全部组模型（含折叠组；refreshMeta 等数据更新用） */
    function _allGroupModels() {
        var out = []
        for (var g = 0; g < _groupStore.length; ++g)
            out.push(_groupStore[g].model)
        return out
    }

    function _clearAllSelections() {
        var models = _inGroupMode() ? _visibleCellModels() : [gridModel]
        for (var m = 0; m < models.length; ++m)
            for (var i = 0; i < models[m].count; ++i)
                models[m].setProperty(i, "selected", false)
    }

    function _syncSelectedIds() {
        var models = _inGroupMode() ? _visibleCellModels() : [gridModel]
        var sel = []
        for (var m = 0; m < models.length; ++m)
            for (var i = 0; i < models[m].count; ++i) {
                var d = models[m].get(i)
                if (d.selected && !d.type) sel.push(d.id)
            }
        root.selectedIds = sel
    }

    function _visibleCellRefs() {
        var models = _inGroupMode() ? _visibleCellModels() : [gridModel]
        var out = []
        for (var m = 0; m < models.length; ++m)
            for (var i = 0; i < models[m].count; ++i)
                out.push({ m: models[m], i: i, id: models[m].get(i).id })
        return out
    }

    function _visibleIndexOfPid(pid) {
        var refs = _visibleCellRefs()
        for (var i = 0; i < refs.length; ++i)
            if (refs[i].id === pid) return i
        return -1
    }

    function _setSelectedByPid(pid, val) {
        var refs = _visibleCellRefs()
        for (var i = 0; i < refs.length; ++i)
            if (refs[i].id === pid) {
                refs[i].m.setProperty(refs[i].i, "selected", val)
                return
            }
    }

    /* 卡片点击选择（Shift 范围 / Ctrl 切换 / 普通单选），两种模式共用 */
    function _cellClicked(pid, mods) {
        var refs = _visibleCellRefs()
        var cur = -1
        for (var i = 0; i < refs.length; ++i)
            if (refs[i].id === pid) { cur = i; break }
        if (cur < 0) return
        if ((mods & Qt.ShiftModifier) && root._anchorIndex >= 0) {
            var a = Math.min(root._anchorIndex, cur)
            var b = Math.max(root._anchorIndex, cur)
            for (var k = 0; k < refs.length; ++k)
                refs[k].m.setProperty(refs[k].i, "selected", k >= a && k <= b)
        } else if (mods & Qt.ControlModifier) {
            var t = !refs[cur].m.get(refs[cur].i).selected
            refs[cur].m.setProperty(refs[cur].i, "selected", t)
            root._anchorIndex = cur
        } else {
            for (var j = 0; j < refs.length; ++j)
                if (j !== cur && refs[j].m.get(refs[j].i).selected)
                    refs[j].m.setProperty(refs[j].i, "selected", false)
            var c2 = refs[cur].m.get(refs[cur].i).selected
            refs[cur].m.setProperty(refs[cur].i, "selected", !c2)
            root._anchorIndex = cur
        }
        _syncSelectedIds()
    }

    /* 折叠/展开某文件夹组：0.5.64 分段重构后仅切换 UI 状态——
       成员始终留在组模型里（折叠=Flow 隐藏），不再搬行/补占位格 */
    function toggleFolderGroup(dir) {
        var nf = {}
        for (var k in collapsedFolders) nf[k] = collapsedFolders[k]
        if (nf[dir])
            delete nf[dir]
        else
            nf[dir] = { rows: [] }
        collapsedFolders = nf
    }


    /* 大图查看器上下文：可见照片 id 序列 + 指定照片的位置（0.5.64 按 id 定位，
       两种模式共用；折叠组成员不进序列，与显示一致） */
    function viewerContextForId(pid) {
        var refs = _visibleCellRefs()
        var ids = []
        var idx = -1
        for (var i = 0; i < refs.length; ++i) {
            if (refs[i].id === pid) idx = ids.length
            ids.push(refs[i].id)
        }
        return [ids, idx]
    }

    /* 平铺模式旧入口（按模型下标）：保留给既有调用方 */
    function viewerContext(index) {
        var ids = []
        var idx = 0
        for (var i = 0; i < gridModel.count; ++i) {
            var d = gridModel.get(i)
            if (d.type) continue
            if (i === index) idx = ids.length
            ids.push(d.id)
        }
        return [ids, idx]
    }

    function firstSelectedIndex() {
        for (var i = 0; i < gridModel.count; ++i)
            if (gridModel.get(i).selected) return i
        return -1
    }

    function openContextAt(index) {
        if (index < 0) return
        if (gridModel.get(index) && gridModel.get(index).type) return
        var vc = viewerContext(index)
        root.photoContextRequested(vc[0], vc[1])
    }

    function selectedPathsText() {
        var arr = []
        for (var i = 0; i < selectedIds.length; ++i) {
            var d = LibraryBridge.photoDetail(selectedIds[i])
            if (d && d.path) arr.push(d.path)
        }
        return arr.join("\n")
    }

    ListModel { id: gridModel }
    /* 0.5.64 分组模式：外层分段模型（dir 唯一；成员在各组的 ListModel 里） */
    ListModel { id: groupSectionsModel }
                /* 0.5.64：照片卡片组件——平铺 GridView 与分组 Flow 共用。
                   model 角色两处一致（同一份 _pack 字段 + selected）；
                   坐标一律 mapToItem(root._viewport)（两种模式的滚动容器不同）。 */
                Component {
                    id: photoCell
                    Item {
                        id: cellRoot
                        width: root.cellSize
                        height: root.cellSize
                        /* 分组模式的圈选注册表（平铺模式走索引反算，不注册） */
                        property int thePid: model.id
                        Component.onCompleted: if (root._inGroupMode())
                            root._cellRegistry.push(cellRoot)
                        Component.onDestruction: {
                            var ri = root._cellRegistry.indexOf(cellRoot)
                            if (ri >= 0) root._cellRegistry.splice(ri, 1)
                        }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 4
                    radius: Theme.radiusMedium
                    /* 组头/占位行不渲染照片卡片 */
                    visible: !model.type
                    color: model.selected ? Theme.primary : Theme.bg
                    border.width: model.selected ? 3 : 1
                    border.color: model.selected ? Theme.primary : Theme.divider
                    clip: true

                    /* 照片内容（组头/占位行隐藏） */
                    Item {
                        anchors.fill: parent
                        visible: !model.type

                    Image {
                        id: thumb
                        anchors.fill: parent
                        anchors.margins: 2
                        fillMode: Image.PreserveAspectCrop
                        source: model.thumb || ""
                        asynchronous: true
                        cache: true
                        smooth: false
                        visible: status === Image.Ready
                    }
                    /* 选中着色层：让整格状态一眼可辨（照片仍可预览） */
                    Rectangle {
                        anchors.fill: parent
                        color: Theme.primary
                        opacity: 0.14
                        visible: model.selected
                    }
                    /* 白色内圈：在深色照片上也看得清边框 */
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 3
                        radius: Theme.radiusSmall
                        color: "transparent"
                        border.width: 1
                        border.color: "#FFFFFF"
                        opacity: 0.9
                        visible: model.selected
                    }
                    /* 左上角勾选徽标 */
                    Rectangle {
                        visible: model.selected
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.margins: 5
                        width: 20
                        height: 20
                        radius: 10
                        color: Theme.primary
                        border.width: 2
                        border.color: "white"
                        Text {
                            anchors.centerIn: parent
                            text: "✓"
                            font.pixelSize: 12
                            font.weight: Font.Bold
                            color: "white"
                        }
                    }
                    /* 0.5.44 视频：左下角 ▶ + 时长徽标（纯覆盖层，不影响点选/圈选） */
                    Rectangle {
                        visible: model.mediaType === "video"
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.margins: 5
                        height: 18
                        width: vidDurRow.implicitWidth + 12
                        radius: 9
                        color: "#CC000000"
                        Row {
                            id: vidDurRow
                            anchors.centerIn: parent
                            spacing: 3
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "▶"
                                font.pixelSize: 9
                                color: "white"
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: {
                                    var s = model.duration
                                    if (!s || s <= 0) return ""
                                    var t = Math.floor(s)
                                    var h = Math.floor(t / 3600)
                                    var m = Math.floor((t % 3600) / 60)
                                    var ss = t % 60
                                    var mm = (m < 10 ? "0" : "") + m
                                    var sss = (ss < 10 ? "0" : "") + ss
                                    return h > 0 ? (h + ":" + mm + ":" + sss) : (m + ":" + sss)
                                }
                                font.pixelSize: 10
                                color: "white"
                            }
                        }
                    }
                    Rectangle {
                        anchors.fill: parent
                        color: Theme.surfaceAlt
                        visible: thumb.status !== Image.Ready
                        Text {
                            anchors.centerIn: parent
                            text: model.faceCount > 0 ? "👤×" + model.faceCount : "?"
                            font.pixelSize: 20
                            color: Theme.textDim
                        }
                    }
                    Rectangle {
                        visible: model.faceCount > 0
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.margins: 6
                        /* 0.5.36：选中时下移避让勾选徽标 */
                        anchors.topMargin: model.selected ? 29 : 6
                        width: 26
                        height: 18
                        radius: 9
                        color: Theme.accent
                        Text {
                            anchors.centerIn: parent
                            text: "👤" + model.faceCount
                            font.pixelSize: 10
                            color: "white"
                        }
                    }
                    Rectangle {
                        visible: model.hasText
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        width: 18
                        height: 18
                        radius: 4
                        color: Theme.primary
                        Text {
                            anchors.centerIn: parent
                            text: I18n.tr("文")
                            font.pixelSize: 10
                            color: "white"
                        }
                    }
                    /* 0.5.64：损坏文件标记（右上角 ⚠，旗标徽标下移避让）。
                       photos.decode_error 由查看时 make_preview 兜底路径或
                       完整性I18n.tr("深度解码检查")写入。 */
                    Rectangle {
                        visible: model.decodeError === true
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        width: 18
                        height: 18
                        radius: 9
                        color: "#e65100"
                        ToolTip.visible: decHover.hovered
                        ToolTip.delay: 550
                        ToolTip.text: I18n.tr("文件数据不完整（可能传输中断/损坏），预览为相机内嵌图")
                        HoverHandler { id: decHover }
                        Text {
                            anchors.centerIn: parent
                            text: "⚠"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "white"
                        }
                    }
                    Rectangle {
                        visible: model.flag === "pick"
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        anchors.topMargin: model.decodeError === true ? 26 : 6
                        width: 22
                        height: 18
                        radius: 9
                        color: "#2e7d32"
                        Text {
                            anchors.centerIn: parent
                            text: "✓"
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            color: "white"
                        }
                    }
                    Rectangle {
                        visible: model.flag === "reject"
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.margins: 6
                        anchors.topMargin: model.decodeError === true ? 26 : 6
                        width: 22
                        height: 18
                        radius: 9
                        color: "#b71c1c"
                        Text {
                            anchors.centerIn: parent
                            text: "✕"
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            color: "white"
                        }
                    }
                    Text {
                        visible: model.rating > 0
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.margins: 6
                        text: "★".repeat(model.rating)
                        font.pixelSize: 11
                        color: "#f5c842"
                        style: Text.Outline
                        styleColor: "black"
                    }
                    Rectangle {
                        visible: (model.stackCount || 0) > 1
                        anchors.bottom: parent.bottom
                        anchors.right: parent.right
                        anchors.margins: 6
                        width: 30
                        height: 18
                        radius: 9
                        color: Theme.primary
                        Text {
                            anchors.centerIn: parent
                            text: "▦" + model.stackCount
                            font.pixelSize: 10
                            color: "white"
                        }
                    }
                    /* 色标圆点（左上角，人脸徽标下方） */
                    Rectangle {
                        visible: (model.colorLabel || "") !== ""
                        anchors.top: parent.top
                        anchors.left: parent.left
                        anchors.margins: 6
                        anchors.topMargin: (model.selected ? 29 : 6) + (model.faceCount > 0 ? 21 : 0)
                        width: 12
                        height: 12
                        radius: 6
                        border.width: 1
                        border.color: "white"
                        color: model.colorLabel === "red" ? "#e53935"
                             : model.colorLabel === "yellow" ? "#fdd835"
                             : model.colorLabel === "green" ? "#43a047"
                             : model.colorLabel === "blue" ? "#1e88e5"
                             : model.colorLabel === "purple" ? "#8e24aa"
                             : "transparent"
                    }
                    Text {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.margins: 6
                        text: (model.takenAt || "").slice(5) + "  " + model.name
                        font.family: Theme.fontFamily
                        font.pixelSize: 9
                        color: "white"
                        elide: Text.ElideMiddle
                        style: Text.Outline
                        styleColor: "black"
                    }
                    } /* photoContent 结束 */
                }

                /* 0.5.64：组头条已上移到外层分段 delegate（组头行 32px）；卡片只画照片 */

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    /* 0.5.67：圈选拖动激活期间阻止 Flickable 抢占鼠标
                       （否则拖出格子范围后被视图滚动接管，圈选失效） */
                    preventStealing: root._rubberActive
                    /* 0.5.63：组头/占位行禁用本 MouseArea——点击穿透到
                       组头条的全宽 MouseArea（整行可点折叠/展开），
                       不再被占位格吞掉（此前只有第一格可点） */
                    enabled: !model.type
                    onPressed: (mouse) => {
                        if (mouse.button === Qt.LeftButton) {
                            root._pressPos = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                            root._cellLeftPressed = true
                            root._suppressClick = false
                        }
                        /* 右键：选中该项（保留单选语义）并弹出上下文菜单
                           （0.5.64：选择操作改走按 id 的模式无关助手） */
                        if (mouse.button === Qt.RightButton) {
                            if (!model.selected) {
                                root._clearAllSelections()
                                root._setSelectedByPid(model.id, true)
                                root._anchorIndex = root._visibleIndexOfPid(model.id)
                                root._syncSelectedIds()
                            }
                            var gp = mapToGlobal(mouse.x, mouse.y)
                            root.contextMenuRequested(gp.x, gp.y)
                            mouse.accepted = true
                        }
                    }
                    onPositionChanged: (mouse) => {
                        /* 0.5.30：左键拖动超过 8px 启动圈选（普通拖=重选，Ctrl/Shift+拖=追加） */
                        if (!root._cellLeftPressed || !(mouse.buttons & Qt.LeftButton))
                            return
                        var p = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                        var dx = p.x - root._pressPos.x, dy = p.y - root._pressPos.y
                        if (!root._rubberActive && dx * dx + dy * dy > 64) {
                            root._rubberActive = true
                            root._rubberMode = (mouse.modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
                                               ? "add" : "replace"
                            root._rubberBaseSel = root.selectedIds.slice()
                            root._rubberStart = root._pressPos
                        }
                        if (root._rubberActive)
                            root._rubberCur = p
                    }
                    onReleased: (mouse) => {
                        if (root._rubberActive) {
                            root._finishRubber()
                            root._rubberActive = false
                            /* 圈选结束的 release 不再触发单击选择 */
                            root._suppressClick = true
                            root._cellLeftPressed = false
                            mouse.accepted = true
                        }
                    }
                    onClicked: (mouse) => {
                        if (mouse.button !== Qt.LeftButton)
                            return
                        if (root._suppressClick) {
                            root._suppressClick = false
                            return
                        }
                        /* 堆叠代表帧：普通点击展开成员弹层；带 Shift/Ctrl 仍走选择逻辑 */
                        if ((model.stackCount || 0) > 1
                            && !(mouse.modifiers & (Qt.ShiftModifier | Qt.ControlModifier))) {
                            stackPopup.openFor(model.stackId, model.name)
                            return
                        }
                        /* 0.5.64：Shift 范围 / Ctrl 切换 / 普通单选统一在根部处理 */
                        root._cellClicked(model.id, mouse.modifiers)
                        if (root.selectedIds.length > 0) {
                            root.photoClicked(model.id)
                            /* 通知大图查看器：当前可见照片序列 + 点击位置 */
                            var vc = root.viewerContextForId(model.id)
                            root.photoContextRequested(vc[0], vc[1])
                        }
                        /* 0.6.3：再次点击已选照片=取消选择，但信息栏不再清空——
                           此前发 photoClicked(-1) 把面板整个重置（currentId=-1），
                           评级/标签/场景等按钮随之全部失效（用户反馈"信息栏
                           按钮都失效、场景不显示"）。保留最后浏览的照片详情，
                           显式点空白处才会清空。 */
                    }
                    onDoubleClicked: (mouse) => {
                        if (mouse.button === Qt.LeftButton
                            && model.mediaType === "video")
                            root._openVideo(model.path)
                    }
                }
                    }
                }


    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            leftPadding: Theme.spacingMedium
            rightPadding: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PMButton {
                objectName: "galleryBackBtn"
                tooltip: I18n.tr("返回上一个浏览入口（事件/文件夹/人物/搜索结果等）")
                text: I18n.tr("‹ 返回")
                width: 68
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                visible: root._mode !== "all"
                onClicked: root.backRequested()
            }
            Text {
                id: titleText
                text: root.pageTitle
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.text
                elide: Text.ElideMiddle
                Layout.maximumWidth: 520
            }
            Text {
                id: countText
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
            }
            /* 0.5.67：人物页专属——批量分拆人脸（归为新人物/并入其他人物） */
            PMButton {
                objectName: "personFacesManageBtn"
                text: I18n.tr("管理头像")
                height: 30
                anchors.verticalCenter: parent.verticalCenter
                visible: root._mode === "person"
                tooltip: I18n.tr("列出该人物的全部头像，勾选后可拆分到新人物或其他人物")
                onClicked: root.personFacesRequested(root._filterValue)
            }
            Item { Layout.fillWidth: true; width: 10 }
            Text {
                text: root.selectedIds.length > 0 ? I18n.tr("已选 ") + root.selectedIds.length + I18n.tr(" 张") : ""
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.primary
            }
        }

        /* 快速筛选条：全部 / 精选 / 已评级 */
        Row {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: 4
            spacing: 6

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.tr("筛选：")
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textDim
            }
            Repeater {
                model: [
                    {"label": I18n.tr("全部"), "mode": "all", "tip": I18n.tr("显示全部未作废的照片")},
                    {"label": I18n.tr("精选 ✓"), "mode": "pick", "tip": I18n.tr("只显示打了「精选」旗标的照片")},
                    {"label": I18n.tr("排除 ✕"), "mode": "reject", "tip": I18n.tr("只显示打了「排除」旗标的照片（筛选候选）")},
                    {"label": I18n.tr("已评级 ★"), "mode": "rated", "tip": I18n.tr("只显示评过星的照片（≥1★）")}
                ]
                delegate: Rectangle {
                    id: chip
                    width: chipText.implicitWidth + 18
                    height: 24
                    radius: 12
                    color: (_mode === modelData.mode || (modelData.mode === "all" && _mode === "all"))
                            ? Theme.primary : Theme.surfaceAlt
                    border.width: 1
                    border.color: Theme.divider
                    Text {
                        id: chipText
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: Theme.fontFamily
                        font.pixelSize: 11
                        color: chip.color === Theme.primary ? "white" : Theme.text
                    }
                    MouseArea {
                        id: chipArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (modelData.mode === "all") root.loadAll()
                            else if (modelData.mode === "pick") root.loadFlag("pick")
                            else if (modelData.mode === "reject") root.loadFlag("reject")
                            else root.loadRated(1)
                        }
                    }
                    ToolTip.visible: chipArea.containsMouse
                    ToolTip.delay: 550
                    ToolTip.text: modelData.tip
                }
            }
            Item { width: 12 }
            PMButton {
                objectName: "stackToggleBtn"
                tooltip: I18n.tr("连拍组按栈合并显示，每栈只显示代表帧，点击栈展开成员")
                text: root.stackMode ? I18n.tr("堆叠视图 ✓") : I18n.tr("堆叠视图")
                width: 96
                height: 24
                anchors.verticalCenter: parent.verticalCenter
                onClicked: {
                    if (root.stackMode) { root.stackMode = false; root.loadAll() }
                    else root.loadStacks()
                }
            }
            Item { width: 6 }
            /* 0.5.55：分组视图独立开关（与堆叠视图同型；仅全部照片视图生效） */
            PMButton {
                objectName: "groupToggleBtn"
                tooltip: I18n.tr("分组视图：全部照片按文件夹分组显示，点组头可折叠/展开（0.5.55；\n与排序解耦——排序保持原样，开关状态会记住）")
                text: root.groupMode ? I18n.tr("分组视图 ✓") : I18n.tr("分组视图")
                width: 96
                height: 24
                anchors.verticalCenter: parent.verticalCenter
                onClicked: root.toggleGroupMode()
            }
            Item { width: 6 }
            /* 0.5.36：排序选择（默认折叠，点击展开菜单） */
            PMButton {
                objectName: "sortToggleBtn"
                tooltip: I18n.tr("选择缩略图排列顺序：时间、文件名、文件夹、相机、评级、大小")
                text: I18n.tr("排序：▸ ") + root._sortLabel(root.sortKey)
                height: 24
                anchors.verticalCenter: parent.verticalCenter
                onClicked: sortMenu.popup(this, 0, height + 2)
                Menu {
                    id: sortMenu
                    objectName: "sortMenu"
                    width: 180
                    Repeater {
                        model: root._sortLabels
                        delegate: MenuItem {
                            required property var modelData
                            text: modelData.label
                            checkable: true
                            checked: root.sortKey === modelData.key
                            onTriggered: root._applySort(modelData.key)
                        }
                    }
                }
            }
        }

        /* 批量操作条：0.5.67 改为固定显示（用户反馈：不选择也应可见）。
           0.5.36 改 Flow 自适应换行，窗口缩小时按钮折到下一行而不是被截断 */
        Rectangle {
            objectName: "batchBar"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(42, batchFlow.implicitHeight + 14)
            Layout.leftMargin: Theme.spacingMedium
            Layout.rightMargin: Theme.spacingMedium
            Layout.bottomMargin: Theme.spacingSmall
            radius: Theme.radiusMedium
            color: root.selectedIds.length > 0 ? Theme.primary : Theme.surfaceAlt
            opacity: 0.95

            Flow {
                id: batchFlow
                anchors.fill: parent
                anchors.margins: 7
                spacing: Theme.spacingSmall

                Text {
                    text: root.selectedIds.length > 0
                          ? I18n.tr("已选 ") + root.selectedIds.length + I18n.tr(" 张")
                          : I18n.tr("未选择照片")
                    height: 30
                    verticalAlignment: Text.AlignVCenter
                    rightPadding: 4
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: "white"
                }
                PMButton {
                    objectName: "batchTagBtn"
                    tooltip: I18n.tr("给所选照片批量添加标签")
                    text: I18n.tr("打标签…")
                    height: 30
                    onClicked: root.batchTagRequested()
                }
                PMButton {
                    objectName: "batchExportBtn"
                    tooltip: I18n.tr("把所选照片导出到文件夹，可选格式（原始/JPG/PNG/WebP/TIFF）与分辨率")
                    text: I18n.tr("导出…")
                    height: 30
                    onClicked: root.batchExportRequested()
                }
                PMButton {
                    objectName: "batchMoveOutBtn"
                    tooltip: I18n.tr("把所选照片移出到指定文件夹并从索引清除（文件不删除，可重新导入）")
                    text: I18n.tr("移出…")
                    height: 30
                    onClicked: root.batchMoveOutRequested()
                }
                PMButton {
                    objectName: "batchPersonMoveBtn"
                    tooltip: I18n.tr("把所选照片从当前人物移出（人脸归属改回未命名）")
                    text: I18n.tr("移出人物…")
                    visible: root._mode === "person"
                    height: 30
                    onClicked: root.moveOutOfPersonRequested()
                }
                PMButton {
                    objectName: "batchCopyBtn"
                    tooltip: I18n.tr("把所选照片的完整文件路径复制到剪贴板")
                    text: I18n.tr("复制路径")
                    height: 30
                    onClicked: root.batchCopyRequested(root.selectedPathsText())
                }
                PMButton {
                    objectName: "batchSelectAllBtn"
                    tooltip: I18n.tr("选中当前已加载的全部照片（继续滚动会加载更多）")
                    text: I18n.tr("全选")
                    height: 30
                    onClicked: root.selectAllLoaded()
                }
                PMButton {
                    objectName: "batchInvertBtn"
                    tooltip: I18n.tr("反选：取消已选中的，选中当前列表里其余未选中的（0.5.52）")
                    text: I18n.tr("反选")
                    height: 30
                    onClicked: root.invertSelection()
                }
                PMButton {
                    objectName: "batchClearBtn"
                    tooltip: I18n.tr("取消当前所有选中")
                    text: I18n.tr("取消选择")
                    height: 30
                    onClicked: root.clearSelection()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingSmall

            /* 照片网格：平铺（非分组）走 GridView；分组走下方分段 ListView */
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.surface
                radius: Theme.radiusLarge
                border.width: 1
                border.color: Theme.divider

                GridView {
                id: gridView
                objectName: "galleryGrid"
                anchors.fill: parent
                anchors.margins: Theme.spacingMedium
                visible: !root._inGroupMode()
                model: gridModel
                cellWidth: root.cellSize
                cellHeight: root.cellSize
                clip: true
                cacheBuffer: 2000
                focus: true
                /* 0.5.67：禁用拖动平移（用户要求：空白拖动留给圈选，滚轮/滚动条滚动）。
                   interactive:false 后滚轮不再由 Flickable 内建处理，显式加 WheelHandler。 */
                interactive: false

                WheelHandler {
                    acceptedModifiers: Qt.NoModifier
                    onWheel: (ev) => {
                        var step = ev.angleDelta.y / 120 * root.cellSize * 2
                        gridView.contentY = Math.max(
                            -gridView.topMargin,
                            Math.min(gridView.contentHeight - gridView.height + gridView.bottomMargin,
                                     gridView.contentY - step))
                        ev.accepted = true
                    }
                }

                /* interactive:false 后程序化滚动不触发 movementEnded，改在 contentY 变化时补加载 */
                onContentYChanged: {
                    if (contentY + height > contentHeight - root.cellSize * 3)
                        root._fetchMore()
                }
                /* 0.5.57：资源管理器风格分组——组头横跨整行（GridView section）。
                   折叠组用I18n.tr("哨兵行")占位（该组唯一行，delegate 渲染为透明），
                   其 section 头显示折叠态；展开组直接由成员行产生 section 头。 */
                /* 0.5.57：资源管理器风格分组——组头行独占一整行（组头+占位格），
                   组头条 delegate 溢出绘制横跨整行；点击组头折叠/展开。 */
                onMovementEnded: {
                    if (contentY + height > contentHeight - cellHeight * 3)
                        root._fetchMore()
                }

                /* 0.5.67：空白处起圈选——此前只能从格子上起拖（缩略图间隙/
                   空白区域按下拖动无反应，用户反馈）。preventStealing 让
                   圈选拖动不被 Flickable 抢走变成滚动；滚轮/滚动条不受影响。
                   z: -1 压到 delegate 层之下——否则会盖住格子吞掉单击
                   （0.5.67 第二次真机反馈的回归）；空白单击 = 取消选择。 */
                MouseArea {
                    anchors.fill: parent
                    z: -1
                    preventStealing: true
                    acceptedButtons: Qt.LeftButton
                    onPressed: (mouse) => {
                        root._pressPos = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                        root._cellLeftPressed = true
                        root._suppressClick = false
                        root._rubberBaseSel = root.selectedIds.slice()
                    }
                    onPositionChanged: (mouse) => {
                        if (!root._cellLeftPressed || !(mouse.buttons & Qt.LeftButton))
                            return
                        var p = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                        var dx = p.x - root._pressPos.x, dy = p.y - root._pressPos.y
                        if (!root._rubberActive && dx * dx + dy * dy > 64) {
                            root._rubberActive = true
                            root._rubberMode = (mouse.modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
                                               ? "add" : "replace"
                            root._rubberStart = root._pressPos
                        }
                        if (root._rubberActive)
                            root._rubberCur = p
                    }
                    onReleased: (mouse) => {
                        if (root._rubberActive) {
                            root._finishRubber()
                            root._rubberActive = false
                            root._cellLeftPressed = false
                            mouse.accepted = true
                        }
                    }
                    onClicked: (mouse) => {
                        /* 空白处单击（未拖出圈选）= 取消全部选择 */
                        if (root._suppressClick) {
                            root._suppressClick = false
                            return
                        }
                        root._clearAllSelections()
                        root.selectedIds = []
                        root.photoClicked(-1)
                    }
                }

                ScrollBar.vertical: PMScrollBar {
                    objectName: "galleryScroll"
                    policy: ScrollBar.AlwaysOn
                    visible: gridView.contentHeight > gridView.height
                }

                /* Ctrl+滚轮缩放缩略图（0.5.31）：普通滚轮仍为垂直滚动 */
                WheelHandler {
                    acceptedModifiers: Qt.ControlModifier
                    blocking: true
                    onWheel: (ev) => {
                        if (!ThemeController)
                            return
                        var v = ThemeController.thumbSize + (ev.angleDelta.y > 0 ? 10 : -10)
                        ThemeController.thumbSize = Math.max(110, Math.min(340, v))
                        ev.accepted = true
                    }
                }

                /* 拖动圈选矩形（0.5.30）：GridView 直接子项 = 视口覆盖层，不随内容滚动 */
                Rectangle {
                    id: rubberBand
                    visible: root._rubberActive
                    x: Math.min(root._rubberStart.x, root._rubberCur.x)
                    y: Math.min(root._rubberStart.y, root._rubberCur.y)
                    width: Math.abs(root._rubberCur.x - root._rubberStart.x)
                    height: Math.abs(root._rubberCur.y - root._rubberStart.y)
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.primary

                    Rectangle {
                        anchors.fill: parent
                        color: Theme.primary
                        opacity: 0.15
                    }
                }

                delegate: photoCell
            }

                /* 0.5.64 分组模式：外层分段列表——每组 = 32px 组头行 + Flow 照片网格。
                   成员留在各组 ListModel 里，折叠仅隐藏 Flow，彻底消除原
                   「组头独占整格」方案的上下空白带（用户反馈问题③）。 */
                ListView {
                    id: groupList
                    objectName: "galleryGroupList"
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMedium
                    visible: root._inGroupMode()
                    clip: true
                    cacheBuffer: 2000
                    model: groupSectionsModel
                    spacing: 10
                    /* 0.5.67：禁用拖动平移（同平铺模式） */
                    interactive: false

                    WheelHandler {
                        acceptedModifiers: Qt.NoModifier
                        onWheel: (ev) => {
                            var step = ev.angleDelta.y / 120 * root.cellSize * 2
                            groupList.contentY = Math.max(
                                -groupList.topMargin,
                                Math.min(groupList.contentHeight - groupList.height + groupList.bottomMargin,
                                         groupList.contentY - step))
                            ev.accepted = true
                        }
                    }

                    onContentYChanged: {
                        if (contentY + height > contentHeight - root.cellSize * 3)
                            root._fetchMore()
                    }

                    onMovementEnded: {
                        if (contentY + height > contentHeight - root.cellSize * 3)
                            root._fetchMore()
                    }

                    /* 0.5.67：空白处起圈选（与平铺模式一致）；z:-1 压到 delegate 之下，
                       空白单击 = 取消选择 */
                    MouseArea {
                        anchors.fill: parent
                        z: -1
                        preventStealing: true
                        acceptedButtons: Qt.LeftButton
                        onPressed: (mouse) => {
                            root._pressPos = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                            root._cellLeftPressed = true
                            root._suppressClick = false
                            root._rubberBaseSel = root.selectedIds.slice()
                        }
                        onPositionChanged: (mouse) => {
                            if (!root._cellLeftPressed || !(mouse.buttons & Qt.LeftButton))
                                return
                            var p = mapToItem(root._viewportItem(), mouse.x, mouse.y)
                            var dx = p.x - root._pressPos.x, dy = p.y - root._pressPos.y
                            if (!root._rubberActive && dx * dx + dy * dy > 64) {
                                root._rubberActive = true
                                root._rubberMode = (mouse.modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
                                                   ? "add" : "replace"
                                root._rubberStart = root._pressPos
                            }
                            if (root._rubberActive)
                                root._rubberCur = p
                        }
                        onReleased: (mouse) => {
                            if (root._rubberActive) {
                                root._finishRubber()
                                root._rubberActive = false
                                root._cellLeftPressed = false
                                mouse.accepted = true
                            }
                        }
                        onClicked: (mouse) => {
                            if (root._suppressClick) {
                                root._suppressClick = false
                                return
                            }
                            root._clearAllSelections()
                            root.selectedIds = []
                            root.photoClicked(-1)
                        }
                    }
                    onAtYEndChanged: {
                        if (atYEnd && root._loaded < root.totalCount)
                            root._fetchMore()
                    }

                    ScrollBar.vertical: PMScrollBar {
                        objectName: "galleryGroupScroll"
                        policy: ScrollBar.AlwaysOn
                        visible: groupList.contentHeight > groupList.height
                    }

                    /* Ctrl+滚轮缩放缩略图（与平铺模式一致） */
                    WheelHandler {
                        acceptedModifiers: Qt.ControlModifier
                        blocking: true
                        onWheel: (ev) => {
                            if (!ThemeController)
                                return
                            var v = ThemeController.thumbSize + (ev.angleDelta.y > 0 ? 10 : -10)
                            ThemeController.thumbSize = Math.max(110, Math.min(340, v))
                            ev.accepted = true
                        }
                    }

                    /* 拖动圈选矩形覆盖层（与平铺模式共用 root 手势状态） */
                    Rectangle {
                        id: rubberBandGroup
                        visible: root._rubberActive
                        x: Math.min(root._rubberStart.x, root._rubberCur.x)
                        y: Math.min(root._rubberStart.y, root._rubberCur.y)
                        width: Math.abs(root._rubberCur.x - root._rubberStart.x)
                        height: Math.abs(root._rubberCur.y - root._rubberStart.y)
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.primary

                        Rectangle {
                            anchors.fill: parent
                            color: Theme.primary
                            opacity: 0.15
                        }
                    }

                    delegate: Column {
                        id: grpCol
                        required property string dir
                        required property string name
                        readonly property var gm: root._groupModelOf(dir)
                        width: groupList.width
                        spacing: 0

                        /* 组头行 32px（资源管理器式，整行可点折叠/展开） */
                        Rectangle {
                            width: parent.width
                            height: 32
                            color: hdrHover.hovered ? Theme.surfaceAlt : Theme.bg
                            radius: Theme.radiusSmall
                            border.width: 1
                            border.color: Theme.divider
                            HoverHandler { id: hdrHover }
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                spacing: 6
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: root.collapsedFolders[grpCol.dir] ? "▸" : "▾"
                                    font.pixelSize: 10
                                    color: Theme.textDim
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: grpCol.name
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    color: Theme.text
                                    elide: Text.ElideMiddle
                                    width: Math.min(implicitWidth + 8, groupList.width - 160)
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: grpCol.gm ? (grpCol.gm.count + I18n.tr(" 张")
                                          + (root.collapsedFolders[grpCol.dir]
                                             ? I18n.tr("（已折叠，点击展开）") : "")) : ""
                                    font.pixelSize: 10
                                    color: Theme.textDim
                                }
                            }
                            MouseArea {
                                objectName: "groupHeaderArea"
                                anchors.fill: parent
                                onClicked: root.toggleFolderGroup(grpCol.dir)
                            }
                        }

                        /* 本组照片网格：Flow 自适应换行，窗口宽度变化无需重排 */
                        Flow {
                            visible: !root.collapsedFolders[grpCol.dir]
                            width: parent.width
                            spacing: 0
                            Repeater {
                                model: grpCol.gm
                                delegate: photoCell
                            }
                        }
                    }
                }
            }
            }



        Column {
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            visible: root._inGroupMode() ? groupSectionsModel.count === 0
                          : gridView.count === 0
            spacing: 12
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root._mode === "search"
                      ? I18n.tr("没有找到匹配的照片")
                      : I18n.tr("还没有照片")
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Theme.textDim
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: root._mode !== "search"
                text: I18n.tr("点击菜单 文件 → 添加照片文件夹…\n选择你的照片文件夹即可入库（就地登记索引，不复制、不移动文件）")
                horizontalAlignment: Text.AlignHCenter
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textDim
                lineHeight: 1.6
            }
        }

        /* 0.5.66：视频播放器改 Loader 懒加载——QtMultimedia 是可选能力
           （麒麟缺 libpulse 时插件加载失败），直接实例化会拖垮整个页面加载；
           懒加载失败（item=null）自动回退系统播放器，其余功能不受影响。 */
        Loader {
            id: videoPlayerLoader
            active: false
            sourceComponent: VideoPlayerDialog { }
        }

        Popup {
            id: stackPopup
            objectName: "stackPopup"
            modal: true
            dim: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
            width: Math.min(parent.width - 80, 820)
            height: Math.min(parent.height - 80, 560)
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            background: Rectangle {
                color: Theme.surface
                radius: Theme.radiusLarge
                border.width: 1
                border.color: Theme.divider
            }
            property int _stackId: -1
            ListModel { id: stackModel }
            function openFor(stackId, title) {
                _stackId = stackId
                var arr = LibraryBridge.stackMembers(stackId)
                stackModel.clear()
                for (var i = 0; i < arr.length; ++i) stackModel.append(arr[i])
                stkTitle.text = I18n.tr("栈：") + title + "（" + stackModel.count + I18n.tr(" 张）")
                open()
            }
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                Row {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    leftPadding: Theme.spacingMedium
                    rightPadding: Theme.spacingMedium
                    Text {
                        id: stkTitle
                        anchors.verticalCenter: parent.verticalCenter
                        font.family: Theme.fontFamily
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: Theme.text
                    }
                    Item { Layout.fillWidth: true }
                    PMButton {
                        text: I18n.tr("关闭")
                        Layout.preferredHeight: 30
                        onClicked: stackPopup.close()
                    }
                }
                GridView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.leftMargin: Theme.spacingMedium
                    Layout.rightMargin: Theme.spacingMedium
                    Layout.bottomMargin: Theme.spacingMedium
                    model: stackModel
                    cellWidth: 150
                    cellHeight: 150
                    clip: true
                    ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AlwaysOn }
                    delegate: Item {
                        width: 150
                        height: 150
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 4
                            radius: Theme.radiusMedium
                            color: Theme.bg
                            border.width: 1
                            border.color: Theme.divider
                            clip: true
                            Image {
                                anchors.fill: parent
                                anchors.margins: 2
                                fillMode: Image.PreserveAspectCrop
                                source: model.thumb || ""
                                asynchronous: true
                                smooth: false
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var ids = []
                                for (var k = 0; k < stackModel.count; ++k)
                                    ids.push(stackModel.get(k).id)
                                var idx = index
                                stackPopup.close()
                                root.photoContextRequested(ids, idx)
                                root.photoClicked(stackModel.get(idx).id)
                            }
                        }
                    }
                }
            }
        }
    }
}
