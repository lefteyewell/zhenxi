# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")

from PySide6.QtCore import QObject, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtCore import QPointF, QPoint, Qt

app = QGuiApplication(sys.argv)
tmp = tempfile.mkdtemp(prefix="repro_bk_")
os.environ["PM_DB"] = os.path.join(tmp, "x.db")
os.environ["PM_THUMBS"] = os.path.join(tmp, "thumbs")

from photo_manager.ui.library_bridge import LibraryBridge
from photo_manager.ui.bridge import ThemeController

gui_bridge = LibraryBridge(os.environ["PM_DB"])
engine = QQmlApplicationEngine()
QML_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "photo_manager", "ui", "qml"))
engine.addImportPath(QML_DIR)
engine.rootContext().setContextProperty("ThemeController", ThemeController())
from photo_manager import APP_NAME, APP_VERSION, APP_COPYRIGHT
engine.rootContext().setContextProperty("AppName", APP_NAME)
engine.rootContext().setContextProperty("AppVersion", APP_VERSION)
engine.rootContext().setContextProperty("AppCopyright", APP_COPYRIGHT)
engine.rootContext().setContextProperty("LibraryBridge", gui_bridge)
engine.load(QUrl.fromLocalFile(os.path.join(QML_DIR, "main.qml")))
root = engine.rootObjects()[0]
win = root
print("LOADED")

bk = root.findChild(QObject, "backupPicker")
print("backupPicker found:", bk is not None)
bk.setProperty("currentPath", tmp)
ok_btn = bk.findChild(QQuickItem, "pickerOk")
mo = ok_btn.metaObject()
print("hasClick:", mo.indexOfMethod("click()") >= 0)
mo.invokeMethod(ok_btn, "click")

before = set(os.listdir(tmp))
for _ in range(50):
    new = [f for f in os.listdir(tmp) if f.startswith("library_") and f.endswith(".db")]
    if new:
        print("BACKUP OK:", new)
        break
    from PySide6.QtTest import QTest
    QTest.qWait(100)
else:
    print("BACKUP FAILED. tmp contents:", os.listdir(tmp))

QTimer.singleShot(300, app.quit)
app.exec()
