# 开发文档（Developer Guide）

面向需要二次开发、调试、扩展本项目的工程师。用户向功能说明见仓库根 `README.md`，本文聚焦**架构、数据模型、桥接 API、测试与构建**等工程细节。

> 代码根：`photo_manager/`（应用包）、`tools/`（打包/验收/生成工具）、`tests/`（单测）、`docs/`（阶段报告与规划）。

---

## 1. 架构分层

```
┌──────────────────────────────────────────────────────────┐
│  QML UI 层  (photo_manager/ui/qml)                         │
│   pages/ (画廊/信息/分类/事件/时间线/地图/回收站/统计/重复) │
│   components/ (弹窗/按钮/树/拖拽把手/Toast…)               │
│   theme/ (Theme.qml 统一配色与字体)                         │
└───────────────▲───────────────────▲───────────────────────┘
                │ 信号上行 / 属性绑定 │ LibraryBridge 槽调用
┌───────────────┴───────────────────┴───────────────────────┐
│  LibraryBridge  (photo_manager/ui/library_bridge.py)       │
│   Python <-> QML 唯一桥梁；所有读/写/异步任务经此暴露为 @Slot│
└───────────────▲───────────────────▲───────────────────────┘
                │ 直接调用            │ 后台线程 (_spawn / worker)
┌───────────────┴───────────────────┴───────────────────────┐
│  Core 层  (photo_manager/core)                             │
│   pipeline / scanner / extractor / faces / facecluster /   │
│   ocr / events / search / sync / backup / duplicates /     │
│   autotag / csv_export / system                            │
└───────────────▲───────────────────────────────────────────┘
                │ 读写
┌───────────────┴───────────────────────────────────────────┐
│  DB 层  (photo_manager/core/db.py)                         │
│   SQLite（WAL + FTS5）；SCHEMA 常量定义全部表与索引          │
└───────────────────────────────────────────────────────────┘
```

**数据流**：扫描入库（`pipeline`/`scanner`/`extractor`）→ 分析（人脸 `faces`/`facecluster`、OCR `ocr`、事件 `events`、聚类、哈希）→ 检索/浏览（QML 经 `LibraryBridge` 读 `db`）→ 导出/移出/同步。

**关键约定**
- `main.py` 是唯一 GUI 入口，构造 `LibraryBridge` 后以 context property 注入 QML（`LibraryBridge`、`ThemeController`）；`--smoke` 仅加载校验不进入事件循环。
- 所有长任务（扫描/人脸/OCR/备份/同步/分析）经 `LibraryBridge._spawn(kind, title, fn, args)` 在后台线程执行，并通过 `taskProgress` / `message` / `toast` 信号回报 UI，避免阻塞主线程。
- **安全红线**：程序内**无任何删除源文件的逻辑**（仅 `moveOut` 移动+清索引、回收站 `movedOutList` 可重导入）。新增功能不得引入源文件删除。

---

## 2. 目录结构（详细）

