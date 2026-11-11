# 真昔（照片管理系统）

> English documentation: [README_EN.md](README_EN.md)

**真昔** —— 面向摄影师的本地照片管理软件：快速检索（人脸 / 文字 / EXIF / 文件夹等任意组合）、
缩略图与原图查看、批量生成常用分辨率图片并导出，**程序内无任何删除或修改用户照片的功能**。

## 最新版本 v0.6.27（2026-11-11）

> 📥 下载：[Releases 页面](https://github.com/lefteyewell/zhenxi/releases) ｜
> 📋 全部版本变化：[CHANGELOG.md](CHANGELOG.md)

本版把 0.6.26 发布后追加的修复正式纳入安装包（线上 v0.6.26 安装包不含这些修复），逐条说明见 CHANGELOG。

**修复**

- **人物视图的「分组视图」开关无效**：进入某人物的照片列表后分组折叠不起作用——现与全部照片视图同样支持，开关即时生效
- **部分对勾仍是根号字形**（麒麟精简字体下明显）：人脸清理、文件夹树、文件夹选择器、分析进度共 4 处改为 Canvas 矢量手绘对勾，零字体依赖
- **疑似重复人物弹窗「出不来结果」**（锚点人物已命名时）：候选对被显示过滤全部滤空——锚点模式放宽限制并显示真实人物名
- **疑似重复扫描进度改为弹窗内计数**：实时显示「已对比 N / M 张人脸」直到「全部对比完毕」，替代此前的任务进度条方案
- **人物列表页排序菜单无效**：排序改在分页切片前完成（名称自然序：人物 2 排在人物 10 之前 / 数量多→少），滚动加载顺序与所选排序一致
- **照片信息栏人脸标签偶发只显示「人物」**：历史字符串数据先归一化再查名称映射

**改进**

- **「查找疑似重复」按人查扩大到全部人物（含已命名）**：整理后期未命名人物所剩无几，此前几乎必然查不到结果；全库扫描范围不变

<details>
<summary>上一版本 v0.6.26（2026-11-10）摘要</summary>

**修复**

- **麒麟包照片列表「选中徽标卡死」**：蓝底白圈勾徽标常显、点选任何照片无视觉反馈——Qt 6.8 下 selected 角色缺失所致；网格改严格布尔比较，并改用模型 C++ `setProperty` 强制写入角色，从根因修复
- **麒麟日志 anchors-in-layout 告警清零**：9 处位置器写法规范化，布局视觉不变
- **统计页五个列表滚动条遮挡数字**：行内容右侧避让滚动条宽度
- **右键菜单「查找相似照片」更名「查找语义相似照片」**：与感知哈希驱动的「重复照片」明确区分
- **后端视频时长空值在 Qt 6.8 下变 undefined**：改发 0，消除 ListModel 逐行告警刷屏（视频徽标行为不变）

**改进**

- **疑似重复人物三项体验修复**：扫描进度在任务栏可见、批量合并清理候选对、按人查只显示与选中人物相关的候选（可解除过滤）

</details>

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

## 下载安装

**普通用户**：到 [Releases 页面](https://github.com/lefteyewell/zhenxi/releases) 下载对应平台的安装包
（Windows / Linux x64 / 银河麒麟 aarch64），AI 模型已全部内置，解压即用。

**从源码构建的开发者**：除源码外还需 3 个离线模型文件（CLIP 编码器 ×2 + 离线地理编码库），
`python tools/fetch_models.py` 一键下载（带 sha256 校验），或手动从
[离线模型 models-v1](https://github.com/lefteyewell/zhenxi/releases/tag/models-v1) 获取；
完整构建步骤见 [docs/BUILDING.md](docs/BUILDING.md)。

**国内下载加速**：GitHub 直连较慢时，可在下载链接前加镜像前缀（把示例里的版本号换成 Releases 页面上实际的版本标签），例如：

```
https://ghfast.top/https://github.com/lefteyewell/zhenxi/releases/download/v0.6.27/PhotoManager-0.6.27-win64.zip
```

常用前缀：`https://ghfast.top/`、`https://gh-proxy.com/` 等（公益镜像时好时坏，失效请更换一个）。

> ⚠️ 安全提示：镜像前缀**只建议用于公开文件的下载**；不要在经过镜像的页面上登录 GitHub
> 或访问私有仓库；浏览器"GitHub 加速"类扩展有读取会话凭据的前科，如需安装请认准开源、
> 大用户量、最小权限的扩展，并务必开启 GitHub 两步验证（2FA）。

## 升级

程序无自动更新，升级 = 手动换新版本目录，用户数据在程序目录的 `data\` 里，跟着搬即可。
每个版本更新了什么，见 [CHANGELOG.md](CHANGELOG.md)。

**方式一（推荐）：新版解压到新目录，迁移 data**

1. 新版压缩包解压到一个**新目录**（不要直接覆盖旧目录，便于随时回退）；
2. 把旧目录的整个 `data\` 文件夹复制到新目录的 `PhotoManager\data\` 位置
   （库、缩略图、备份全部继承；照片原图在库外，不受影响；界面设置存于系统配置，自动保留）；
3. 运行新版 `PhotoManager`，确认照片与功能正常后，旧目录可删除或留档。

**方式二：覆盖解压**——先完全退出程序（含托盘图标），再把新版覆盖解压到旧目录。
`data\` 不在安装包内，不会被覆盖；若覆盖时提示文件被占用，说明程序未退干净。

**注意**：

- 程序目录必须**可写**（不要放 Program Files 等受保护目录，建议 `D:\PhotoManager` 这类位置）；
- 升级前建议先在旧版本里执行一次「工具中心 → 备份」；涉及库结构变更的大版本，
  新版首次启动会自动迁移，升级前有备份才进可攻退可守；
- 程序目录与 `data\` 一起搬到别的电脑/盘符没问题（缩略图为相对路径）；
  但照片原图位置变了的话，对应照片会显示 missing，需更新扫描根目录后重新导入。

## 运行环境

- Windows 10/11 x86_64、银河麒麟 V10 桌面版 aarch64（飞腾 / 鲲鹏）
- 目标机器完全断网运行，全部依赖与 AI 模型随安装包内置

### 硬件需求

| 项目 | 最低配置 | 建议配置 |
|---|---|---|
| 处理器 | 4 核（x86_64 / aarch64 均可） | 8 核及以上 |
| 内存 | 8 GB | 16 GB 及以上 |
| 硬盘 | 程序安装约 1.5 GB（AI 模型内置）+ 库数据空间（约为照片总量的 3%~10%，视缩略图/人脸缓存/语义索引而定）；机械硬盘可用 | 程序与 `data\` 放在 SSD，万张级库的分析与缩略图浏览明显更快 |
| 显示器 | 1280×720 | 1920×1080 及以上 |
| 显卡 | 无要求——全部 AI 推理为 CPU 运算，不需要独立显卡 | 同左 |

说明：

- **基础使用**（浏览、筛选、标签、人物整理）对配置要求不高，最低配置即可流畅使用；
- **AI 分析**（人脸识别、文字识别、以文搜图/以图搜图的语义索引）为多进程 CPU 密集计算，
  首次全量分析耗时与照片数量、CPU 核数成正比（万张级照片约几十分钟量级），期间可正常
  浏览其他照片，分析在后台分批进行、可中途暂停；
- 内存不足时建议在设置里把「分析并行度」调低（auto = 自动留 2 核；每个并行 worker
  都会加载一份模型副本，占内存）；
- 银河麒麟平台（aarch64）按上述同标准执行，低功耗飞腾/鲲鹏处理器建议按建议配置留余量。

## 技术栈

| 组件 | 选型 |
|---|---|
| 语言 / UI | Python 3.12 + PySide6（Qt Quick / QML） |
| 数据库 | SQLite（WAL + FTS5） |
| RAW 解码 | rawpy（LibRaw） |
| OCR | RapidOCR（PP-OCRv4 ONNX，离线） |
| 人脸 | OpenCV Zoo YuNet + SFace（ONNX，离线，可商用许可） |
| 打包 | PyInstaller（三平台；麒麟 aarch64 经 Docker + QEMU 交叉构建，产物为 tar.gz） |

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
docs/                   开发文档（DEVELOPMENT.md）+ 打包指南（BUILDING.md）+ 依赖说明（DEPENDENCIES.md）+ GPLv3 中文参考译文
```

详见 **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**：架构分层、数据模型、LibraryBridge 桥接 API、QML 结构、测试与构建、开发约定（popupGate 门禁、无删除红线、PopupDragHandle 用 `var` target 等易踩坑）。

## 构建与打包

三平台完整步骤见 **[docs/BUILDING.md](docs/BUILDING.md)**（与 CI `.github/workflows/release.yml` 一一对应，照抄即可得到与官方 Release 相同的包）。

**Windows（最简）**：`pip install -r requirements.txt` 后 `python tools\build_win.ps1`（按 `photo_manager.spec` 打包并 `--smoke` 自检，产物 `dist\PhotoManager\PhotoManager.exe`）。

**银河麒麟 V10 (aarch64)**：无需真机，任意装了 Docker 的 x86_64 机器即可交叉构建——用 `tools/arm/kylin.Dockerfile`（glibc 2.31 底座）建镜像，容器内 PyInstaller 打包 + 运行库闭包收集 + GLIBC 预检 + 容器内打 tar，命令见 BUILDING.md 第 3 节（CI 亦按此流程自动构建）。注意旧脚本 `tools/arm/build_kylin.sh` 缺少关键闭包步骤，仅作历史参考，勿用于出货。

**模型准备**：人脸模型已随仓库内置；CLIP 与 geo.sqlite 从 [models-v1 Release](https://github.com/lefteyewell/zhenxi/releases/tag/models-v1) 获取，或直接 `python tools/fetch_models.py` 一键下载（带 sha256 校验）。

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
- [x] 4. 百万级性能优化 / 弱机适配 / 验收联调

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
- **菜单与布局优化**：工具菜单快捷项（备份/CSV/导出元数据包/自动分析）、搜索菜单快捷筛选（精选/已评级/高评分）、左侧导航按「浏览/按内容分类/时间与统计」分组


## 许可与版权

- **版权所有 (C) 2026 蒙汗药**
- 联系邮箱：`lefteyewell@qq.com`（小写，首字母为字母 l 而非数字 1；
  仅作联系与商业授权咨询用，见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)）
- 社区版以 GPLv3 开源（见 [LICENSE](LICENSE)，英文原文为准）；
  中文帮助理解版见 [docs/LICENSE-GPLv3-zh.md](docs/LICENSE-GPLv3-zh.md)（非官方译文，仅供参考）
- 闭源集成 / OEM 等场景可购买商业授权（见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)）
- 提交贡献即视为同意 [CLA.md](CLA.md) 的版权转让条款
