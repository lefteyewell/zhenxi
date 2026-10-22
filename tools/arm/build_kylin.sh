#!/usr/bin/env bash
# 银河麒麟 V10 aarch64 打包脚本
#
# 用途：在麒麟 aarch64 真机（或 aarch64 容器）内一键产出
#       dist_arm/PhotoManager-kylin-aarch64.tar.gz
#
# 用法：
#   bash tools/arm/build_kylin.sh
#
# 说明：
#   - Windows x86_64 无法交叉编译出 aarch64 产物（PyInstaller 不支持），
#     本脚本必须在 aarch64 环境内执行。
#   - 复用根目录的 photo_manager.spec（与 Windows 版同一份，无平台相关配置）。
#   - 如需在容器内构建，先准备含 PySide6 全栈 + pyinstaller 的 aarch64 镜像
#     （参见 tools/arm/stage5.Dockerfile），再把项目挂载进去执行本脚本。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
echo "项目根目录: $ROOT"

DIST_DIR="${DIST_DIR:-dist_arm}"
WORK_DIR="${WORK_DIR:-build_arm}"
VENV="${VENV:-.venv_arm}"

echo "=== [1/5] 准备虚拟环境 ($VENV) ==="
if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

echo "=== [2/5] 安装依赖 ==="
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pyinstaller

echo "=== [3/5] PyInstaller 打包 (aarch64) ==="
rm -rf "$DIST_DIR/PhotoManager"
python -m PyInstaller --noconfirm --clean \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    photo_manager.spec

echo "=== [4/5] 体积裁剪 + 冒烟自检 ==="
python tools/trim_dist.py "$DIST_DIR/PhotoManager"
QT_QPA_PLATFORM=offscreen "$DIST_DIR/PhotoManager/PhotoManager" --smoke

echo "=== [5/5] 打成 tar.gz ==="
tar -czf "$DIST_DIR/PhotoManager-kylin-aarch64.tar.gz" -C "$DIST_DIR" PhotoManager
SIZE="$(du -sm "$DIST_DIR/PhotoManager" | cut -f1)"
echo "=== 打包完成 ==="
echo "产物: $DIST_DIR/PhotoManager-kylin-aarch64.tar.gz (解压约 ${SIZE}MB)"
