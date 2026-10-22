# 真昔（照片管理系统）

> English documentation: [README_EN.md](README_EN.md)

**真昔** —— 面向摄影师的本地照片管理软件：快速检索（人脸 / 文字 / EXIF / 文件夹等任意组合）、
缩略图与原图查看、批量生成常用分辨率图片并导出，**程序内无任何删除功能**。

## 许可证

本项目采用 **GPLv3 + 商业双重授权**：

- **社区版**：以 [GNU 通用公共许可证第 3 版](LICENSE)（GPLv3）发布——个人使用、学习、
  二次开发并同样开源均免费；衍生作品须同样以 GPLv3 开源
- **商业授权**：企业嵌入、闭源集成、OEM 预装等场景需要付费商业授权，
  详见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)
- **贡献**：提交贡献即同意签署 [CLA.md](CLA.md)（版权转让，双重授权模式的前提），
  贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)
- 第三方依赖许可证清单见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)

## 发布地址

- **官方仓库**：[github.com/lefteyewell/zhenxi](https://github.com/lefteyewell/zhenxi)
  （源码、发行版下载、问题反馈）——源码获取与官方渠道以此为准
- 联系邮箱见文末「许可与版权」

## 运行环境

- Windows 10/11 x86_64、银河麒麟 V10 桌面版 aarch64（飞腾 / 鲲鹏）
- 目标机器完全断网运行，全部依赖与 AI 模型随安装包内置

## 技术栈

| 组件 | 选型 |
|---|---|
| 语言 / UI | Python 3.12 + PySide6（Qt Quick / QML） |
| 数据库 | SQLite（WAL + FTS5） |
| RAW 解码 | rawpy（LibRaw） |
| OCR | RapidOCR（PP-OCRv4 ONNX，离线） |
| 人脸 | OpenCV Zoo YuNet + SFace（ONNX，离线，可商用许可） |
| 打包 | PyInstaller（Windows）/ PyInstaller + deb（麒麟 ARM） |

## 开发环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m photo_manager.main
```

无界面自检（CI / 冒烟测试）：

```powershell
$env:QT_QPA_PLATFORM="offscreen"; python tests/smoke_ui.py
```

## 目录结构

```
photo_manager/          应用主包
  __init__.py           APP_NAME / APP_VERSION / QML_DIR / models_dir()
  main.py               GUI 入口（--smoke 无界面自检）
  cli.py                命令行 pm：ingest/faces/ocr/events/facecluster/search/stats/sync*/hashes/dedupe/backup/tag/restore
  core/                 db(scherma/连接/FTS5) · pipeline · scanner · extractor · faces · facecluster · ocr · events · search · sync · backup · duplicates · autotag · csv_export · system
  ui/library_bridge.py  Python <-> QML 桥（全部读/写/异步任务经此暴露为 @Slot）
  ui/qml/               QML 界面（theme 主题 / components 组件 / pages 页面）
tools/                  打包(build_win.ps1)、验收(gui_check/accept_real/acceptance)、图集与基准生成、模型获取、aarch64 容器/子系统验证、分发裁剪(trim_dist)
tests/                  smoke_ui + test_pipeline/cluster/faces/search/stage3/people_tags/autotag/c3_features
docs/                   各阶段验收报告 + DEVELOPMENT.md（开发文档）+ agents/ 迭代方案
```

详见 **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**：架构分层、数据模型、LibraryBridge 桥接 API、QML 结构、测试与构建、开发约定（popupGate 门禁、无删除红线、PopupDragHandle 用 `var` target 等易踩坑）。

## 构建与打包

**Windows**：`pip install -r requirements.txt` 后 `python tools\build_win.ps1`（按 `photo_manager.spec` 打包并 `--smoke` 自检，产物 `dist\PhotoManager\PhotoManager.exe`）。

**银河麒麟 V10 (aarch64)**：经 `tools/setup_docker.ps1` / `setup_wsl*.ps1` 准备离线环境，详见 `docs/kylin_test_guide.md`。模型用 `python tools/fetch_models.py` 下载到 `models/`。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py"     # 单元/管线测试
$env:QT_QPA_PLATFORM="offscreen"; python tests/smoke_ui.py   # 无头加载全部 QML
python tools/gui_check.py --offscreen                    # 全量界面验收（不动真实库）
python tools/accept_real.py                              # 真实照片全链路验收
python tools/acceptance.py                               # 端到端验收
```

## 阶段计划（全部完成）

- [x] 0. 环境搭建 + 界面骨架 + 打包流水线 + 测试图集工具
- [x] 1. 扫描入库 / EXIF / 缩略图 / 基础搜索 / 导出引擎
- [x] 2. OCR / 人脸 / 自动归类 / 智能相册
- [x] 3. 双机元数据同步 / 重复检测 / 高级搜索 / 备份
- [x] 4. 百万级性能优化 / 弱机适配 / 验收联调（详情见 docs/stage4_report.md）

## 扩展功能（C 系列迭代，均已全量自检）

- **人物 / 标签管理**：人物、地点、设备、标签分类浏览；标签重命名与合并、移出人物、回收站恢复
- **时间线 / 统计**：按 年→月→天 层级浏览；库统计（照片/人脸/标签/评级分布等）
- **评级与精选/排除**：1-5 星评级、精选/排除旗标；图库快速筛选、高级搜索 `rating:`/`flag:` 语法、统计面板分布
- **幻灯片播放**：大图查看器内播放/暂停，左右键切换，关闭自动停止
- **批量时间校正**：按小时偏移整体校正拍摄时间（预览影响张数后可执行）
- **元数据 CSV 导出**：照片清单 + EXIF + 标签 + 评级/旗标（UTF-8 BOM，Excel 友好）
- **GPS 散点地图**：离线地图页按经纬度散点浏览带坐标照片，点击查看
- **退出自动备份**：正常退出时自动备份数据库（保留最近 10 份）
- **多级返回**：进入事件/人物/地点/设备/标签/月份等照片页时显示「‹ 返回」，一键回到来源页
- **多人脸逐脸区分**：同一照片多张人脸可单独指派人物（信息面板人脸裁剪列表 + 大图人脸框叠加 + 指派弹窗），不再整张照片一起移
- **批量选择**：人物分类支持多选合并；回收站「全部恢复」一键重导入全部已移出目录
- **缺失照片两阶段清除**：重建索引标记为 missing 的照片在回收站「缺失照片」区可单选 / 全选 / 按文件夹批量移入待删除区（可恢复，文件找回自动恢复）；「待删除」区二次确认后才彻底删除记录与缩略图——原照片文件本就在系统外被删除，程序仍不触碰任何现存文件
- **菜单与布局优化**：工具菜单快捷项（备份/CSV/导出 XMP/自动分析）、搜索菜单快捷筛选（精选/已评级/高评分）、左侧导航按「浏览/按内容分类/时间与统计」分组


## 许可与版权

- **版权所有 (C) 2026 蒙汗药**
- 联系邮箱：`lefteyewell@qq.com`（小写，首字母为字母 l 而非数字 1；
  仅作联系与商业授权咨询用，见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)）
- 社区版以 GPLv3 开源（见 [LICENSE](LICENSE)，英文原文为准）；
  中文帮助理解版见 [docs/LICENSE-GPLv3-zh.md](docs/LICENSE-GPLv3-zh.md)（非官方译文，仅供参考）
- 闭源集成 / OEM 等场景可购买商业授权（见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)）
- 提交贡献即视为同意 [CLA.md](CLA.md) 的版权转让条款