```
photo_manager/
  __init__.py            APP_NAME / APP_VERSION / QML_DIR / models_dir()
  main.py                GUI 入口（--smoke 无界面自检）
  cli.py                 命令行 pm：ingest/faces/ocr/events/facecluster/
                         search/stats/syncexport/syncimport/hashes/dedupe/
                         backup/tag/restore
  core/
    db.py                SQLite schema / 连接 / FTS5 同步（SCHEMA 常量）
    pipeline.py          入库管线编排（扫描→提取→缩略图→索引）
    scanner.py           文件系统递归扫描
    extractor.py         EXIF / 尺寸 / GPS 提取
    faces.py             人脸检测（OpenCV Zoo YuNet）+ 裁剪
    facecluster.py       人脸聚类与识别（SFace 描述子）
    ocr.py               RapidOCR（PP-OCRv4 ONNX，离线）文本识别
    events.py            事件（时间/空间）聚类
    search.py            搜索：FTS5 + tag:/person:/camera:/date:/gps:/rating:/flag: 语法
    sync.py              双机元数据同步（导出/导入包）
    backup.py            数据库备份/恢复（退出自动备份保留最近 10 份）
    duplicates.py        感知哈希重复检测
    autotag.py           依据路径/相机等自动打标签
    csv_export.py        元数据 CSV 导出（UTF-8 BOM）
    system.py            弱机适配 / 系统信息
  ui/
    library_bridge.py    Python <-> QML 桥（核心 API 见 §3）
    bridge.py            ThemeController 等 QML 侧控制对象
    qml/
      main.qml           主窗口（导航/页签/全局弹窗/快捷键门禁 popupGate）
      pages/             GalleryPage / InfoPanel / CategoryPage / EventsPage /
                         TimelinePage / MapPage / StatsPage / DuplicatesPage /
                         TrashPage / PhotoViewer
      components/        PopupDragHandle / PMButton / Toast / BatchTagDialog /
                         *Dialog / FolderTree / NavItem / qmldir
      theme/             Theme.qml（统一配色/字体/圆角），qmldir
tools/
  build_win.ps1          一键打包（PyInstaller + --smoke 自检）
  gui_check.py           全量界面验收（A 层 QML + B 层 bridge，默认用临时库副本）
  accept_real.py         真实照片全链路验收（EXIF/事件/人脸/OCR）
  acceptance.py          端到端验收（GUI + CLI 统计/搜索/重复）
  gen_test_images.py     生成测试图集（连拍/人物/风景等，确定性）
  gen_perf_db.py         生成性能基准库（百万级压测）
  fetch_models.py        下载 AI 模型到 models/
  setup_docker.ps1 / setup_wsl*.ps1    aarch64 容器/子系统验证环境
  trim_dist.py           分发裁剪（精简依赖体积）
tests/
  smoke_ui.py            无头加载全部 QML + LibraryBridge + 主题
  test_pipeline.py / test_cluster.py / test_faces.py / test_search.py /
  test_stage3.py / test_people_tags.py / test_autotag.py / test_c3_features.py
docs/
  stage0~4_report.md     各阶段验收报告
  agents/PLAN_C1.md / PLAN_C2.md   C 系列迭代方案
  kylin_test_guide.md    银河麒麟 aarch64 测试指南
```

---

## 3. 数据模型（`core/db.py` · `SCHEMA`）

| 表 | 关键列 | 说明 |
|---|---|---|
| `meta` | key, value | 元数据（版本/设置） |
| `scan_roots` | path, last_scan_at | 已纳入管理的根目录 |
| `photos` | id, file_path(UNIQUE), file_name, folder_path, ext, file_size, file_mtime, content_hash, taken_at, sort_key, camera_make/model, lens_model, exposure, f_number, iso, focal_length, gps_lat/lon/alt, width, height, thumbnail_path, thumb_width/height, face_count, has_text, ocr_text, status(pending/indexed/error), error, indexed_at, **rating(0-5), flag(''/'pick'/'reject')**, created_at | 核心照片表 |
| `faces` | id, photo_id(FK CASCADE), bbox, descriptor(BLOB), score, cluster_id, person_id | 人脸检测与识别 |
| `ocr_texts` | id, photo_id(FK), text, conf, bbox | OCR 文本（另建 `ocr_fts` 全文表） |
| `events` | id, start_at, end_at, title, center_lat/lon, photo_count | 事件聚类 |
| `event_photos` | event_id, photo_id（联合主键） | 事件-照片关联 |
| `persons` | id, name(UNIQUE), face_count | 人物 |
| `photo_tags` | photo_id, tag（联合主键） | 标签（多对多） |
| `photos_fts` | file_name, folder_path, camera_make, camera_model, lens_model … | FTS5 全文索引 |
| `analysis_state` | — | 分析阶段状态（断电续跑） |
| `move_out_records` | id, photo_id, dest_dir | 移出/回收站记录 |

**索引**：`idx_photos_taken_at` / `folder` / `status` / `taken_expr` / `face_count` / `sort_key` / `rating` / `flag`，`idx_faces_photo` / `cluster`，`idx_ocr_photo`，`idx_tags_tag`，`idx_move_out_dir`。

