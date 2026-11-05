# 打包指南（三平台从源码构建）

本文说明如何从源码复现与官方 Release 相同的安装包。
`.github/workflows/release.yml`（CI）执行的正是本文的命令——**照抄即可得到可用产物**。

| 平台 | 产物 | 难度 |
|---|---|---|
| Windows x86_64 | `PhotoManager-<版本>-win64.zip` | ★ 最简单，一台装好 Python 的电脑即可 |
| Linux x86_64 | `PhotoManager-<版本>-linux64.tar.gz` | ★★ 需要 Ubuntu 22.04+ 与若干 Qt 系统库 |
| 银河麒麟 V10 aarch64 | `PhotoManager-<版本>-kylin-aarch64.tar.gz` | ★★★ 需要 Docker（qemu 模拟 arm64，构建慢属正常） |

## 0. 公共前置：模型准备（一键）

除仓库内置的人脸模型（YuNet / SFace）外，还需 3 个大文件（合计约 750MB，
因体积原因不入 git，托管在公开 Release [models-v1](https://github.com/lefteyewell/zhenxi/releases/tag/models-v1)）：

```bash
python tools/fetch_models.py
```

脚本自动下载并做 sha256 校验：人脸模型 ×2（多源回退）、CLIP 图像/文本编码器、
离线地理编码库 geo.sqlite。放置路径：

```
models/
├── face_detection_yunet_2023mar.onnx     # 仓库已内置
├── face_recognition_sface_2021dec.onnx   # 仓库已内置
├── clip/
│   ├── vit-b-16.img.fp32.onnx            # ~334MB ← models-v1
│   ├── vit-b-16.txt.fp32.onnx            # ~393MB ← models-v1
│   └── (config.json / vocab.txt 等仓库已内置)
└── geo/
    └── geo.sqlite                        # ~24MB ← models-v1
```

也可手动从 models-v1 页面下载后放入对应目录（脚本会校验失败即报错，不会装错文件）。

## 1. Windows x86_64

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tools\fetch_models.py
python tools\build_win.ps1        # 1) 装 PyInstaller 2) 按 photo_manager.spec 打包 3) --smoke 自检
```

产物：`dist\PhotoManager\`（解压即用目录）。对外分发前可选裁剪：

```powershell
python tools\trim_package.py dist\PhotoManager   # 只裁 Qt 运行时，勿动 models/
```

⚠️ 若 `dist\PhotoManager\` 里已有旧包的 `data\`（用户真实照片库），重新打包前先把它迁出，打完再放回。

## 2. Linux x86_64（Ubuntu 22.04 或更新）

```bash
# Qt 运行系统库（与 CI 一致）
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
  libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1

python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pyinstaller==6.21.0
python tools/fetch_models.py
python -m PyInstaller --noconfirm photo_manager.spec
python tools/trim_dist.py dist/PhotoManager
# 冒烟自检（可选）
QT_QPA_PLATFORM=offscreen ./dist/PhotoManager/PhotoManager --smoke
# 打 tar 前清除冒烟生成的 data/，然后打包
rm -rf dist/PhotoManager/data
tar -czf PhotoManager-linux64.tar.gz -C dist PhotoManager
```

## 3. 银河麒麟 V10（aarch64 / 飞腾·鲲鹏）

无需 aarch64 真机：任意装了 Docker 的 x86_64 机器（Linux / macOS / Windows + WSL2）
都能交叉构建，Docker 通过 qemu 模拟 arm64。**qemu 下整包构建需数小时，属正常现象。**

以下命令与 CI 完全一致，在**仓库根目录**执行：

### 3.1 构建镜像（glibc 2.31 底座，麒麟兼容关键）

```bash
docker build --platform linux/arm64 \
  --build-arg PY_IMAGE=python:3.11-slim-bullseye \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple \
  -f tools/arm/kylin.Dockerfile -t pm-kylin .
```

- 底座必须是 **bullseye（glibc 2.31）**——麒麟 V10 的 glibc 上限。用更新的发行版底座
  会产出要求 GLIBC_2.34+ 的包，真机直接无法运行（历史事故）。
- 国内网络可省略两个 `--build-arg`（Dockerfile 默认清华 pip 源 + daocloud 镜像）。

### 3.2 容器内 PyInstaller 打包

```bash
docker run --rm --platform linux/arm64 \
  -v "$PWD":/work -w /work \
  -u "$(id -u):$(id -g)" -e HOME=/tmp \
  pm-kylin bash -c '
    set -e
    python -m PyInstaller --noconfirm \
      --distpath dist_arm --workpath build_arm \
      photo_manager.spec
    python tools/trim_dist.py dist_arm/PhotoManager
  '
```

### 3.3 收集运行库闭包 + gstreamer + fcitx 插件（勿跳过！）

```bash
docker run --rm --platform linux/arm64 \
  -v "$PWD":/work -w /work \
  pm-kylin bash -c '
    set -e
    mkdir -p dist_arm/PhotoManager/_internal/gstreamer-1.0
    cp /usr/lib/*/gstreamer-1.0/*.so dist_arm/PhotoManager/_internal/gstreamer-1.0/ || true
    IME_DEST=dist_arm/PhotoManager/_internal/PySide6/Qt/plugins/platforminputcontexts
    mkdir -p "$IME_DEST"
    cp tools/arm/fcitx5-plugin/libfcitx5platforminputcontextplugin.so "$IME_DEST/"
    test -f "$IME_DEST/libfcitx5platforminputcontextplugin.so" || { echo "fcitx 插件未入包"; exit 1; }
    python tools/arm/bundle_runtime_libs.py dist_arm/PhotoManager/_internal
    test -f dist_arm/PhotoManager/_internal/libnsl.so.2 || { echo "libnsl.so.2 未打包"; exit 1; }
  '
```

缺此步的包在麒麟真机会**启动即崩**：麒麟 V10 没有 libnsl.so.2 与 gstreamer，
QtMultimedia 插件加载失败会导致 QML 类型不可用（历史事故，勿重蹈）。

### 3.4 冒烟自检 + GLIBC 出货预检

```bash
# 冒烟：offscreen 启动全部 QML，启动即崩将在此暴露
docker run --rm --platform linux/arm64 \
  -v "$PWD":/work -w /work/dist_arm/PhotoManager \
  -u "$(id -u):$(id -g)" -e HOME=/tmp \
  -e QT_QPA_PLATFORM=offscreen \
  pm-kylin bash -c 'timeout 600 ./PhotoManager --smoke && echo SMOKE_OK'

# GLIBC 预检：核心库版本要求必须 ≤ 2.31（显式保险丝）
docker run --rm --platform linux/arm64 \
  -v "$PWD":/work -w /work/dist_arm/PhotoManager \
  pm-kylin bash -c '
    set -e
    for f in _internal/PySide6/QtCore.abi3.so _internal/PySide6/QtQml.abi3.so \
             _internal/libxkbcommon.so.0 _internal/libnsl.so.2; do
      v=$(grep -aoE "GLIBC_[0-9.]+" "$f" | sort -Vu | tail -1)
      echo "$f: $v"
      req=${v#GLIBC_}
      if [ "$(printf "2.31\n%s\n" "$req" | sort -V | tail -1)" != "2.31" ]; then
        echo "GLIBC 超限：$f 要求 $v（> 2.31）"; exit 1
      fi
    done
    echo GLIBC_PRECHECK_OK
  '
```

### 3.5 打 tar 包（必须在容器内打！）

```bash
docker run --rm --platform linux/arm64 \
  -v "$PWD":/work -w /work \
  pm-kylin bash -c '
    rm -rf dist_arm/PhotoManager/data
    VER=$(grep -aoE "APP_VERSION = \"[^\"]+\"" photo_manager/__init__.py | cut -d\" -f2)
    tar -czf "dist_arm/PhotoManager-${VER}-kylin-aarch64.tar.gz" -C dist_arm PhotoManager
  '
```

⚠️ 在 Windows 宿主机直接 tar 会丢失可执行权限位（NTFS 无 x 位），解压后主程序无法运行，
必须**容器内打包**（产物 root:root rwxr-xr-x，麒麟上开箱即用）。

## Legacy：不要用这些出货行

以下为早期方案，**缺少 gstreamer/libnsl 闭包收集、fcitx 插件、GLIBC 预检**等关键步骤，
按它们打出的包在麒麟真机会崩溃，仅作历史参考：

- `tools/arm/build_kylin.sh`
- `tools/setup_docker.ps1` / `tools/setup_wsl*.ps1`

## 常见坑速查

| 坑 | 结论 |
|---|---|
| 重建前 `dist/PhotoManager/data/` | 用户真实照片库，先迁出、打完放回 |
| PyInstaller 版本 | 锁 `6.21.0`，与 spec/CI 一致 |
| 麒麟底座 | 必须 bullseye / glibc ≤ 2.31，出货前跑 3.4 的预检 |
| Windows 侧打麒麟 tar | 丢执行位 → 必须容器内打 |
| 打 tar 前的 `data/` | 冒烟自检会生成测试库与日志，打 tar 前删除 |
| CLIP 模型 | 随包分发（spec 已含 models/clip），不要裁掉 |
