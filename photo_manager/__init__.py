"""照片管理系统"""

import os
import sys
from pathlib import Path

APP_NAME = "真昔"
APP_VERSION = "0.6.29"
# 0.6.28：指向「帮助 → 开源许可 (GPLv3)」（即随包 LICENSE 文件的查看入口）——
# 此前误写「见 帮助 → 关于」，而关于弹窗正是显示本串的地方，形成自我指向；
# 0.6.29 补：GPLv3 只在此处出现一次，担保行改为指引「帮助 → 开源许可」不再重复
APP_COPYRIGHT = "© 2026 蒙汗药 · 以 GNU GPLv3 授权发布"

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
