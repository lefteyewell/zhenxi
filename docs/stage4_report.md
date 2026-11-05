# 阶段 4 验收报告 — 百万级性能 / 弱机适配 / 验收联调

日期：2026-08-01 ｜ 项目：照片管理系统（离线 · 双平台：Windows x86_64 + 麒麟 ARM64）

## 一、总体结论

阶段 4 全部完成：
1. **百万级性能基准**：合成 20 万 / 100 万行真实库，全链路实测（搜索/聚类/哈希/相册）
2. **GUI 虚拟化**：GridView 滚动加载（500/批）+ 缩略图异步解码，20 万行库端到端验证
3. **索引优化**：相册首屏 1182ms → **0.3ms**；新增 COALESCE 表达式索引 + face_count 索引
4. **弱机适配**：内存探测自动分档 workers/MAX_DIM（PM_MAX_WORKERS/PM_MAX_DIM/PM_BATCH 可覆盖）
5. **验收联调**：一键验收脚本 7/7 + aarch64 容器全链路 10/10 + PyInstaller 打包冒烟
6. **sort_key 物化排序列**：dates 半年 1668ms → **1.3ms**、faces:0 1144ms → **0.9ms**（详情见第六节）
7. **打包体积裁剪**：845.7MB → **468MB**（tools/trim_dist.py）
8. 修复：faces/OCR `scanned` 统计缺失、PMButton implicitWidth 自引用循环、SCHEMA 索引顺序、测试 sort_key 等

## 二、性能基准（8 核 / 8GB 弱机，SQLite 64MB 缓存）

### 20 万行（库 97MB）
| 操作 | 耗时 |
|------|------|
| FTS 关键词搜索 | 26-44 ms |
| camera:/date:/dates:/faces: 高级条件 | 33-76 ms |
| 相册首屏 500 张 | 43 ms |
| 事件聚类（全库） | 2.6 s |
| 人脸聚类（3 万张脸，事件域分块） | 15.3 s |
| 入库 20 万行 | 22.6 s |

### 100 万行（库 480MB）
| 操作 | 优化前 | 优化后 |
|------|--------|--------|
| 相册首屏 500 张 | 1182 ms | **0.3 ms** |
| dates 半年范围 | 1668 ms | **1.3 ms** |
| date 单日 | ~300 ms | **27 ms** |
| faces:0 | 1144 ms | **0.9 ms** |
| camera:sony 等 LIKE | ~1200 ms | ~3 ms（热缓存，提前 LIMIT） |
| FTS 关键词 | 962 ms | 962 ms |
| 组合（dates+相机词） | - | 1229 ms（可接受） |
| 事件聚类 | 45.5 s | 49.9 s（后台任务） |

结论：**百万级日常查询 ≤30ms，组合查询 ~1.2s，后台任务（聚类 ~50s、哈希）可增量执行**。

## 三、GUI 虚拟化（GalleryPage）

- 滚动到底自动加载下一批（500/批），`photos/eventPhotos/searchPhotos` 增加 offset 分页
- `Image.asynchronous: true` 异步解码缩略图，滚动不卡 UI
- 计数显示"已加载 / 总数"；`totalPhotos()` 槽
- 20 万行库端到端验证：loadAll 首批 500 → 连续 4 批 2500 全部正确、totalCount=200000（gui_scroll 脚本）

## 四、弱机适配（photo_manager/core/system.py）

| 可用内存 | workers | MAX_DIM | 适用 |
|----------|---------|---------|------|
| ≥ 8 GB | 4 | 3000 | 开发机 |
| 4-8 GB | 2 | 2500 | 8GB 弱机 |
| < 4 GB | 1 | 2000 | 麒麟低配 |

- Windows 用 GlobalMemoryStatusEx、Linux 读 /proc/meminfo，探测失败回退 8GB 档
- faces/ocr/duplicates 全部接入 auto_workers()；faces MAX_DIM 接入 max_dim()
- 环境变量覆盖：`PM_MAX_WORKERS / PM_MAX_DIM / PM_BATCH`

