# 麒麟兼容构建镜像：python:3.11-slim-bullseye = glibc 2.31 + Python 3.11
# 目标：银河麒麟桌面 V10（glibc 2.31）/ Ubuntu 20.04+ aarch64
#
# 历史教训：
#   1. debian:bullseye 官方源最高 python3.9，而 PySide6 自 6.9 起不再支持 3.9，
#      导致 CI 只能装 6.8.0.2，应用按 6.12 开发 → 真机启动即崩（运行无反应）。
#      修复：FROM 换 python:3.11-slim-bullseye（bullseye 底座 + 官方 Python 3.11）。
#   2. QtMultimedia 的 QML 插件依赖系统库 libnsl.so.2（麒麟 V10 无此库），
#      插件加载失败 → main.qml 的 VideoPlayerDialog/GalleryPage 类型不可用 → 秒退。
#      修复：镜像内预装 libnsl2 + gstreamer 全家桶，打包后由
#      tools/arm/bundle_runtime_libs.py 把闭包库收集进 _internal，
#      并把 gstreamer 插件复制到 _internal/gstreamer-1.0（main.py 启动时注入路径）。
#
# 用法（仓库根目录为构建上下文，需包含 requirements.txt）：
#   docker build --platform linux/arm64 --build-arg PIP_INDEX_URL=https://pypi.org/simple \
#     --build-arg PY_IMAGE=python:3.11-slim-bullseye \
#     -f tools/arm/kylin.Dockerfile -t pm-kylin .
#   docker run --rm --platform linux/arm64 -v <项目>:/work -w /work \
#     -u "$(id -u):$(id -g)" -e HOME=/tmp pm-kylin \
#     python -m PyInstaller --noconfirm --distpath dist_arm --workpath build_arm photo_manager.spec
#
# 本地（国内）构建可不传 PIP_INDEX_URL / PY_IMAGE，默认清华源 + daocloud 镜像。
ARG PY_IMAGE=docker.m.daocloud.io/library/python:3.11-slim-bullseye
FROM ${PY_IMAGE}

# CI（GitHub 海外机器）构建时用 --build-arg PIP_INDEX_URL=https://pypi.org/simple 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# bullseye 已归档（2026-08 EOL），用官方 archive.debian.org（http 免证书）
RUN printf 'deb http://archive.debian.org/debian bullseye main\ndeb http://archive.debian.org/debian-security bullseye-security main\n' > /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils \
    libgl1 libegl1 libbrotli1 libfontconfig1 libfreetype6 libxkbcommon0 \
    libxcb1 libxcb-xkb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
    libdbus-1-3 libdouble-conversion3 libharfbuzz0b libpng16-16 libmd4c0 \
    libgssapi-krb5-2 libpcre2-16-0 libpulse0 libglib2.0-0 \
    libnsl2 \
    libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    && rm -rf /var/lib/apt/lists/*

# 依赖版本由仓库根 requirements.txt 唯一约束（含 PySide6>=6.9.0）
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip -i ${PIP_INDEX_URL} \
    && python -m pip install --no-cache-dir \
       -i ${PIP_INDEX_URL} \
       -r /tmp/requirements.txt \
       "PyInstaller==6.21.0"

RUN ldd --version | head -1 \
    && python - <<'EOF'
import sys
print(sys.version)
import numpy, cv2, rawpy, onnxruntime, PIL, exifread, rapidocr_onnxruntime
import PySide6, PyInstaller
from PySide6.QtCore import qVersion
print("numpy      ", numpy.__version__)
print("opencv     ", cv2.__version__)
print("onnxruntime", onnxruntime.__version__)
print("Pillow     ", PIL.__version__)
print("PySide6    ", PySide6.__version__, "Qt", qVersion())
print("PyInstaller", PyInstaller.__version__)
print("ALL_KYLIN_DEPS_OK")
EOF
