# 阶段0 - aarch64 全依赖冒烟测试镜像（含 PySide6 图形栈）
FROM photo-smoke-core:arm64

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libegl1 libbrotli1 libfontconfig1 libfreetype6 libxkbcommon0 \
    libxcb1 libxcb-xkb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
    libdbus-1-3 libdouble-conversion3 libharfbuzz0b libpng16-16 libmd4c0 \
    libgssapi-krb5-2 libpcre2-16-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple PySide6

RUN QT_QPA_PLATFORM=offscreen python - <<'EOF'
from PySide6.QtCore import qVersion
from PySide6.QtQml import QQmlApplicationEngine
import PySide6.QtQuick
print("=== aarch64 GUI 栈导入测试 ===")
print("Qt        ", qVersion())
print("QtQml     ", "ok")
print("QtQuick   ", "ok")
print("=== ALL GUI IMPORTS OK ===")
EOF
