# 麒麟 aarch64 真机测试指南

日期：2026-08-02 ｜ 交付物：`dist_arm/PhotoManager-kylin-aarch64.tar.gz`（243MB，解压 611MB）

## 交付物

- 包：`dist_arm/PhotoManager-kylin-aarch64.tar.gz`
- 结构：`PhotoManager/`（PyInstaller onedir：可执行文件 + `_internal/` 依赖，含人脸模型与 QML 资源）
- 构建方式：`tools/arm/stage5.Dockerfile`（aarch64 容器内 PyInstaller 构建 + `tools/trim_dist.py` 裁剪）
- 构建冒烟：容器内 offscreen 启动退出码 0；解压部署后再次冒烟退出码 0（QML 全部加载、缩略图网格渲染、主题正常）

## 真机部署步骤（麒麟 V10 aarch64）

```bash
# 1. 解压（放到有写权限的目录，如用户主目录）
mkdir -p ~/PhotoManager && tar xzf PhotoManager-kylin-aarch64.tar.gz -C ~

# 2. 运行
cd ~/PhotoManager
./PhotoManager/PhotoManager

# 3. 若缺系统库报错（罕见，见"离线说明"），在有网的麒麟机上安装后离线部署
sudo apt-get install -y libgl1 libglib2.0-0 libxcb1 libxcb-cursor0 libxkbcommon-x11-0
```

## 离线说明（重要）

**程序包完全自包含、无需任何额外安装文件**：

- 包内自带 Python 3.11 运行时（`_internal/python3.11/` + `libpython3.11.so.1.0`）、全部 Python 依赖（PySide6/opencv/onnxruntime/rawpy 等及其私有 .so）、AI 模型（YuNet/SFace）与 QML 界面资源——解压即跑，不依赖真机安装 Python 或任何 pip 包
- 真机仅需要系统自带的 Qt/xcb 基础图形库（libX11/libxcb/libxkbcommon/libGL/libglib2.0 等）——**麒麟桌面版默认具备**（桌面环境本身依赖这些）；已在容器内 offscreen 冒烟与解压部署冒烟双重验证
- 无需准备离线 deb 包：Debian 容器产出的 deb 与麒麟自有软件源不兼容；若真机异常缺库（仅极简服务器版可能），在有网的麒麟机器上装对应库即可：
  `sudo apt-get install -y libgl1 libglib2.0-0 libxcb1 libxcb-cursor0 libxkbcommon-x11-0`
  或 `sudo yum install -y libgl libglib2 libxcb libxkbcommon-x11`
- 包内 ldd 提示的 `libQt6WebEngine*/libpulse/libgst*/libwayland-*` 等 not found 均为已裁剪模块（WebEngine/Multimedia/Pdf）的陈旧引用，程序不加载这些模块，可忽略

## 数据与配置

- 默认库：程序运行目录下 `data/library.db`（自动创建）；也可用环境变量指定：
  `PM_DB=/home/user/photos/library.db ./PhotoManager/PhotoManager`
- 照片目录：GUI 顶部"扫描"选择照片目录；缩略图写入照片目录下 `thumbs/`
- 人脸/OCR/聚类/备份/同步等全功能走 GUI 或源码 CLI（`python -m photo_manager.cli ...`）
- 重要：**Windows 与麒麟不要共用同一个库文件**（缩略图路径分隔符差异），各自独立入库后可用双机同步功能交换元数据

## 推荐验证路径

1. 启动 → 扫描一个照片目录（50-500 张）
2. 缩略图网格滚动（验证分页加载与异步解码）
3. 人脸识别 → 人物分组 → 命名（验证 YuNet/SFace 在真机 CPU 速度）
4. OCR → 关键词搜索（验证 RapidOCR + FTS）
5. 高级搜索（tag:/dates:/camera:）、事件归类
6. 备份 / 重复检测 / 标签
7. 性能抽查：5 千-1 万张库上的相册滚动与搜索响应

## 已知差异（容器模拟 vs 真机）

- 容器 qemu 模拟下 AI 推理约慢 5-10 倍，真机为原生速度（阶段 4 容器全链路 10/10 已验）
- 麒麟桌面可能缺少 xcb 相关库，按第 3 步补装
- 若 GUI 字体显示异常，安装中文字体：`sudo apt-get install -y fonts-noto-cjk`（或 `yum install`）
