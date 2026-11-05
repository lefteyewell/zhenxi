# 阶段 3 验收报告 — 双机元数据同步 / 重复检测 / 高级搜索 / 备份

日期：2026-08-01 ｜ 项目：照片管理系统（离线 · 双平台）

## 一、总体结论

阶段 3 全部 6 项完成：
1. **双机元数据同步**（导出→导入回路实测：人物 3 / 人脸归属 72 / 事件 4 / 标签 160 全量迁移，72 张脸 100% 按 bbox 归位）
2. **重复检测**（dHash 感知哈希，320 张 1.1s 全量计算；注入 3 张同内容实测检出 1 组；真实库 0 误报）
3. **高级搜索**（tag/person/camera/folder/ext/date/dates/gps/faces + AND/OR/NOT，8 项字段断言全过）
4. **备份/恢复**（VACUUM INTO 在线备份 + restore 回路验证）
5. **GUI 接入**（重复视图、高级搜索面板、备份/同步按钮、标签编辑）
6. **测试**：test_stage3 8/8 + 全量回归（pipeline/cluster/smoke）通过

## 二、交付模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 同步 | `photo_manager/core/sync.py` | 导出 persons/face_assign/events/photo_tags 元数据包（SQLite）；导入按 file_path+bbox 匹配、事件按 start_at 覆盖、人物按名合并；**导入前自动备份** |
| 备份 | `photo_manager/core/backup.py` | `VACUUM INTO` 在线安全备份（WAL checkpoint 后），失败回退文件复制；restore 清理 WAL 残留 |
| 重复检测 | `photo_manager/core/duplicates.py` | 64-bit dHash（基于缩略图，多进程）；前 16bit 分桶 + 汉明距离 ≤6 并查集聚类；主照片=最高分辨率+最早时间；仅报告不删除 |
| 高级搜索 | `photo_manager/core/search.py` | 语法：`tag:/person:/camera:/folder:/ext:/date:/dates:/gps:/faces:`、`-` 排除、`OR`、逗号多值；未知词走 FTS（前缀+trigram） |
| 标签 | DB photo_tags 表 + CLI `pm tag` + GUI 详情面板 | 标签搜索、同步、展示 |
| CLI | `pm syncexport / syncimport / hashes / dedupe / backup / restore / tag` | 全部经实测 |
| GUI | DuplicatesPage、AdvancedSearchPanel、顶部备份/同步按钮、InfoPanel 标签编辑 | LibraryBridge 新增 6 个槽 |

## 三、验证结果（320 张真实测试库）

| 项 | 结果 |
|----|------|
| 同步导出 | 人物 3 / 人脸归属 72 / 事件 4 / 标签 160（包 76KB） |
| 同步导入 | matched_faces 72/72、事件标题导出方覆盖、人物名按名合并（异名新建实体）、标签 160、未匹配 0；导入前自动生成备份 |
| 重复哈希 | 320 张 1.11s（2 进程），fail 0；注入 3 张同图 → 检出 1 组 3 冗余，主照片正确保留 |
| 高级搜索 | tag 120 / person / camera / ext / date / dates / faces:0 / `OR` / `-tag` 组合全过（8 断言） |
| 备份恢复 | backup → 破坏库 → restore → 数据完整 |
| GUI | 重复视图渲染、高级搜索面板（位置/尺寸正确）、搜索框 4 种语法回车全链路执行、标签增删改 |

## 四、关键设计决策

1. **同步以"人工整理结果"为边界**：照片文件本体由外部工具（rsync/robocopy）同步，软件只交换元数据；避免双机文件镜像的复杂度。
2. **导入保守合并**：人物按名匹配（异名新建不覆盖）、事件按 start_at 覆盖标题（避免污染本地聚类）、人脸按 file_path+bbox 匹配（防止跨照片误挂）。
3. **重复检测用缩略图而非原图**：dHash 只依赖相对亮度关系，JPEG 压缩/缩放稳健；320 张 1.1s，20 万级预估 ~12 分钟（可后台跑）。
4. **VACUUM INTO 备份**：事务安全、在线执行、产出紧凑副本；WAL checkpoint 后复制更干净。
5. **高级搜索解析器**：token 级解析（组间 AND、组内 OR、`-` 取反、逗号多值展开），未知字段回退 FTS，不破坏既有简单查询。

## 五、遗留 / 后续

- 人物重名合并 UI（同步后同名异实体需要合并操作）
- 重复组批量导出清理包（仅报告，用户自行处理）
- GUI 截图工具对 Popup 渲染受限（RHI 交换链），已用功能级验证替代
- 麒麟 aarch64 实机联调（阶段 4）