> 本地库默认路径 `data/library.db`（WAL 模式）。`data/` 已在 `.gitignore`，不入库；改动前请用 `LibraryBridge.backupNow()` 或 `cli backup` 备份。

---

## 4. LibraryBridge 桥接 API（`ui/library_bridge.py`）

全部以 `@Slot` 暴露给 QML，返回常用 `QVariant`（list[dict] / dict / int / str / bool）。以下为分类速查（参数略，详见源码）。

**浏览 / 路径导航**
`photos(offset,limit)` · `totalPhotos()` · `photoDetail(id)` · `folderTree(root)` · `folderPhotos(folder,offset,limit)` · `folderCount(folder)` · `folderTreeAll()` · `folderToggle(path,expanded)` · `dirChildren(path)` · `dirCount(path)` · `dirPhotos(path,offset,limit)` · `fsRoots()` · `fsChildren(path)` · `fsParent(path)` · `fsHome()` · `fsLastRoot()` · `managedPaths()` · `openFolder(photo_id)`（系统文件管理器打开所在目录，返回 bool）

**分类浏览**
`people()` · `personPhotos(id,offset,limit)` · `personCount(id)` · `renamePerson(id,name)` · `newPerson(name)` · `mergePersons(src,dst)` · `movePhotosToPerson(ids,person_id)` · `photoFaces(photo_id)` · `assignFace(face_id,person_id)` · `faceCropUrl(face_id)` · `mergePeople(ids)` · `locations()` · `locationPhotos(lat,lon,…)` · `locationCount(lat,lon)` · `devices()` · `devicePhotos(model,…)` · `deviceCount(model)` · `tags()` · `tagPhotos(tag,…)` · `tagCount(tag)` · `renameTag(old,new)` · `mergeTags(src,dst)` · `events()` · `timeline()` · `timelineDays(ym)` · `dateMonthPhotos(ym,…)` · `dateMonthCount(ym)` · `datePhotos(day,…)` · `dateCount(day)` · `mapPoints()` · `mapPhotos(lat,lon,…)` · `mapCount()`

**回收站**
`movedOutList()` · `reimportMovedOut(folder)` · `restoreAllMovedOut()`

**检索**
`searchPhotos(q,offset,limit)` · `suggest(q)`

**标签 / 评级 / 旗标**
`addTag(photo_id,tag)` · `removeTag(photo_id,tag)` · `photoTags(photo_id)` · `setRating(photo_id,rating)` · `setFlag(photo_id,flag)` · `ratedPhotos(min_rating,…)` · `ratedCount(min_rating)` · `flagPhotos(flag,…)` · `flagCount(flag)` · `bulkTag(match,tag)` · `batchTag(ids,tag)`（单事务幂等，返回真实插入数）· `setClipboard(text)` · `autoTagAll()`

**相册 / 色标 / 以图搜图（C11）**
`albums()` · `albumCreate(name)`（重名返回 0）· `albumRename(id,name)` · `albumDelete(id)`（只删分组，不动照片）· `albumAddPhotos(id,ids)` · `albumRemovePhotos(id,ids)` · `albumPhotos(id,offset,limit)` · `albumPhotoCount(id)` · `setColorLabel(ids,color)`（批量；red/yellow/green/blue/purple 或中文单字，空串清除）· `findSimilar(photo_id)`（后台，完成后发 `similarFinished`）· `similarCount()` · `similarPhotos(offset,limit)`（保持相似度降序，附 `score`）

