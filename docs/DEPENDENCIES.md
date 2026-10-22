# 依赖清单与平台差异

更新：2026-10-21（0.5.66）

## 一、Python 依赖（pip 层）—— Windows / Linux 完全相同

所有 Python 依赖在两个平台上**没有差异**（同一份 `requirements.txt`），
全部依赖均有 Windows amd64 与 Linux aarch64（manylinux）预编译轮子，无需编译安装：

| 依赖 | 最低版本 | 用途 | 备注 |
|------|---------|------|------|
| PySide6 | >= 6.9.0 | GUI（Qt Quick / QML） | abi3 轮：py3.9 装 6.9.x、py3.12 装 6.11 |
| Pillow | >= 11.1.0 | 图像解码 / 缩略图 / 预览 | |
| numpy | >= 1.26.0 | CLIP 向量运算 / 数组 | 麒麟包（py3.9）解析为 2.0.x |
| pillow-heif | >= 1.1.0 | HEIC / AVIF 解码 | iPhone / 新安卓照片 |
| rawpy | >= 0.21.0 | 44 种相机 RAW 解码（LibRaw） | |
| exifread | >= 3.0.0 | EXIF 元数据 | |
| opencv-python-headless | >= 4.10.0 | 视频抽帧 / 图像处理 | |
| onnxruntime | >= 1.19.0 | AI 推理运行时（人脸/OCR/CLIP） | |
| rapidocr-onnxruntime | >= 1.3.24 | OCR（PP-OCRv4，离线） | |
| piexif | >= 1.1.3 | 仅 `tools/` 测试数据工具需要 | 主程序不使用 |

**可选依赖**（缺失时优雅降级，不装也能用）：

| 依赖 | 用途 | 现状 |
|------|------|------|
| pillow-jxl-plugin | JPEG XL (.jxl) 解码 | 无 cp312 轮，两平台均未装，.jxl 优雅缺席 |
| ImageMagick（系统程序，非 pip） | FITS / HDR / EXR / FLIF / PCD 等长尾格式预览兜底 | 可选；未装时这些格式无预览 |

**自实现无第三方依赖**：`core/zhvar.py`（繁简归一化，Unihan 数据 + 人工补充，
替代 GPLv2+ 的 zhconv）、开机自启（Windows 注册表 / Linux XDG autostart，均走标准库）。

**Python 版本约束**（按平台）：

| 平台 | Python | 说明 |
|------|--------|------|
| Windows 打包 | 3.12 | 官方 python.org / venv |
| 麒麟 / Linux ARM64 兼容包 | 3.9 | bullseye 底座（glibc 2.31）；代码已全量审计 3.9 兼容 |

## 二、系统级依赖（非 pip）—— 差异所在

### Windows x86_64

**无任何系统级依赖**：PyInstaller onedir 自带全部 DLL 与 PySide6 内置
WMF/ffmpeg 多媒体后端，解压即用。视频内嵌播放开箱可用。

### 银河麒麟桌面 V10 aarch64（Ubuntu 20.04 底座，glibc 2.31）

pip 依赖随包自带；以下**系统级库**需要目标机具备（桌面版默认全部自带，
仅极简/服务器环境可能需补）：

```bash
sudo apt-get install -y \
    libgl1 libegl1 libglib2.0-0 libfontconfig1 libfreetype6 libxkbcommon0 \
    libxcb1 libxcb-xkb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
    libdbus-1-3 libdouble-conversion3 libharfbuzz0b libpcre2-16-0 \
    fonts-noto-cjk
```

**可选系统组件**（缺失自动降级，不影响启动）：

| 组件 | 用途 | 缺失时的行为 |
|------|------|--------------|
| libpulse0 | 内嵌视频播放的音频 | 0.5.66 起视频播放器为懒加载：只禁用内嵌播放并回退系统播放器，**程序正常启动** |
| gstreamer | 视频播放后端 | 同上（内嵌播放不可用，回退系统播放器） |
| ImageMagick | 长尾 RAW 格式预览兜底 | 对应格式无预览 |

### Ubuntu aarch64（20.04 ~ 24.04）

与麒麟桌面 V10 同一兼容包（glibc 2.29 ≤ 系统底座 2.31/2.35/2.39），系统库同上。

### Ubuntu x86_64 及其他 x86 Linux

**暂无官方包**。需要时用同一 spec 在 x86_64 Linux + Python 3.9+ 环境执行
PyInstaller 即可（代码无架构相关逻辑）。

## 三、构建工具链差异（仅开发机需要）

| 平台 | 工具链 |
|------|--------|
| Windows | Python 3.12 venv + `PyInstaller --noconfirm photo_manager.spec`（含 .ver 版本信息）+ `tools/trim_package.py` |
| 麒麟 / Linux ARM64 | Docker `tools/arm/kylin.Dockerfile` → 镜像 `photo-build-arm64:kylin`（bullseye/glibc 2.31/py3.9）+ `python3.9 -m PyInstaller ... --distpath dist_arm_kylin` + `tools/trim_dist.py`；产物 `dist_arm_kylin/PhotoManager-kylin-aarch64-glibc231.tar.gz` |

⚠️ 构建镜像的 glibc 必须 ≤ 目标系统 glibc（GLIBC 符号向后不兼容）：
bullseye 2.31 → 覆盖麒麟桌面 V10；trixie 2.41 的产物只适配 Ubuntu 24.04+ 等新系统。
