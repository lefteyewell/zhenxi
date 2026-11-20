# 真昔（照片管理系统）

> English documentation: [README_EN.md](README_EN.md)

**真昔** —— 面向摄影师的本地照片管理软件：快速检索（人脸 / 文字 / EXIF / 文件夹等任意组合）、
缩略图与原图查看、批量生成常用分辨率图片并导出，**程序内无任何删除或修改用户照片的功能**。

## 最新版本 v0.7.7（2026-11-20）

> 📥 下载：[Releases 页面](https://github.com/lefteyewell/zhenxi/releases) ｜
> 📋 全部版本变化：[CHANGELOG.md](CHANGELOG.md)

**变更**

- **「查找疑似重复」只能在勾选 1 个人物时使用**：人物页查重按钮在未勾选或勾选多人时置灰并给出提示（请先点「选择」勾选 1 个人物 / 一次只能按 1 个人物查重）；后台进行、关闭弹窗不中断、忙碌期自动排队不变
- **移除全库扫描入口**：弹窗内「全库扫描」按钮与未勾选时的全库比对入口一并移除，查重只有按人查一条路径；「显示全部」仅解除人物过滤，不触发扫描
- **帮助与提示文案同步更新**：帮助写明按钮可用条件；弹窗空列表提示引导先勾选 1 个人物

<details>
<summary>上一版本 v0.7.6（2026-11-19）摘要</summary>

**修复**

- **不同入口进入「疑似重复人物」弹窗，顶部提示口径不统一**：等待提示混杂「扫描中…」「已对比 0 / 1 张人脸」「加载中…」三种写法；现扫描等待统一为「扫描中… · 已用 mm:ss」（进度已知带计数与预计剩余），仅候选加载显示「加载中…」
- **从菜单进入弹窗残留上次的「仅看：人物 X」过滤**：现进入时自动重置为显示全部候选
- **人物页查重按钮悬停说明与实际不符**：旧文案称「只与这一个人比较」，实际比对全库（含已命名）；已重写

**改进**

- **扫描完成提醒**：弹窗关闭时扫描照常后台进行，完成后底部提示「发现 N 组，点击查看」可点击重开弹窗；未发现/失败同样有提示
- **弹窗说明与按钮提示写明后台与排队行为**：后台进行、关闭弹窗不中断、重复发起自动排队

</details>

<details>
<summary>上一版本 v0.7.5（2026-11-19）摘要</summary>

**修复**

- **查找疑似重复时「提示有结果、列表却空」**：连续给多个人物查找、或全库扫描进行中时，扫描请求被静默丢弃而弹窗照样打开——显示上一次的进度与结果数，列表却按当前人物过滤为空、时好时坏；现忙碌期请求自动排队，当前扫描完成后自动按所选人物补扫
- **所选人物没有可用人脸或扫描失败时完全静默**：现明确提示并自动解除过滤显示全部候选；全库扫描异常提示「扫描失败，请重试」
- **候选数据加载失败被误报为「暂无候选」**：现明确提示加载失败

**改进**

- **扫描进度新增耗时预估**：进度附带「已用 mm:ss · 预计还需约 mm:ss」，按实际速率每秒刷新
- **弹窗内常驻排队提示**：排队期间显示「排队中：当前扫描完成后将自动按『人物 X』补扫」，此前仅弹一次底部提示

</details>

<details>
<summary>上一版本 v0.7.4（2026-11-18）摘要</summary>

**修复**

- **麒麟系统「疑似重复人物」弹窗空白**：全库查找后再对单个人物查找疑似相似无结果；根源为跨线程数据传输在麒麟 Qt 版本上不可靠，现全程序统一改 JSON 文本传输根治（0.7.3 的加固只是缓解）
- **弹窗「仅看：人物 N」与勾选的人物对不上**：弹窗内人物称呼现与人物页显示编号完全同口径
- **人物命名/合并/删除后疑似重复候选指向错误人物**：编号复用使旧候选「死而复生」；现三条路径都同步清理候选表
- **「已选人物」面板行上 ✕ 点击无效**：行悬停区域拦截了按钮按下事件；现 ✕ 与取消勾选框等效

**改进**

- **「使用说明」弹窗提纲式改版**：左侧章节目录 + 右侧正文；标题与菜单统一；首次使用弹窗统一为「首次使用引导」；开源许可弹窗新增中文参考版页签（非官方译本）
- **高级搜索面板字段说明**：「相机 → 评级」各输入框右侧直接写明填写规则（人物名称或编号、位置可填地名、支持 >/>= 比较等）

</details>

<details>
<summary>上一版本 v0.7.3（2026-11-18）摘要</summary>

**新功能**

- **人物页多选右栏「已选人物」面板**：人物多选时右侧信息栏自动顶替为已选人物清单（头像 / 名称 / 照片数），勾选即时增减、点 ✕ 直接取消勾选，降低误选风险；退出选择或离开人物页自动恢复信息栏

**修复**

- **照片信息栏人脸计数不准**：隐藏人脸后摘要与人脸分区两处数字漂移、高级搜索「人脸数」受影响；现统一按可见人脸口径实时显示，历史库自动重算（每库一次，无需手动操作）
- **4 张脸时「还有 N 张」不出现**：折叠阈值与单行显示口径不一致，正好藏 1 张却无展开按钮
- **按人物编号搜索找不到人**：`person:` 搜索编号与界面显示的重排编号不一致（命名过人物即错位）；现完全一致
- **「疑似重复人物」弹窗打开报 TypeError、扫描后可能停在「正在汇总…」**：装饰器贴错位置致弹窗初始化中断；候选回填加固为逐行容错

</details>

<details>
<summary>上一版本 v0.7.2（2026-11-18）摘要</summary>

**新功能**

- **JPEG XL（.jxl）开箱即支持**：随包内置 libjxl 官方解码器 djxl（BSD-3），不再需要手动安装 pillow-jxl-plugin（已装的自动优先）；导入 / 缩略图 / 预览 / 人脸 / 文字识别 / 语义向量全链路可用
- **苹果实况照片（.livp）支持导入**：自动解包为「HEIC 静态照片 + MOV 视频」两条正常记录，各走既有分析链路，不新增特判路径
- **天文格式 FITS 支持导入**：内置零依赖迷你解析器，整数 / 浮点全支持，分位数拉伸显示
- **照片解码多层兜底**：OpenCV → Pillow → djxl → 系统已装 ImageMagick 逐级兜底，冷门格式照片不再「解不出即报错」

**改进**

- **帮助中心例外说明更新**：.jxl 改「开箱即支持」、FITS 移出 ImageMagick 依赖清单、明示视频解码为程序内置（HEVC 无需安装系统解码扩展）

</details>

<details>
<summary>上一版本 v0.7.1（2026-11-15）摘要</summary>

**修复**

- **装在 TIFF 容器里的相机 RAW 无法识别**：部分转换工具会把尼康 NEF、佳能 CR2 等传感器数据原样转存为 .tiff——扩展名看着是普通图片，内容其实是相机 RAW。此前按普通图片解码：一部分导入直接报错，另一部分只解出百像素级内嵌小缩略图，预览特小、宽高记错、人脸检不出、OCR 失败。现按**文件内容**自动嗅探（LibRaw 识别为相机 RAW 且尺寸明显更大才判 RAW），实测 21 张样片全部解出真实图像，缩略图 / 预览 / 宽高 / 人脸 / OCR 恢复正常
- **这类照片的预览方向错乱**：外层 TIFF 方向标记与内嵌像素方向冲突导致画面横躺、人脸躺倒检不出；现方向以解码数据流实际方向为准，已正立的不再重复转
- **照片预览弹窗对 .tif/.tiff 仍显示空白或小图**：.tif/.tiff 在「Qt 可直接解码」名单里，预览弹窗此前把原文件直接交给 Qt 引擎，完全绕过嗅探链；现预览弹窗与完整性校验均先做容器嗅探，容器型 RAW 显示按需生成的解码预览（生成后缓存）

**改进**

- **普通 TIFF 照片完全不受影响**：嗅探仅限 .tif / .tiff 扩展名，且要求尺寸 ≥2 倍差异或普通解码失败才判为相机 RAW；结果按文件缓存，分析链路零重复开销
- **大图查看器「1:1 原始」改名「大分辨率」并如实说明**：RAW/HEIC 等格式的查看图是最长边 1920px 的解码预览（既有设计），气泡提示改为如实说明
- **帮助中心新增「例外与特别说明」章节**：集中列出 RAW/HEIC 预览分辨率、JPEG XL 默认不支持、冷门格式依赖 ImageMagick 等易忽略的例外

> ⚠️ **该版升级后请跑一次「扫描入库」**：首次启动会自动把库里已有的 .tif / .tiff 照片置回待重析（每个数据库只做一次），随后一次「扫描入库」即重建缩略图 / 预览 / 宽高并重跑人脸 / OCR / 语义分析。普通照片与视频不受影响。建议先备份数据库。

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
https://ghfast.top/https://github.com/lefteyewell/zhenxi/releases/download/v0.7.7/PhotoManager-0.7.7-win64.zip
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
