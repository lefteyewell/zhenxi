# 阶段 2 验收报告 — 事件聚类 / 人脸聚类 / AI 多进程并行 / GUI 接入

日期：2026-08-01 ｜ 项目：照片管理系统（离线 · 双平台）

## 一、总体结论

阶段 2 全部 6 项完成：
1. **事件时间聚类**（4 小时间隔，准确还原 4 个拍摄事件，0.2s）
2. **人脸聚类**（128 维特征 + 余弦相似度 + 并查集，3 位人物 72 张脸全对）
3. **AI 管线多进程并行**（人脸 4 进程、OCR 4 进程 × 单线程推理，320 张全量通过）
4. **GUI 真实接入**（缩略图网格 / 事件视图 / 中文搜索 / 详情面板 / 批量导出，截图验证）
5. 3000px 解码上限（**防 OOM 死机**，8GB 内存机器）
6. 阶段 2 测试 5/5 通过，GUI 冒烟 + 全链路功能验证通过

## 二、交付模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 事件聚类 | `photo_manager/core/events.py` | gap_hours=4.0 时间窗口聚类；文件夹名去日期前缀命名；GPS 取中位数 |
| 人脸聚类 | `photo_manager/core/facecluster.py` | 余弦相似度阈值 0.637 + UnionFind 并查集；分块 1024 矩阵乘；>30000 张脸按事件域 scoped 聚类；persons 表 + person_id/cluster_id 回写 |
| 人脸并行 | `photo_manager/core/faces.py` | ProcessPoolExecutor，默认 `min(cpu,4)`；MAX_DIM=3000 缩放上限 |
| OCR 并行 | `photo_manager/core/ocr.py` | 同上；RapidOCR 推理线程=1（配置 `rapidocr_config.yaml`，4 进程不超订） |
| 入库修复 | `photo_manager/core/pipeline.py` | `_upsert` 文件变更时清理残留 faces/ocr_texts 行 |
| GUI 数据桥 | `photo_manager/ui/library_bridge.py` | statsText/photos/eventPhotos/events/searchPhotos/suggest/photoDetail/exportPhotos + 信号 |
| GUI 页面 | `ui/qml/main.qml` + `pages/GalleryPage.qml` `EventsPage.qml` `InfoPanel.qml` | 真实缩略图网格、搜索框联想（文件名+目录）、事件卡片、EXIF/OCR 详情、批量导出（仅复制） |
| 入口 | `photo_manager/__main__.py` | `python -m photo_manager` 可启动 |
| 冒烟测试 | `tests/smoke_ui.py` | offscreen 子进程启动 + QML 全模块加载 + 主题切换 |

## 三、验证结果（320 张测试图，test_data 4 事件 × 4 相机 × 20）

| 项 | 结果 |
|----|------|
| 入库 | 320/320 indexed，0 failed，65.96s |
| 人脸 | 72 张脸检出（320 张中 92 张含脸），0 失败，156.45s（4 进程） |
| 人脸聚类 | 72 张脸 → **3 位人物，与生成器真值 100% 一致**；类内相似度 min 0.543 / mean 0.855，类间 max 0.627 |
| OCR | 128 张含文字 161 段，0 失败，757.83s（4 进程） |
| 事件聚类 | 4 个事件，与生成器 4 事件完全一致，0.207s |
| 搜索 | "年会" → 120 张（FTS 文件名/目录命中），联想"年"→ 公司年会 3 目录 |
| GUI | 3 页截图均渲染真实缩略图；QML smoke 通过；导出复制 1 张成功 |

## 四、性能对比（8 核 / 8GB 开发机）

| 管线 | 阶段 1（单进程） | 阶段 2（多进程） | 加速 |
|------|------|------|------|
| 人脸 320 张 | 基线（96 张 242s → 320 张约 810s） | **156.45s** | ~5.2× |
| OCR 320 张 | 962.23s（1 worker） | 757.83s（4 worker × 1 thread） | 1.27× |

OCR 加速有限的原因：8GB 内存下磁盘交换（WAL + 页缓存 + 4 进程解码），CPU 多核未吃满；目标机 16GB+ 预期更好。

## 五、关键技术决策与教训

1. **OOM 死机**：8 进程 × 30MP 全尺寸解码直接耗尽 8GB 内存导致系统死机（WAL 落盘无损）。修复：MAX_DIM=3000 缩放上限 + 默认 4 worker。
2. **3000px 上限反而提升检出率**：YuNet 在超大分辨率（6720px）全尺寸检测失效（锚点范围外），缩放后 71 张脸全检出。
3. **OCR 线程调优**：默认 RapidOCR 每进程 8 onnx 线程会过订阅（8 核 4 进程=32 线程）；`rapidocr_config.yaml` 锁定 intra/inter=1，每进程 1 推理线程。
4. **聚类正确性**：余弦相似度阈值 0.637（= 距离 0.363）在测试集上人物 3 身份零误差；大库（>30000 脸）自动按事件域分块避免全量 N² 内存。
5. **变更文件残留**：pipeline `_upsert` 曾遗留旧 faces/ocr_texts 行导致重复 photo_id，已修复并加清理。

## 六、遗留 / 后续阶段

- 人物 / 地点 / 设备 / 标签 视图（nav 占位，阶段 3）
- 缩略图异步加载（当前 QML Image 直载，20 万级需要 LRU 缓存）
- OCR 提速依赖目标机内存；可加 JPEG 解码用 AVX 编译的 OpenCV（已有）
- 麒麟 aarch64：face/ocr 管线已容器冒烟，GUI 需 Qt 6.8 aarch64 包验证