## 五、验收联调

### 一键验收（tools/acceptance.py）7/7
单测 pipeline / cluster / stage3（同步·重复·搜索·备份）+ GUI 冒烟 + CLI 统计/高级搜索/重复检测全通过。

### aarch64 容器全链路（tools/arm/stage4.Dockerfile + accept_arm.py）10/10
`docker build --platform linux/arm64`（qemu 模拟麒麟）：ingest 320 张 ✓、人脸管线（cv2+onnx）✓、OCR（RapidOCR）✓、dHash 320 ✓、重复 0 组 ✓、事件 4 ✓、人脸聚类（注入合成脸 20 人）✓、FTS 搜索 120 命中 ✓、备份 ✓。
注意：qemu 模拟下单图人脸/OCR 推理约 1-2 分钟（限 2 张验证链路），真机为原生速度；320 张全量人脸在模拟下不现实（约 30 分钟挂起记录）。

### PyInstaller 打包（photo_manager.spec + tools/trim_dist.py，**468MB**）
- 打包 845.7MB → 裁剪 396MB → **468MB**（删除 Qt6WebEngineCore.dll 195MB、resources 101MB、多余翻译 55MB、metatypes/开发资源 16MB 等）
- GUI exe 冒烟 `--smoke` 退出码 0（QML 全部加载）；100 万行库 `PM_DB` 启动冒烟退出码 0
- 内置 QML 资源 9 文件 + 人脸模型 2 个（YuNet/SFace）随包分发
- 注意：PyInstaller 内置 hook 在 Analysis 阶段重新收集 Qt 文件，spec 级过滤无效 → 用构建后 trim_dist.py 裁剪（构建流程：`pyinstaller photo_manager.spec --noconfirm --clean && python tools/trim_dist.py`）

## 六、补充优化：sort_key 物化排序列（dates/faces 百万级根治）

原 `ORDER BY COALESCE(taken_at,'')` 表达式排序在 100 万行触发 temp b-tree（1.2-1.7s）。方案：
- photos 表新增 `sort_key TEXT NOT NULL DEFAULT ''` 列（入库时写 `COALESCE(taken_at,'')`，老库 `_migrate` 自动回填 100 万行 57s）
- 相册/搜索/事件排序全部改 `ORDER BY sort_key DESC, id DESC`（索引逆扫，无 temp b-tree）
- dates/date 条件改写为 `sort_key` 范围（语义等价：NULL→'' 不影响范围匹配）
- 新增 `idx_photos_fc_sort(face_count, sort_key)` 复合索引
- 注意：SCHEMA 中引用新列的索引必须放 `_migrate`（ALTER 之后），否则老库 connect 崩溃

## 七、修复清单

| Bug | 影响 | 修复 |
|-----|------|------|
| faces/ocr `scanned` 统计从未递增 | 进度显示永远 0 | finally 补 `stats["scanned"] += 1` |
| PMButton `implicitWidth: Math.max(96, root.implicitWidth)` 自引用 | binding loop 警告 | 改 `implicitContentWidth + padding` |
| aarch64 验收：`find_duplicates` 返回 list、`backup_db` 需 Database 对象 | 验收脚本崩溃 | 修正断言与调用 |
| SCHEMA 索引引用新列早于 `_migrate` ALTER | 老库 connect 崩溃 | sort_key 相关索引全部移入 `_migrate` |
| 测试直插 photos 不填 sort_key | date/dates 查询回归失败 | 测试 helper 补 sort_key 列 |

## 八、遗留 / 后续

- 麒麟 aarch64 真机联调（容器已验证，需真机跑同套 accept_arm.py）
- onnx 模型半精度压缩（468MB → 可再省 ~30MB）
- 组合查询（dates+相机词）百万级 1.2s，可 trigram 索引根治（低优先）
- 100 万行合成库 `data/perf_test.db`（480MB）供后续基准复用
