# 阶段5 - aarch64 麒麟版打包镜像：PySide6 全栈 + PyInstaller
FROM photo-smoke-full:arm64

RUN apt-get update && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller==6.21.0

CMD ["echo", "photo-build-arm64:stage5 ready"]
