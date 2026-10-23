"""真昔（照片管理系统）- 应用入口"""

from __future__ import annotations

from photo_manager.i18n import t as _tr
import multiprocessing
import os
import sys
from pathlib import Path

# Linux 打包版：若随包分发了 gstreamer 运行库（_internal/gstreamer-1.0），
# 在 Qt 初始化前注入插件搜索路径，保证视频内嵌播放不依赖目标机的系统组件。
if sys.platform.startswith("linux"):
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass:
        _gst_dir = Path(_meipass) / "gstreamer-1.0"
        if _gst_dir.is_dir():
            os.environ.setdefault("GST_PLUGIN_SYSTEM_PATH", str(_gst_dir))

from PySide6.QtCore import QLockFile, QObject, QCoreApplication, QStandardPaths, QUrl, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QMenu

try:  # Qt6 起 QSystemTrayIcon 在 QtGui；个别构建可能在 QtWidgets
    from PySide6.QtGui import QSystemTrayIcon
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtQml import QQmlApplicationEngine

from photo_manager import APP_NAME, APP_VERSION, APP_COPYRIGHT, QML_DIR
from photo_manager.ui.bridge import ThemeController
from photo_manager.ui.library_bridge import LibraryBridge


def _app_icon() -> QIcon:
    """运行时绘制应用/托盘图标（相机意象），避免依赖外部图片资源。"""
    px = QPixmap(64, 64)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    body = QPainterPath()
    body.addRoundedRect(2.0, 8.0, 60.0, 48.0, 10.0, 10.0)
    grad = QLinearGradient(0, 0, 0, 64)
    grad.setColorAt(0.0, QColor("#5B9BF8"))
    grad.setColorAt(1.0, QColor("#2E5FD9"))
    p.fillPath(body, grad)
    p.setPen(QColor(255, 255, 255, 0))
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(22.0, 22.0, 20.0, 20.0)          # 镜头外圈
    p.setBrush(QColor("#2E5FD9"))
    p.drawEllipse(28.0, 28.0, 8.0, 8.0)            # 镜头内芯
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(24.0, 4.0, 16.0, 8.0, 2.0, 2.0)  # 取景器凸起
    p.end()
    return QIcon(px)


class TrayController(QObject):
    """0.5.48：系统托盘常驻。关闭窗口→隐藏到托盘；托盘双击/右键恢复，右键可退出。

    系统托盘不可用（无头/部分 Linux WM）时 trayActive() 返回 False，
    QML 的 onClosing 拦截自动失效——窗口照常关闭，绝不出现「隐形应用」。
    """

    def __init__(self, bridge: LibraryBridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._window = None
        self._quitting = False
        self._tray = None
        bridge.trayEnabledChanged.connect(self._on_setting_changed)

    # ---------- QML 可调用 ----------
    @Slot(result=bool)
    def trayActive(self) -> bool:
        return (self._tray is not None and self._tray.isVisible()
                and self._bridge.trayEnabled())

    @Slot(result=bool)
    def quitting(self) -> bool:
        return self._quitting

    @Slot()
    def showMainWindow(self) -> None:
        w = self._window
        if w is None:
            return
        w.show()
        w.showNormal()
        w.raise_()
        w.requestActivate()

    @Slot()
    def notifyHidden(self) -> None:
        if self._tray is not None:
            self._tray.showMessage(APP_NAME, _tr("已最小化到托盘，双击图标恢复窗口"),
                                   3000)

    @Slot()
    def requestQuit(self) -> None:
        self._quitting = True
        if self._tray is not None:
            self._tray.hide()
        # 走窗口关闭流程而非直接 app.quit()：让 QML onClosing 里的
        # 「退出自动备份」照常执行（ quitting() 为 True，托盘拦截自动让路）
        w = self._window
        if w is not None:
            w.close()
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ---------- 生命周期 ----------
    def bind(self, window) -> None:
        """engine.load 后调用：绑定主窗口并按当前设置创建托盘。"""
        self._window = window
        if self._bridge.trayEnabled():
            self._setup_tray()

    def _on_setting_changed(self, on: bool) -> None:
        if on:
            self._setup_tray()
        elif self._tray is not None:
            self._tray.hide()
            self._tray = None

    def _setup_tray(self) -> None:
        if self._tray is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._bridge.message.emit(
                _tr("系统托盘不可用：关闭窗口将直接退出（可在设置中关闭「最小化到托盘」）"))
            return
        tray = QSystemTrayIcon(_app_icon(), self)
        menu = QMenu()
        act_show = menu.addAction(_tr("显示主窗口"))
        act_show.triggered.connect(self.showMainWindow)
        menu.addSeparator()
        act_quit = menu.addAction(_tr("退出"))
        act_quit.triggered.connect(self.requestQuit)
        tray.setContextMenu(menu)
        tray.setToolTip(APP_NAME)
        tray.activated.connect(self._on_activated)
        tray.show()
        self._tray = tray

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.showMainWindow()

def default_db_path() -> str:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base / "data" / "library.db")


