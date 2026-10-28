# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：照片管理系统（Windows x86_64）
# 体积裁剪：打包后运行 python tools/trim_dist.py（删除 Qt WebEngine/翻译/开发资源）
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH)

datas, binaries, hiddenimports = [], [], []
for pkg in ["PySide6", "rapidocr_onnxruntime"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 0.5.43：现代编解码（HEIC/AVIF/JXL）——收集 libheif / libjxl 二进制。
# 条件收集：构建机上没装该库也不影响打包（运行期对应格式优雅降级）。
for pkg in ["pillow_heif", "pillow_jxl_plugin"]:
    try:
        __import__(pkg)
    except Exception:
        continue
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 内置 QML 界面资源
datas += [("photo_manager/ui/qml", "photo_manager/ui/qml")]
datas += [("photo_manager/__init__.py", "photo_manager")]
# 许可证随包分发（GPLv3 要求；LGPL/组件署名见 THIRD-PARTY-NOTICES.md）
datas += [("LICENSE", "."), ("THIRD-PARTY-NOTICES.md", ".")]
datas += [("photo_manager/core/rapidocr_config.yaml", "photo_manager/core")]

# 人脸模型（YuNet + SFace，随包分发）
datas += [
    ("models/face_detection_yunet_2023mar.onnx", "models"),
    ("models/face_recognition_sface_2021dec.onnx", "models"),
]

# CLIP 语义模型（M1：图像+文本编码器，约 760MB）
# 延迟加载：仅在首次语义搜索/场景标签时载入，不影响启动速度。
for _f in sorted(os.listdir("models/clip")):
    datas += [(f"models/clip/{_f}", "models/clip")]

# 离线逆地理编码库（M2：约 24MB，由 tools/build_geo.py 生成）
# 只需成品 geo.sqlite；cities1000.zip / countryInfo.txt 等为构建输入，不随包分发。
datas += [("models/geo/geo.sqlite", "models/geo")]

a = Analysis(
    ["photo_manager/main.py"],
    pathex=[str(project)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["PySide6.QtQml", "PySide6.QtQuick"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# 0.5.66：Windows 版本信息（资源管理器右键 → 属性 → 详细信息）。
# 版权署名与 APP_COPYRIGHT 同源（蒙汗药）。
# 0.5.67：加平台守卫——win32.versioninfo 仅 Windows 存在，Linux/macOS 构建须跳过。
import os as _os
import re as _re

_app_ver = _re.search(
    r'APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"',
    (project / "photo_manager" / "__init__.py").read_text(encoding="utf-8"),
).group(1)

_exe_kwargs = {}
if _os.name == "nt":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringTable, StringStruct,
        VSVersionInfo, VarFileInfo, VarStruct,
    )

    _v1, v2, v3, v4 = (_app_ver.split(".") + ["0"])[:4]
    # PyInstaller 6.21：EXE(version=) 直接接受 VSVersionInfo 对象（经 versrsrc 注入 exe）
    _exe_kwargs["version"] = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=(int(_v1), int(v2), int(v3), int(v4)),
            prodvers=(int(_v1), int(v2), int(v3), int(v4)),
            mask=0x3F, flags=0x0, OS=0x40004,
            fileType=0x1, subtype=0x0, date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable("080404b0", [   # 简体中文 / Unicode
                    StringStruct("CompanyName", "蒙汗药"),
                    StringStruct("FileDescription", "真昔 · 照片管理系统"),
                    StringStruct("FileVersion", _app_ver),
                    StringStruct("InternalName", "PhotoManager"),
                    StringStruct("LegalCopyright", "Copyright (C) 2026 蒙汗药"),
                    StringStruct("OriginalFilename", "PhotoManager.exe"),
                    StringStruct("ProductName", "真昔"),
                    StringStruct("ProductVersion", _app_ver),
                ]),
            ]),
            VarFileInfo([VarStruct("Translation", [2052, 1200])]),
        ],
    )

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhotoManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    **_exe_kwargs,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PhotoManager",
)
