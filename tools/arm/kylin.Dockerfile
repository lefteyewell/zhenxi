# 麒麟兼容构建镜像（0.5.66）：debian:bullseye = glibc 2.31
# 目标：银河麒麟桌面 V10（glibc 2.31）/ Ubuntu 20.04+ aarch64
# 用法：
#   docker build --platform linux/arm64 -f tools/arm/kylin.Dockerfile \
#     -t photo-build-arm64:kylin tools/arm
#   docker run --rm --platform linux/arm64 -v <项目>:/work -w /work \
#     photo-build-arm64:kylin bash tools/arm/build_kylin_compat.sh
FROM docker.m.daocloud.io/library/debian:bullseye

# CI（GitHub 海外机器）构建时用 --build-arg PIP_INDEX_URL=https://pypi.org/simple 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# bullseye 已归档（2026-08 EOL），用官方 archive.debian.org（http 免证书）
RUN printf 'deb http://archive.debian.org/debian bullseye main\ndeb http://archive.debian.org/debian-security bullseye-security main\n' > /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.9 python3-pip python3.9-dev binutils \
    libgl1 libegl1 libbrotli1 libfontconfig1 libfreetype6 libxkbcommon0 \
    libxcb1 libxcb-xkb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
    libdbus-1-3 libdouble-conversion3 libharfbuzz0b libpng16-16 libmd4c0 \
    libgssapi-krb5-2 libpcre2-16-0 libpulse0 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.9 -m pip install --no-cache-dir --upgrade pip -i ${PIP_INDEX_URL}

RUN python3.9 -m pip install --no-cache-dir \
    -i ${PIP_INDEX_URL} \
    "numpy<2.1" "Pillow" "piexif" "pillow-heif" "rawpy" "exifread" \
    "opencv-python-headless" "onnxruntime" "rapidocr-onnxruntime" \
    "PySide6" "PyInstaller==6.21.0"

RUN ldd --version | head -1 \
    && python3.9 - <<'EOF'
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
