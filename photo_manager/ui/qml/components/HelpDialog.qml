/* PhotoManager - 照片管理系统
 * Copyright (C) 2026 蒙汗药
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import components 1.0
import i18n 1.0

/* 帮助中心：新手向使用说明（内容与 GUI 实际功能一一对应） */
Popup {
    id: root

    objectName: "helpDialog"

    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 680
    height: 620
    padding: 0

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            Layout.leftMargin: Theme.spacingLarge
            Layout.rightMargin: Theme.spacingMedium
            spacing: Theme.spacingSmall

            PopupDragHandle { target: root; Layout.fillWidth: true; Layout.preferredHeight: 52 }

            Column {
                spacing: 2
                Text {
                    text: I18n.tr("帮助中心")
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: I18n.tr("功能说明与操作方法（离线本地处理，不联网）")
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    color: Theme.textDim
                }
            }
            Item { Layout.fillWidth: true }
            PMButton {
                text: I18n.tr("关闭")
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.divider
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: Theme.spacingSmall
            clip: true
            contentHeight: bodyText.height + 40
            ScrollBar.vertical: PMScrollBar { policy: ScrollBar.AsNeeded }

            Text {
                id: bodyText
                width: root.width - Theme.spacingLarge * 2
                x: Theme.spacingLarge
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.text
                lineHeight: 1.8
                wrapMode: Text.Wrap
                textFormat: Text.RichText
                text: I18n.tr("<b>一、快速开始（三步）</b><br/>") +
                      I18n.tr("1. 点菜单“<b>文件 → 添加照片文件夹…</b>”，选择存放照片的文件夹，稍等片刻；<br/>") +
                      I18n.tr("2. 扫描完成后，中间区域会显示全部照片（按拍摄时间倒序）；<br/>") +
                      I18n.tr("3. 点击任意照片查看右侧详情；在顶部搜索框输入关键词即可筛选。<br/><br/>") +
                      I18n.tr("<b>二、添加照片</b><br/>") +
                      I18n.tr("· 菜单“文件 → 添加照片文件夹…”→ 选文件夹 → 自动扫描；<b>可勾选“包含子文件夹”</b>") +
                      I18n.tr("（默认勾选，取消后只扫描所选文件夹的顶层）；<br/>") +
                      I18n.tr("· <b>导入机制</b>：只处理<b>图片格式白名单</b>内的文件") +
                      I18n.tr("（图片：jpg/png/heic/heif/avif/webp/tif/bmp/gif/mpo/psd + 44 种相机 RAW；视频：mp4/mov/mkv/avi/webm 等；FITS/HDR/EXR/PhotoCD 等冷门格式需系统装有 ImageMagick 兜底），")
                      + I18n.tr("<b>其他任何非图片/视频文件一律不读取、不分析、不复制</b>，仅在遍历目录时跳过；<br/>") +
                      I18n.tr("· <b>JPEG XL（.jxl，可选）</b>：默认未启用——没有可直接安装的预编译库，需手动安装 pillow-jxl-plugin 后才能识别；未安装时 .jxl 会被当作非图片跳过，<b>不影响其他任何格式</b>。<br/>") +
                      I18n.tr("· <b>RAW/HEIC 等大图</b>：Qt 不能直接解码这些格式，打开大图时会<b>自动生成解码预览</b>（缓存于 data/previews/，长边 1920px）后显示；个别损坏文件会提示「无法预览」。<br/>") +
                      I18n.tr("· <b>程序已在运行时再次启动</b>（双击图标/ exe）：不会开第二个实例，而是<b>唤起已有窗口</b>（托盘场景同样适用）。<br/>") +
                      I18n.tr("· <b>视频</b>：支持常见视频格式，自动生成缩略图与时长；在信息面板点「▶ 播放」或双击缩略图，用<b>内嵌播放器</b>播放（若当前环境缺少解码组件——如麒麟未装 gstreamer——会自动提示并改用系统播放器）。<b>0.5.51 起视频可被语义检索</b>：入库时按时长均匀抽取 5 个关键帧（信息面板可见帧带），编码为语义向量后可用「clip:文字」搜到视频、也会打场景标签。<br/>") +
                      I18n.tr("· 只读取信息、生成缩略图，<b>不会删除、移动或修改原照片</b>；<br/>") +
                      I18n.tr("· 再次扫描同一文件夹只会补充新增的照片，不会重复添加；<br/>") +
                      I18n.tr("· 菜单“文件 → 管理路径…”可查看已纳入管理的文件夹（树状展示，点击节点展开/收起）。<br/><br/>") +
                      I18n.tr("<b>三、浏览照片</b><br/>") +
                      I18n.tr("左侧导航分三组：<br/>") +
                      I18n.tr("· <b>浏览</b>：全部照片（按拍摄时间倒序，向下滚动自动加载更多）、按文件夹；<br/>") +
                      I18n.tr("· <b>按内容分类</b>：事件、重复、人物、地点、设备、标签；<br/>") +
                      I18n.tr("· <b>时间与统计</b>：时间线、相册、回忆、作废（不删除）、已导出、统计、地图、回收站。<br/>") +
                      I18n.tr("说明：<br/>") +
                      I18n.tr("· <b>按文件夹</b>：点开即按计算机目录树（系统浏览器式）浏览；可切换 <b>仅已添加</b>") +
                      I18n.tr("（只看已纳入管理的文件夹及其父/子文件夹）或 <b>全部</b>（显示所有文件夹，未添加的显示为灰色）；<br/>") +
                      I18n.tr("· <b>事件</b>：按拍摄时间自动聚类的照片组；<b>人物</b>：按人脸聚类；<b>地点</b>：按 GPS 坐标聚合；") +
                      I18n.tr("<b>设备</b>：按相机型号；<b>标签</b>：按标签；<b>重复</b>：查找内容相同或相似的照片（只报告、不删除）；<br/>") +
                      I18n.tr("· <b>时间线</b>：按 年→月→天 层级浏览；<b>统计</b>：库统计面板（照片/人脸/标签/评级分布等）；<br/>") +
                      I18n.tr("· <b>地图</b>：离线 GPS 散点，按经纬度浏览带坐标照片，点击查看；<br/>") +
                      I18n.tr("· <b>回收站</b>：移出管理的照片，可“全部恢复”一键重导入；<br/>") +
                      I18n.tr("· 进入事件/人物/地点/设备/标签/月份等照片页时顶部显示“‹ 返回”，一键回到来源页；<br/>") +
                      I18n.tr("· 照片右下角标记：👤×N 表示人脸数，文 表示含识别文字。<br/><br/>") +
                      I18n.tr("<b>四、搜索照片</b><br/>") +
                      I18n.tr("顶部搜索框直接输入即可，支持：<br/>") +
                      I18n.tr("· 普通关键词：文件名、相机型号、OCR 文字；<br/>") +
                      I18n.tr("· tag:旅行 —— 按标签搜索；层级标签用 / 分隔（如「旅行/北京」），输入父节点名（如 旅行）会匹配其所有子孙节点；<br/>") +
                      I18n.tr("· person:王老师 —— 按人物搜索；<br/>") +
                      I18n.tr("· date:2025-03-02 —— 某一天拍摄；<br/>") +
                      I18n.tr("· dates:2025-01-01..2025-06-30 —— 日期范围；<br/>") +
                      I18n.tr("· camera:sony —— 按相机品牌搜索；<br/>") +
                      I18n.tr("· faces:2 —— 按人脸数量搜索；<br/>") +
                      I18n.tr("· rating:4 —— 评分≥4 星；flag:pick —— 精选；flag:reject —— 排除；<br/>") +
                      I18n.tr("· flag:archive / archived:yes —— 仅看已作废（语法保留 archive 字样）；archived:no —— 仅看未作废；<br/>") +
                      I18n.tr("· color:red（或 color:红/黄/绿/蓝/紫）—— 按色标筛选；color:none —— 未打色标；<br/>") +
                      I18n.tr("· clip:一张海边日落的照片 —— 中文语义搜索（默认开启「自动语义索引」：扫描入库后自动生成向量，在设置里打开开关也会立即为已有照片补跑；也可在工具中心手动「生成语义向量」）；<br/>") +
                      I18n.tr("· ext:jpg —— 按文件类型搜索；<br/>") +
                      I18n.tr("· 排除：-tag:草稿 —— 不要带此标签的；<br/>") +
                      I18n.tr("· 组合：tag:旅行 person:王老师 —— 多个条件空格隔开；<br/>") +
                      I18n.tr("· 输入时下方会弹出联想建议，点击即可搜索。<br/>") +
                      I18n.tr("也可用菜单“<b>搜索 → 高级搜索…</b>”按标签/人物/旗标/类型/日期组合筛选；") +
                      I18n.tr("搜索菜单还提供快捷入口：今天/本周拍摄、带文字、带人脸、精选照片、已评级(≥1★)、高评分(≥4★)。<br/><br/>") +
                      I18n.tr("<b>五、评级、精选与排除</b><br/>") +
                      I18n.tr("· 右侧详情点击星标 <b>1–5★</b> 给照片评级；点“精选 ✓”/“排除 ✕”按钮打旗标；<br/>") +
                      I18n.tr("· 顶部筛选条（chip）：全部 / 精选 / 排除 / 已评级，点击即切换对应视图；<br/>") +
                      I18n.tr("· 搜索菜单快捷：精选照片、已评级(≥1★)、高评分(≥4★)；<br/>") +
                      I18n.tr("· 大图查看器内快捷键：<b>1–5</b> 评级、<b>0</b> 清除评级、<b>P</b> 精选、<b>X</b> 排除、<b>U</b> 取消旗标。<br/><br/>") +
                      I18n.tr("<b>六、大图查看器与幻灯片</b><br/>") +
                      I18n.tr("· <b>点击图库中的照片</b>只在右侧信息面板显示详情，<b>不会弹出大图</b>；<br/>") +
                      I18n.tr("· <b>点击右侧信息面板中的照片预览图</b>（或右键照片选“打开大图”）打开<b>大图查看器</b>（独立窗口）；<br/>") +
                      I18n.tr("· <b>← / →</b> 切换上一张 / 下一张；<b>Esc</b> 关闭；<br/>") +
                      I18n.tr("· 点“幻灯片 ▶”按钮播放/暂停，自动轮播当前照片集；<br/>") +
                      I18n.tr("· 查看器中同样可评级、精选/排除、指派人脸。<br/><br/>") +
                      I18n.tr("<b>七、选择、右键菜单与快捷键</b><br/>") +
                      I18n.tr("· 选择：<b>Ctrl+点击</b> 多选；<b>Shift+点击</b> 范围选择；<b>Ctrl+A</b> 全选当前已加载；<b>Esc</b> 清空选择；")
                      + I18n.tr("选中后底部批量条里点「<b>反选</b>」可翻转选中（取消已选、选中其余）；<br/>") +
                      I18n.tr("· <b>分组视图</b>（工具栏开关，0.5.55）：全部照片视图下按<b>文件夹分组</b>显示，")
                      + I18n.tr("点组头卡片可<b>折叠/展开</b>该组；与排序互相独立（开关状态会记住，默认关）；<br/>") +
                      I18n.tr("· 选中后顶部出现<b>批量操作条</b>（已选 N 张）：批量打标签 / 导出所选 / 移出所选 / 清除选择；<br/>") +
                      I18n.tr("· 右键任意照片弹出菜单：打开大图 / 查找相似照片 / 批量打标签 / 添加到相册 / 色标 /<br/>") +
                      I18n.tr("  导出所选 / 移出所选 / 复制所选路径；<br/>") +
                      I18n.tr("· <b>色标</b>：给照片打红/黄/绿/蓝/紫彩色标记（缩略图左上角圆点），可用 color: 语法筛选；<br/>") +
                      I18n.tr("· <b>查找相似照片</b>：按画面内容找视觉相似的照片（需先生成语义向量）；<br/>") +
                      I18n.tr("· <b>相册</b>：左侧导航「相册」新建自己的分组，选中照片右键「添加到相册」；<br/>") +
                      I18n.tr("  相册只存引用，不会复制/移动/删除任何照片文件，删除相册照片完全不受影响。<br/>") +
                      I18n.tr("· 全局快捷键：<b>Ctrl+F</b> 聚焦搜索框、<b>Ctrl+A</b> 全选、<b>Esc</b> 清空选择。<br/><br/>") +
                      I18n.tr("<b>八、照片详情与标签</b><br/>") +
                      I18n.tr("· 点击照片，右侧显示拍摄时间、相机、镜头、参数、尺寸、位置、人脸数、OCR 文字等；<br/>") +
                      I18n.tr("· 在右侧“标签”输入框输入文字（如：家人）回车或点“加”，即可给照片打标签；<br/>") +
                      I18n.tr("· 同一照片多张人脸可<b>逐脸区分</b>：信息面板的人脸裁剪列表 + 大图人脸框叠加 + 指派弹窗，") +
                      I18n.tr("把每张脸单独指派到某个人物，不再整张照片一起移动；<br/>") +
                      I18n.tr("· <b>低质量人脸清理</b>（工具中心）：列表支持<b>点击行勾选</b>多选，顶部「全选 / 反选」，") +
                      I18n.tr("底部「隐藏选中 / 删除选中标签」只作用于勾选项（另有隐藏全部 / 删除全部）；<br/>") +
                      I18n.tr("· 打过标签的照片可用 tag:标签名 快速找回。<br/><br/>") +
                      I18n.tr("<b>九、导出、备份与移出</b><br/>") +
                      I18n.tr("· <b>文件 → 导出所选</b>：把选中的照片复制到指定文件夹（原片不动）；<br/>") +
                      I18n.tr("· <b>文件 → 移出管理</b>：把选中的照片<b>移出管理</b>（移到指定文件夹，并从<br/>") +
                      I18n.tr("索引、搜索、归类、人脸/标签中彻底清除；不会删除文件，移动前会检查目标盘空间）；<br/>") +
                      I18n.tr("· <b>文件 → 立即备份</b>：把数据库（含人脸、标签、事件）备份到程序 data/backups；<br/>") +
                      I18n.tr("· <b>文件 → 备份到…</b>：选择任意目录备份数据库（生成 library_日期.db）；<br/>") +
                      I18n.tr("· <b>文件 → 从备份恢复…</b>：选择备份文件还原数据库（恢复前自动再备份一份）；<br/>") +
                      I18n.tr("· <b>文件 → 导出/导入元数据</b>：把人物、人脸归属、事件、标签导出/恢复为 .db 文件；<br/>") +
                      I18n.tr("· <b>工具 → 导出全部元数据 CSV…</b>：导出照片清单 + EXIF + 标签 + 评级/旗标（UTF-8 BOM，Excel 友好）。<br/><br/>") +
                      I18n.tr("<b>十、界面与个性化</b><br/>") +
                      I18n.tr("· 顶部菜单收纳了全部功能按钮，窗口再小也不会丢失入口；<br/>") +
                      I18n.tr("· “配色”下拉框：选择主题颜色；“深色/浅色”按钮：切换明暗模式。<br/><br/>") +
                      I18n.tr("<b>十一、工具中心（智能分析）</b><br/>") +
                      I18n.tr("菜单“<b>工具 → 工具中心…</b>”打开：<br/>") +
                      I18n.tr("· <b>自动分析</b>：按 事件聚类 → 重复检测 → 人脸识别 → 文字识别 依次运行，可随时“停止”中断（已完成阶段保留），再继续；<br/>") +
                      I18n.tr("· <b>后台任务不挡操作</b>：分析运行期间可正常浏览、筛选、评级；进度弹窗点「隐藏」仅收起提示，<b>不会中断任务</b>（状态栏仍显示进度）；")
                      + I18n.tr("需要互斥的操作（再次分析/备份/导出/移出等）会提示“有任务正在运行，请稍候”并排队；<br/>") +
                      I18n.tr("· <b>任务队列</b>：进度弹窗列出本次待运行的全部阶段（✓已完成 / ▶进行中 / ·待办），一眼看清共几项、当前第几项；<br/>") +
                      I18n.tr("· <b>人脸识别</b>：为未处理的照片检测人脸并提取特征；<b>文字识别（OCR）</b>：识别照片中的文字；<br/>") +
                      I18n.tr("· <b>感知哈希</b>：计算照片指纹，供“重复”视图查找相似照片；<b>事件聚类</b>：按拍摄时间重新归并事件；<br/>") +
                      I18n.tr("· <b>人脸聚类</b>：把同一人的多张脸归并为一位“人物”；<b>批量打标签</b>：按路径/文件名关键词统一加标签；<br/>") +
                      I18n.tr("· <b>自动打标签</b>：按<b>文件路径/文件名中的场景关键词</b>自动打标签") +
                      I18n.tr("（如路径含“旅行”“海边”“发布会”即打对应标签；<b>不做画面内容识别</b>）；") +
                      I18n.tr("<b>批量时间校正</b>：按小时偏移整体校正拍摄时间（先“预览受影响”再“执行偏移”）；<br/>") +
                      I18n.tr("· <b>重建索引</b>：检查照片是否已在系统外被删除，发现后自动从搜索与归类中排除，避免出错或崩溃；<br/>") +
                      I18n.tr("· <b>检查照片文件夹</b>：对每个已登记的扫描根与照片库根重新扫描——自动收录新增的照片，") +
                      I18n.tr("并对比库内数据发现<b>被人工删除</b>或改动的照片（详情可用「完整性校验」查看）。") +
                      I18n.tr("把照片复制进照片文件夹后点此按钮即可收录；配合定时任务可全自动；<br/>") +
                      I18n.tr("以上计算都在后台执行，完成后照片详情、搜索结果自动刷新。<br/><br/>") +
                      I18n.tr("<b>照片库根目录、定时任务与常驻</b><br/>") +
                      I18n.tr("· <b>照片库根目录</b>（设置 → 照片库根目录）：可添加多个文件夹作为照片库保存路径，列表显示每个根的剩余空间，★ 为默认根；<br/>") +
                      I18n.tr("· <b>自动复制入库</b>：开启后，导入/检查时不在任何照片库根目录下的照片会按") +
                      I18n.tr("「源文件夹名/子路径」整体复制入库（<b>只复制照片文件</b>，非图片一律不复制；") +
                      I18n.tr("源照片保持原样，已在库内的照片直接就地登记）；<b>某个根磁盘空间不足时，自动改用其他有空间的根</b>") +
                      I18n.tr("（按文件大小预留 256MB 余量挑选）；<br/>") +
                      I18n.tr("· <b>定时任务</b>：菜单栏「<b>定时任务</b>」独立设置——选择 关闭 / 仅一次 / 每日，") +
                      I18n.tr("设定执行时间，勾选「检查照片文件夹」和/或「智能分析」，到点自动执行。") +
                      I18n.tr("<b>执行方式二选一</b>：<b>程序内计时</b>（默认，需程序保持运行，配合开机启动+托盘）或 ") +
                      I18n.tr("<b>系统任务计划</b>（Windows 任务计划 / 麒麟 systemd 用户定时器，关机不错过、到点自动唤起程序跑完即退，不常驻内存）。") +
                      I18n.tr("一次性任务执行后自动关闭；错过的每日任务下次开会自动补跑；<br/>") +
                      I18n.tr("· <b>开机自动启动</b>（设置 → 启动与常驻，默认关）：开机时自动运行本程序，") +
                      I18n.tr("绿色便携无需安装、无需管理员权限；启用后若移动程序文件夹，请取消勾选再重新勾选；<br/>") +
                      I18n.tr("· <b>关闭窗口时最小化到托盘</b>（设置 → 启动与常驻，<b>默认开</b>）：") +
                      I18n.tr("点关闭按钮会隐藏到系统托盘继续后台运行，双击托盘图标恢复窗口，右键托盘图标可退出；") +
                      I18n.tr("系统不支持托盘时该选项自动失效，窗口照常关闭。<br/>") +
                      I18n.tr("配合「开机自动启动」+ 托盘常驻，定时任务即可在每次开机后持续生效。<br/>") +
                      I18n.tr("<b>十二、常见问题</b><br/>") +
                      I18n.tr("Q：为什么打开后没有照片？<br/>") +
                      I18n.tr("A：首次使用库是空的，点菜单“文件 → 添加照片文件夹…”选择照片文件夹即可<br/>") +
                      I18n.tr("（就地登记索引，不复制、不移动原文件）。<br/>") +
                      I18n.tr("Q：为什么照片的人脸/文字/重复检测是空的？<br/>") +
                      I18n.tr("A：扫描入库时只生成缩略图与基本信息；点“工具 → 工具中心”运行自动分析或分别运行<br/>") +
                      I18n.tr("人脸识别、文字识别、感知哈希即可补齐，完成后会自动聚类事件与人物。<br/>") +
                      I18n.tr("Q：备份存在哪里？恢复怎么操作？<br/>") +
                      I18n.tr("A：“立即备份”存在程序 data/backups；“备份到…”可存到任意目录。恢复用<br/>") +
                      I18n.tr("“文件 → 从备份恢复…”（或工具中心里的“从备份恢复”），选择备份文件即可<br/>") +
                      I18n.tr("还原（恢复前会自动再备份当前库）。<br/>") +
                      I18n.tr("Q：如何校正相机时间偏差 / 批量改拍摄时间？<br/>") +
                      I18n.tr("A：打开“工具 → 工具中心”，在“批量时间校正”输入偏移小时数（负值向前、正值向后），<br/>") +
                      I18n.tr("先点“预览受影响”确认张数，再点“执行偏移”。<br/><br/>") +
                      I18n.tr("<b>十三、键盘快捷键</b><br/>") +
                      I18n.tr("· <b>Ctrl+F</b>：定位到搜索框；<b>Ctrl+A</b>：全选已加载照片；<br/>") +
                      I18n.tr("· <b>空格 / 回车</b>：打开选中照片的大图（大图内 ←→ 翻页，Esc 关闭）；<br/>") +
                      I18n.tr("· <b>1~5 / 0</b>：大图内评级（0 清除）；<b>P / X / U</b>：精选 / 排除 / 清除旗标；<br/>") +
                      I18n.tr("· <b>Delete / Backspace</b>：大图内排除 / 清除旗标（可逆，程序内不删除原图）；<br/>") +
                      I18n.tr("· <b>F5</b>：刷新当前视图；<b>Ctrl+,</b>：打开设置；<b>Esc</b>：关闭弹窗。")
            }
        }
    }
}