def acquire_single_instance() -> QLockFile | None:
    """单实例锁：已在运行时直接返回 None（调用方应退出）。

    Windows 打包后 exe 位于用户目录下，锁文件写入系统用户数据目录，
    避免程序目录只读导致锁创建失败。
    """
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir / "photo_manager.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return None
    return lock


# 0.5.51：单实例唤醒通道名（托盘常驻 + 开机自启场景下，用户再次双击
# 图标/ exe 时，第二个实例不发一声就退出，而是通知已运行的实例把窗口
# 显示出来——此前第二个实例只会打印一行控制台（GUI 用户完全无感）。
_WAKE_SERVER = "PhotoManager-Wake"
# 持有已发送的客户端连接：Windows 命名管道上，客户端连接被 GC 销毁时可能
# 把服务端还没读走的缓冲数据一起丢弃（实测 readyRead=False, data=b''）。
# 进程内最多留存个位数连接，无泄漏顾虑。
_WAKE_SOCKS: list = []


def _wake_existing_instance() -> bool:
    """尝试连接已在运行的实例并发送「显示窗口」；成功返回 True。"""
    sock = QLocalSocket()
    sock.connectToServer(_WAKE_SERVER)
    if not sock.waitForConnected(300):
        sock.abort()
        return False
    sock.write(b"show")
    sock.flush()
    sock.waitForBytesWritten(300)
    # 等服务端读完主动断开（服务端读毕会 disconnectFromServer）；超时则
    # 保持连接存活（下方模块级持有），数据留在管道里由服务端稍后读取。
    sock.waitForDisconnected(500)
    _WAKE_SOCKS.append(sock)
    return True


def _listen_for_wake(on_show) -> QLocalServer | None:
    """首个实例：监听唤醒请求（on_show 被调用时显示主窗口）。

    清理可能残留的旧服务名（上次异常退出未清理）；listen 失败（极罕见
    的竞态）时返回 None，调用方按无双实例保护继续运行（功能不受影响）。
    """
    QLocalServer.removeServer(_WAKE_SERVER)
    server = QLocalServer()
    if not server.listen(_WAKE_SERVER):
        return None

    def _on_new():
        conn = server.nextPendingConnection()
        while conn is not None:
            try:
                conn.waitForReadyRead(200)
                if bytes(conn.readAll()).startswith(b"show"):
                    on_show()
            except Exception:
                pass
            finally:
                try:
                    conn.disconnectFromServer()
                except Exception:
                    pass
                conn.deleteLater()
                conn = server.nextPendingConnection()

    server.newConnection.connect(_on_new)
    return server


