# 阶段 0 验收报告 — 构建环境 / 多架构验证 / 项目骨架

日期：2026-08-01 ｜ 项目：照片管理系统（离线 · 双平台：Windows x86_64 + 麒麟 ARM64）

## 一、总体结论

阶段 0 全部 10 项待办完成。开发环境、项目骨架、Windows 打包流水线、测试图集、WSL2 + Docker
多架构验证均已跑通。**ARM64 全依赖栈（含 PySide6 GUI、opencv、onnxruntime、rawpy、OCR）已在
Docker 模拟环境下验证可运行，人脸检测/识别模型在 aarch64 上实测输出正常。**

## 二、完成项明细

| # | 待办 | 状态 | 说明 |
|---|------|------|------|
| 1 | 环境基线 | ✅ | Windows 10 22H2 (19045.6466)，虚拟化开启，联网正常 |
| 2 | 项目骨架 + git | ✅ | 首次提交 862373a；`photo_manager/` + `tests/` + `tools/` |
| 3 | venv 依赖 | ✅ | Python 3.12.5，requirements.txt 锁定 |
| 4 | QML 三栏主窗口 + 8 套主题 | ✅ | 修复 `onPrimary` 保留名冲突 → `textOnPrimary`；`tests/smoke_ui.py` 通过 |
| 5 | Windows 打包流水线 | ✅ | PyInstaller 6.21.0 → `dist\PhotoManager\PhotoManager.exe`（656MB，--smoke 自检通过）；`tools/build_win.ps1` |
| 6 | 测试图集 | ✅ | `tools/gen_test_images.py`：96 张（4 事件/8 相机/横幅文字/简笔人脸/GPS），EXIF 完整 |
| 7 | WSL2 | ✅ | Ubuntu 22.04 导入（TUNA rootfs，`wsl --import`），内核 2.7.11 |
| 8 | Docker Desktop | ✅ | 29.6.2，`--backend=wsl-2` 启动，引擎就绪 |
| 9 | ARM 模拟冒烟 | ✅ | `docker run --platform linux/arm64 alpine uname -a` → `aarch64 Linux` |
| 10 | ARM 全依赖冒烟 | ✅ | 见下节 |

## 三、ARM64 验证详情（重点）

### 3.1 镜像构建（QEMU 模拟，全部走国内镜像源）

- `photo-smoke-core:arm64`（1.04GB）：python:3.11-slim + numpy / opencv-python-headless / rawpy /
  onnxruntime / Pillow / exifread / rapidocr-onnxruntime，导入测试全部通过。
- `photo-smoke-full:arm64`（1.99GB）：+ PySide6 全量，offscreen 模式 QtQml/QtQuick 导入通过。

踩坑记录：
- `cv2` 导入报 `libxcb.so.1` 缺失 → 补装系统库 `libgl1 libglib2.0-0 libxcb* libxkbcommon*`。
- PySide6 导入报 `libbrotlidec.so.1` 缺失 → 补装 Qt 运行库（brotli/fontconfig/freetype/dbus 等 20 个）。
- Docker Hub 直连超时 → 全部镜像使用前缀 `docker.m.daocloud.io/`；pip 用 TUNA 源。
- `~/.docker/config.json` 首次写入带 BOM 导致 Docker 解析失败 → 用 .NET WriteAllText 无 BOM 重写。

### 3.2 人脸视觉链路实测（aarch64 容器内）

输入：`tools/arm/face_test.jpg`（3000×4000，测试图集 _MG_4000.JPG，含 1 张简笔人脸）
模型：YuNet `face_detection_yunet_2023mar.onnx`（227KB）+ SFace `face_recognition_sface_2021dec.onnx`（36.9MB）

结果：
```
image: (3000, 4000, 3)
faces detected: 1
descriptor: (1, 128) norm: 3.73
=== VISION SMOKE OK ===
```

模型下载坑：opencv_zoo 仓库用 Git LFS 管理模型，`raw.githubusercontent.com` 返回的是 **LFS 指针文件**
（131 字节），需改用 `media.githubusercontent.com/media/...` 或 HuggingFace 镜像（`hf-mirror.com/opencv/...`）
下载真实文件。

## 四、环境要点备忘

- Docker CLI PATH：`$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"`
- Docker 引擎启动：`Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`（约 40s 就绪）
- Docker Hub 不可直连 → 任何 `FROM`/`docker run` 镜像名加前缀 `docker.m.daocloud.io/`
- 提权脚本：`Start-Process powershell -Verb RunAs -ArgumentList '...','-File','"<含空格路径>"'`
- PowerShell 脚本须带 UTF-8 BOM，Dockerfile/heredoc 内脚本用英文
- 备选 ARM 验证路径：WSL2 内已装 `qemu-user-static`（若 Docker 模拟失效可切换）

## 五、遗留与后续建议（阶段 1 输入）

1. 麒麟 ARM64 目标机验证仍未在真机进行（受限于无目标机）；Docker 模拟 + qemu 结果作为先行验证，
   建议后续在麒麟 aarch64 真机上以同版本依赖跑同一套 `tools/arm/smoke_vision.py`。
2. 离线安装策略：锁定 ARM64 wheel 清单并预下载到交付介质（pip download -d packages/ --platform manylinux2014_aarch64），
   避免目标机 pip 联网。
3. 模型文件不入库（37MB，.gitignore 已排除），由 `tools/arm/fetch_models.ps1` 类脚本统一拉取 + 校验 sha256。
4. opencv-python-headless 4.12+ 与 opencv-zoo 模型兼容性需在阶段 1 人脸管线联调时复核。
5. 打包体积优化（PySide6 裁剪、Qt 翻译/示例剔除）留待阶段 1。

## 六、验收标准对照

| 标准 | 结果 |
|------|------|
| WSL2 可用（功能正常 + 发行版导入） | ✅ Ubuntu 22.04 运行中 |
| Docker Desktop 引擎就绪 | ✅ 29.6.2，wsl-2 后端 |
| ARM64 模拟运行容器 | ✅ alpine aarch64 uname 验证 |
| ARM64 核心依赖（cv/onnx/rawpy/ocr/PIL）导入 | ✅ 全部通过 |
| ARM64 GUI 栈（PySide6 QML） | ✅ offscreen 导入通过 |
| ARM64 人脸模型推理 | ✅ 检测 1 脸 + 128 维特征 |
| Windows 打包产物自检 | ✅ PhotoManager.exe --smoke |
| 测试图集完整 | ✅ 96 张，EXIF 可读 |

**阶段 0 验收：通过。**
