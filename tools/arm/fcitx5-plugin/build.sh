#!/bin/bash
# fcitx5 Qt6 输入上下文插件构建脚本（在 pm-kylin 容器内运行）
# 前置：/opt/qt6 = conda-forge qt6-main 6.8.0（含 private 头）
#       /build = 仓库 tools/arm/fcitx-build（源码与产物持久化）
set -e
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq g++ libxcb1-dev libxkbcommon-dev libx11-dev libgl1-mesa-dev >/dev/null 2>&1
pip install -q cmake ninja zstandard 2>&1 >/dev/null
export PATH=/opt/qt6/lib/qt6/bin:/opt/qt6/bin:$PATH
export LD_LIBRARY_PATH=/opt/qt6-deps/lib:/opt/qt6/lib

python - <<'PYEOF'
import urllib.request, json, zipfile, tarfile, io, os
UA = {"User-Agent": "Mozilla/5.0"}
def fetch(pkg, ver_prefix, subdir="linux-aarch64"):
    j = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.anaconda.org/package/conda-forge/" + pkg, headers=UA), timeout=60))
    cands = [f for f in j["files"] if subdir in f.get("attrs", {}).get("subdir", "")
             and str(f.get("version", "")).startswith(ver_prefix)
             and f["basename"].endswith(".conda")]
    if not cands:
        raise SystemExit("no %s %s for %s" % (pkg, ver_prefix, subdir))
    cands.sort(key=lambda f: f["version"], reverse=True)
    f = cands[0]
    base = os.path.basename(f["basename"])
    url = "https://anaconda.org/conda-forge/%s/%s/download/%s/%s" % (pkg, f["version"], subdir, base)
    print("GET", url, flush=True)
    open("/build/" + base, "wb").write(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=300).read())
    print("ok", base, flush=True)
for pkg, ver in [("icu", "75"), ("libstdcxx", ""), ("libgcc", "")]:
    fetch(pkg, ver)
print("all fetched", flush=True)
PYEOF

python - <<'PYEOF'
import zipfile, tarfile, io, glob, zstandard
for path in sorted(glob.glob("/build/icu-*.conda")) + sorted(glob.glob("/build/libstd*.conda")) + sorted(glob.glob("/build/libgcc*.conda")):
    z = zipfile.ZipFile(path)
    inner = [n for n in z.namelist() if n.startswith("pkg-")][0]
    dctx = zstandard.ZstdDecompressor()
    tf = tarfile.open(fileobj=dctx.stream_reader(io.BytesIO(z.read(inner))), mode="r:")
    tf.extractall("/opt/qt6-deps")
    print("extracted", path.split("/")[-1], flush=True)
PYEOF
ls /opt/qt6-deps/lib | grep -E "icui18n|libstdc" | head -4

rm -rf b-fcitx
cmake -S fcitx5-qt-5.1.16 -B b-fcitx -G Ninja \
  -DCMAKE_PREFIX_PATH=/opt/qt6 \
  -DQT_HOST_PATH=/opt/qt6 \
  -DENABLE_QT4=off -DENABLE_QT5=off -DENABLE_QT6=on \
  -DENABLE_QT6_WAYLAND_WORKAROUND=off \
  -DENABLE_X11=on \
  -DBUILD_ONLY_PLUGIN=on -DBUILD_STATIC_PLUGIN=off -DCMAKE_INSTALL_RPATH="\$ORIGIN" \
  -DWITH_FCITX_PLUGIN_NAME=on \
  -DBUILD_TESTING=off -DBUILD_DOCS=off \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/fcitx5-qt >/dev/null
echo "CONFIGURE_OK"
cmake --build b-fcitx 2>&1 | tail -2
cmake --install b-fcitx >/dev/null && echo "INSTALL_OK"
find /opt/fcitx5-qt -name "*.so*" 2>/dev/null
mkdir -p /build/artifacts
find /opt/fcitx5-qt -name "*.so*" -exec cp {} /build/artifacts/ \;
ls -la /build/artifacts
echo "BUILD_ALL_DONE"

# ============================================================================
# ⚠️ 安装位置（10-28 实测教训）：Qt 只扫描 _internal/PySide6/Qt/plugins/
# （Qt 官方布局，QT_DEBUG_PLUGINS 实证），不扫 _internal/PySide6/plugins/。
# PyInstaller 的 PySide6 hook 把 compose/ibus 等放两处，fcitx 插件必须放
# "Qt/plugins" 这一份，QT_DEBUG_PLUGINS=1 出现 "looking at libfcitx5..." 为准：
#   cp tools/arm/fcitx5-plugin/libfcitx5platforminputcontextplugin.so \
#      dist_arm/PhotoManager/_internal/PySide6/Qt/plugins/platforminputcontexts/
# ============================================================================