def _run_scheduled(db_path: str) -> int:
    """0.5.51 路线 B：OS 级定时调度入口（无窗口跑完即退）。

    Windows 任务计划 / 麒麟 systemd --user timer 到点唤起
    `PhotoManager.exe --scheduled-run`：按设置执行「检查照片文件夹」+
    「智能分析」，干完即退——不常驻内存（CLIP 模型随进程退出释放）。
    与 GUI 实例互斥：程序已在运行时跳过本次（避免并发写库）。
    """
    from PySide6.QtCore import QEventLoop, QTimer

    lock = acquire_single_instance()
    if lock is None:
        print("[scheduled-run] 程序已在运行，跳过本次")
        return 0
    bridge = LibraryBridge(db_path)
    bridge.message.connect(lambda m: print("[scheduled-run]", m))
    do_check = bridge.scheduleCheckEnabled()
    do_analyze = bridge.scheduleAnalyzeEnabled()
    if not (do_check or do_analyze):
        print("[scheduled-run] 未勾选执行项，退出")
        bridge.close()
        lock.unlock()
        return 0
    print(f"[scheduled-run] 开始 check={do_check} analyze={do_analyze}")
    if do_check:
        bridge.folderCheck(analyze_after=do_analyze)
    else:
        bridge.autoAnalyze()
    loop = QEventLoop()

    def _poll():
        if bridge._busy <= 0:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(_poll)
    timer.start(1000)
    QTimer.singleShot(4 * 3600 * 1000, loop.quit)  # 安全上限 4 小时
    loop.exec()
    bridge.close()
    lock.unlock()
    print("[scheduled-run] 完成")
    return 0


def main() -> int:
    # 0.5.58：PyInstaller 打包下 multiprocessing 子进程入口必须先走 freeze_support
    # （clip 编码已改为 spawn 子进程执行，规避 Qt 环境后台线程 native 崩溃）
    import multiprocessing as _mp

    _mp.freeze_support()

    QCoreApplication.setOrganizationName("PhotoManager")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(APP_VERSION)

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")

    smoke = "--smoke" in sys.argv
    scheduled = "--scheduled-run" in sys.argv
    db_path = os.environ.get("PM_DB", default_db_path())

    # 0.5.58：clip 编码子进程入口（无 Qt 进程，规避 Qt 环境后台线程 native 崩溃）。
    # 须在 QApplication 创建之前处理，跑完即退。
    if "--clip-worker" in sys.argv:
        from photo_manager.core.clip import cli_worker_main

        return cli_worker_main(sys.argv)
    # 无头定时运行：Linux 无显示环境时强制 offscreen（须在 QApplication 前设）
    if scheduled and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication(sys.argv)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(_app_icon())

    if scheduled:
        # 0.5.51 路线 B：OS 级调度到点唤起，跑完即退（不进 GUI/托盘/唤醒逻辑）
        return _run_scheduled(db_path)

    if not smoke:
        # 0.5.51：已是运行中的实例 → 发唤醒信号后退出（不再静默）
        if _wake_existing_instance():
            return 0
        lock = acquire_single_instance()
        if lock is None:
            # 锁被占但唤醒通道没响应（极端竞态）：按老逻辑退出
            print("真昔已在运行，请勿重复打开。")
            return 0
    else:
        lock = None

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))

    theme = ThemeController()
    engine.rootContext().setContextProperty("ThemeController", theme)

    engine.rootContext().setContextProperty("AppName", APP_NAME)
    engine.rootContext().setContextProperty("AppVersion", APP_VERSION)
    engine.rootContext().setContextProperty("AppCopyright", APP_COPYRIGHT)

    bridge = LibraryBridge(db_path)
    bridge.start_scheduler()
    engine.rootContext().setContextProperty("LibraryBridge", bridge)

    # 0.5.48：托盘常驻控制器（须在 load 前注入；窗口在 load 后 bind）
    tray = TrayController(bridge)
    engine.rootContext().setContextProperty("TrayHelper", tray)

    # 0.5.51：监听后续实例的唤醒请求（第二个实例启动时通知本实例显示窗口）
    wake_server = None
    if not smoke:
        wake_server = _listen_for_wake(tray.showMainWindow)

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "main.qml")))
    if not engine.rootObjects():
        return 1
    # QML 选择器/目录树的导入信号直连 Python（QML→Python 方法调用会被静默丢弃）
    bridge.attachQmlSignals(engine.rootObjects()[0])
    tray.bind(engine.rootObjects()[0])

    if smoke:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1500, app.quit)

    ret = app.exec()
    bridge.close()
    if lock is not None:
        lock.unlock()
    if wake_server is not None:
        wake_server.close()
    return ret


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