**照片库 / 定时任务 / 文件夹检查（C12）**
`ingest(folder,recursive)` / `ingestMany(folders,recursive)`（QML 一律走 1 参槽 `ingest`/`ingestMany`/`ingestFlat`/`ingestManyFlat`，⚠️ 2 参 QML→Python 调用在 gui_check offscreen 下会 TypeError，原因未明，规避之）· `libraryRoots()/setLibraryRoots(text)`（每行一个库根）· `copyToLibraryEnabled()/setCopyToLibraryEnabled(bool)`（开启后导入自动把库外照片复制入库，见 core/library.py relocate_file，映射表 library_imports）· `folderCheck(analyze_after)`（后台：扫描根∪库根重新扫描自动收录新增 + check_integrity 报缺失/改动）· `scheduleMode/setScheduleMode`（off/once/daily）· `scheduleTime/setScheduleTime`（每日 HH:MM）· `scheduleOnceAt/setScheduleOnceAt` · `scheduleCheckEnabled/setScheduleCheckEnabled` · `scheduleAnalyzeEnabled/setScheduleAnalyzeEnabled`（QTimer 每 30s 轮询，`_sched_tick` 判定到期，main.py 启动时 `start_scheduler()`；软件运行期间生效）

**导出 / 移出**
`exportPhotos(ids,dest_dir)` · `moveOut(ids,dest_dir)` · `exportCsv(out_path)`

**分析（异步，经 `_spawn`）**
`runFaces(limit)` · `runOcr(limit)` · `runHashes(limit)` · `runEvents()` · `runFaceCluster()` · `autoAnalyze()` · `stopAnalysis()` · `analysisStatus()`

**维护 / 库管理**
`ingest(folder)` · `ingestMany(folders)` · `reindexCheck()` · `backupNow()` · `backupTo(out_dir)` · `backupOnExit()` · `restoreBackup(file)` · `syncExport(out_path)` · `syncImport(src_path)` · `duplicates(dist)` · `timeShiftPreview(hours,folder)` · `timeShift(hours,folder)` · `statsText()` · `statsDashboard()` · `dbDetail()` · `close()`

**信号**：`photosChanged` · `photoSelected(id)` · `message(str)` · `taskProgress(cur,total,str)` · `toast(text, kind)`（`kind` ∈ success/error/warning/info，由 `_finish()` 按内容判定）· `integrityFinished(str)` · `similarFinished(str)`（JSON 摘要）

> 约定：批量写操作（打标签/移出/导出）**不主动发 `photosChanged`**（避免主视图 `showAll()` 重置已选），由调用方在需要时显式刷新。

---

## 5. QML 结构

- **主题**：`theme/Theme.qml` 集中定义 `primary` / `surface` / `surfaceAlt` / `divider` / `text` / `success` / `warning` / `danger` / `radius*` / `spacing*` / `fontFamily`，所有页面/组件统一引用，避免硬编码颜色。
- **页面**：`GalleryPage`（网格+筛选 chip+批量条+右键菜单，含 album/similar 模式与色标圆点）、`InfoPanel`（详情/评级/旗标/标签/人脸指派）、`CategoryPage`（人物/地点/设备/标签 Tab）、`EventsPage`、`TimelinePage`、`MapPage`、`StatsPage`、`DuplicatesPage`、`TrashPage`、`AlbumsPage`（虚拟相册，navState 17）、`PhotoViewer`（独立大图窗口，幻灯片）。
- **通用组件**：`PMButton`、`PopupDragHandle`（弹窗标题栏拖拽，见 §7）、`Toast`、`BatchTagDialog`、`*Dialog`（文件/文件夹/合并/重命名/分析进度/帮助/工具/高级搜索）、`FolderTree`、`NavItem`。组件经各目录 `qmldir` 注册（如 `components/PopupDragHandle.qml` → `PopupDragHandle 1.0`）。
- **筛选 chip 注意**：`GalleryPage` 筛选 chip 的 `Repeater` 使用 **JS 对象数组** `model: [{label, mode}, …]`；delegate 内必须用 `modelData.label` / `modelData.mode`（本 Qt 版本下 `model` 指向数组本身而非元素，`model.label` 为 undefined）。

---

## 6. 测试

