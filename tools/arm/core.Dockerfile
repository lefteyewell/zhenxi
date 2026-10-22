# 阶段0 - aarch64 依赖冒烟测试镜像（核心图像/AI 栈）
FROM docker.m.daocloud.io/library/python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libxcb-cursor0 libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    numpy opencv-python-headless rawpy onnxruntime Pillow exifread rapidocr-onnxruntime

RUN python - <<'EOF'
import numpy
import cv2
import rawpy
import onnxruntime
import PIL
import exifread
import rapidocr_onnxruntime
print("=== aarch64 core deps import test ===")
print("numpy      ", numpy.__version__)
print("opencv     ", cv2.__version__)
print("onnxruntime", onnxruntime.__version__)
print("Pillow     ", PIL.__version__)
print("rawpy      ", rawpy.__version__)
print("rapidocr   ", "ok")
print("=== ALL CORE IMPORTS OK ===")
EOF
