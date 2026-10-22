# 阶段4 - aarch64 完整验收：项目代码挂载进容器，跑核心管线（ingest→faces→ocr→cluster→search→sync→dedupe→backup）
FROM docker.m.daocloud.io/library/python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libxcb-cursor0 libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    numpy opencv-python-headless rawpy onnxruntime Pillow exifread rapidocr-onnxruntime

WORKDIR /app
CMD ["python", "tools/arm/accept_arm.py"]
