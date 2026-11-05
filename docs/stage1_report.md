# 阶段 1 验收报告 — 核心入库管线 / AI 索引 / 全文搜索

日期：2026-08-01 ｜ 项目：照片管理系统（离线 · 双平台）

## 一、总体结论

阶段 1 全部 8 项完成。扫描→EXIF→缩略图→入库→人脸→OCR→搜索的全链路已打通，
在 96 张测试图上验证通过（0 失败），并完成 20 万行合成数据性能粗测。
**核心库（photos/faces/ocr_texts/events）+ WAL/FTS5 双索引（unicode61 + trigram）已就绪。**

## 二、交付模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 数据库层 | `photo_manager/core/db.py` | WAL + synchronous=NORMAL + busy_timeout + 64MB 页缓存；schema v1；列级迁移（face_done/ocr_done） |
| 扫描器 | `photo_manager/core/scanner.py` | 递归扫描，格式白名单（图片 10 种 + RAW 10 种），mtime+size 增量跟踪，跳过隐藏/系统目录 |
| 提取器 | `photo_manager/core/extractor.py` | EXIF（Pillow get_ifd 解析 EXIF/GPS 子 IFD）、拍摄时间 ISO 归一、GPS 十进制度转换、RAW 内嵌预览缩略图 |
| 入库管线 | `photo_manager/core/pipeline.py` | 扫描→提取→缩略图→写库；逐文件容错；变更文件自动重置 AI 状态待重跑 |
| 人脸管线 | `photo_manager/core/faces.py` | YuNet 检测 + SFace 特征（128 维 float32 blob）；中文路径兼容（imdecode） |
| OCR 管线 | `photo_manager/core/ocr.py` | RapidOCR（模型内置离线）；聚合文本→photos.ocr_text + ocr_fts 双写 |
| 搜索 | `photo_manager/core/search.py` | 文件名/文件夹/相机 unicode61 前缀 + OCR trigram 子串；<3 字符 LIKE 回退；文件名联想 |
| CLI | `photo_manager/cli.py` | ingest / faces / ocr / search / stats |
| 模型拉取 | `tools/fetch_models.py` | 双镜像源 + sha256 校验 + 已存在跳过 |
| 集成测试 | `tests/test_pipeline.py` | 3 用例（元数据/增量入库/搜索），unittest 通过 |

## 三、验证结果（96 张测试图，test_data）

| 项 | 结果 |
|----|------|
| 入库 | 96/96 indexed，0 failed，27s（含缩略图），增量续扫 0 新增 |
| 元数据填充 | taken_at / camera_model / width / 缩略图 / GPS 全部 96/96（修复前 GPS 0/96） |
| 人脸 | 44 张检出 71 张脸，0 失败，243s（CPU）；特征 128 维，aarch64 容器内同链路已验 |
| OCR | 38 张含文本 48 段，置信度 1.0（"2025年度公司年会"等横幅），0 失败，291s |
| 搜索 | 年会→36 / canon→3 / _MG→3 / R6→2 / "年会 canon"→3（跨索引 AND） |
| WAL | journal_mode=wal 确认 |
| FTS 同步 | photos_fts 96/96 与主表一致（触发器） |

## 四、性能粗测（20 万行合成数据，SQLite 51MB）

| 查询 | 耗时 |
|------|------|
| FTS 前缀（相机/文件名/OCR 组合） | <1ms（首查 234ms 含冷缓存） |
| OCR trigram 子串（含双词 AND） | <1ms |
| 文件名联想 LIKE 前缀 | 0.2s |
| 按时间倒序取 50 | 0.34s（生产表有 taken_at 索引，此测例未建） |

结论：搜索设计在 100 万张规模下可支撑（预计联想 ~1s，需 1 万+ 张时复核 LIKE 路径）。

## 五、关键踩坑记录

1. **Pillow getexif 子 IFD**：getexif() 对 EXIF(34665)/GPS(34853) 只返回偏移量，须 `get_ifd()` 解析——否则 ISO/快门/GPS 全空。
2. **cv2.imread 中文路径**：Windows 下失败 → 改 `np.fromfile + cv2.imdecode`。
3. **FTS5 中文分词**：unicode61 将连续中文视为单 token，"年会" 搜不到 "年度公司年会" → OCR 建 trigram 独立索引（子串匹配）；<3 字符走 LIKE 回退（含相机列）。
4. **FTS5 引号与前缀**：`"词"*` 引号短语不参与分词前缀；ASCII 安全词裸词保留 `词*` 前缀语义。
5. **opencv-python 与 headless 冲突**：rapidocr 元依赖 opencv-python，与 headless 互斥 → 保留 headless 并卸载 opencv-python。

## 六、遗留与后续（阶段 2 输入）

1. **并行化**：人脸/OCR 单线程 2.5s~3s/张，100 万张需多进程（进程池 + 独立连接），估算目标 ≥8 进程。
2. 事件时间聚类（events 表已建，聚类算法待做：时间簇主信号 + OCR/文件夹名辅助）。
3. 人脸聚类归一化（descriptor 已入库，cluster_id/person_id 待算：余弦相似度 + 连通分量）。
4. 搜索联想在 10 万+ 规模复核 LIKE 路径；OCR 短词（1-2 字）LIKE 全表扫描风险记录。
5. GUI 接入：搜索框（联想）、相册流（缩略图）、批量导出（无删除功能约束已明确）。
6. HEIC 支持需 pillow-heif（离线打包时评估）。
7. 麒麟 ARM 打包：wheel 离线介质 + PyInstaller aarch64 交叉验证（阶段 0 已铺路）。

## 七、验收标准对照

| 标准 | 结果 |
|------|------|
| 96 张全链路 0 失败 | ✅ |
| 增量续扫不重复入库 | ✅ |
| 元数据（EXIF/GPS/缩略图）完整 | ✅ |
| 人脸检测+特征入库 | ✅（含 aarch64 同链路） |
| OCR 文本入库 + FTS 可搜 | ✅ |
| 中文子串搜索 | ✅ trigram |
| 多词跨索引组合搜索 | ✅ |
| 单元测试 | ✅ 3/3 |

**阶段 1 验收：通过。**
