"""照片管理系统"""

import os
import sys
from pathlib import Path

APP_NAME = "真昔"
APP_VERSION = "0.6.13"
APP_COPYRIGHT = "© 2026 蒙汗药 · 基于 GNU GPLv3 许可（见 帮助 → 关于）"

PACKAGE_DIR = Path(__file__).resolve().parent
QML_DIR = PACKAGE_DIR / "ui" / "qml"


def models_dir() -> str:
    """定位 AI 模型目录（人脸 detector/recognizer + OCR）。

    开发环境：项目根 /models；PyInstaller 打包后：_internal/models。
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return str(base / "models")
    over = os.environ.get("PM_MODELS")
    if over:
        return over
    return str(PACKAGE_DIR.parent / "models")