| 命令 | 说明 |
|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 单元/管线测试（约 59 项，含 pipeline/cluster/faces/search/people_tags/autotag/c3_features） |
| `$env:QT_QPA_PLATFORM="offscreen"; python tests/smoke_ui.py` | 无头加载全部 QML + LibraryBridge + 主题，校验无加载错误 |
| `python tools/gui_check.py --offscreen` | **全量界面验收**（A 层 QML objectName 查找 + B 层直接调 bridge，默认 `VACUUM INTO` 临时库副本，**不动真实库**） |
| `python tools/accept_real.py` | 真实照片全链路验收（EXIF/事件/人脸/OCR/聚类） |
| `python tools/acceptance.py` | 端到端验收（GUI + CLI 统计/高级搜索/重复检测） |

**约定**
- `gui_check` 通过 `objectName` 定位 QML 元素（如 `batchBar` / `galleryMenu` / `toastLayer` / `ctxOpen`），新增可测 UI 元素时务必设置 `objectName`，并同步补充 `A*`/`B*` 验收项。
- `gen_test_images.py` 对同一脚本版本**确定但跨版本不字节一致**；图集重生成后需 `restore_ingest.py` 或 `cli ingest` 重建索引，否则 DB 记录与磁盘字节不符。
- 验收产物日志写入 `tools/gc_*.txt`（已在 `.gitignore`）。

---

## 7. 开发约定（易踩坑）

1. **`popupGate` 门禁**：`main.qml` 中维护一个 `QtObject { id: popupGate }` 汇总所有窗口级 `Popup`/`Menu` 的 `opened` 状态。**新增窗口级弹窗/菜单必须并入 `popupGate`**，否则 `Esc`/`Ctrl+A` 等全局快捷键会与 `Popup.CloseOnEscape` 抢键。
2. **`PopupDragHandle.target` 必须是 `var`**：原声明 `property Item target` 在 `target: <Popup>` 时静默失败（Popup 非 `QQuickItem`），导致拖拽失效并报警告；已改为 `property var target`。改动委托/对话框时勿改回。
3. **无删除红线**：任何新增功能不得删除源照片文件；"移除/移出"应走 `moveOut` + `move_out_records`，可回收站重导入。
4. **后台长任务**：耗时操作一律经 `LibraryBridge._spawn` 进线程，禁止在主线程做 IO/解码。
5. **离线优先**：全部 AI 模型与依赖随安装包内置，目标机器断网运行；禁止引入联网依赖或功能。
6. **跨平台路径**：文件名/路径含中文与空格，凡涉及 `os.startfile` / `subprocess` 打开目录、缩略图 URL（`file://`）、`QUrl.fromLocalFile` 均需正确处理编码与绝对路径。

---

## 8. 构建与打包

**Windows（x86_64）**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tools\build_win.ps1        # 1) 装 PyInstaller 2) 按 photo_manager.spec 打包 3) --smoke 自检
# 产物：dist\PhotoManager\PhotoManager.exe
```
打包规格在仓库根 `photo_manager.spec`（PyInstaller）；`tools/trim_dist.py` 用于分发裁剪。

**银河麒麟 V10（aarch64 / 飞腾·鲲鹏）**
通过 `tools/setup_docker.ps1` / `setup_wsl*.ps1` 准备容器或子系统，模型与依赖离线内置；详见 `docs/kylin_test_guide.md`。

**模型准备**：`python tools/fetch_models.py` 下载 YuNet / SFace / PP-OCRv4 等 ONNX 到 `models/`（开发环境 `models_dir()` 默认取 `项目根/models`，打包后取 `_internal/models`）。

---

## 9. 常见调试

- **QML 加载/绑定警告**：`QT_LOGGING_RULES="qt.qml.connections=false"` 配合 offscreen 跑 `smoke_ui.py`；关注 `Unable to assign [undefined]`（多为 `model` vs `modelData`、属性类型不匹配）。
- **库状态异常**：`LibraryBridge.reindexCheck()` 检查缺失原图/缩略图；`dbDetail()` 看库概览；先 `backupNow()` 再任何重建索引操作。
- **性能基准**：`tools/gen_perf_db.py` 生成百万级库，配合 `tools/bench_perf.py` 压测检索/缩略图路径。
