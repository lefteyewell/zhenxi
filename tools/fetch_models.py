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
"""下载 AI 模型并校验（离线打包用）。

覆盖两类模型：
  1. 人脸模型（YuNet / SFace）：多源回退下载，sha256 校验
  2. CLIP 编码器 ×2 + 离线地理编码库 geo.sqlite：来自官方开源仓库的
     models-v1 Release（约 750MB，体积原因不入 git），sha256 校验

用法：python tools/fetch_models.py            # 全部下载（已存在的自动跳过）
     python tools/fetch_models.py --skip-release   # 只补人脸/OCR 模型
详细打包步骤见 docs/BUILDING.md。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"

MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "size": 232589,
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "urls": [
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://hf-mirror.com/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
        ],
    },
    "face_recognition_sface_2021dec.onnx": {
        "size": 38696353,
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "urls": [
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
            "https://hf-mirror.com/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
        ],
    },
}

# 大体积模型：来自开源仓库 models-v1 Release（不入 git，见 docs/BUILDING.md）
# sha256 与体积为发布时登记值，下载后强校验，防止镜像/截断导致的坏文件
RELEASE_REPO = "lefteyewell/zhenxi"
RELEASE_TAG = "models-v1"

RELEASE_ASSETS = {
    "clip/vit-b-16.img.fp32.onnx": {
        "size": 349217747,
        "sha256": "92b623429f2ee08dc20d2f7f64e930576b94a7db8c306950f67dc64d0b7c7dcf",
        "urls": [
            f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_TAG}/vit-b-16.img.fp32.onnx",
        ],
    },
    "clip/vit-b-16.txt.fp32.onnx": {
        "size": 411325342,
        "sha256": "7218d930ad4bac927331840716ea3bb25c9ba5e5477745546e86cd8b9d4e1712",
        "urls": [
            f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_TAG}/vit-b-16.txt.fp32.onnx",
        ],
    },
    "geo/geo.sqlite": {
        "size": 24440832,
        "sha256": "3b078b4d4498044faa96ec8da7c53e716d96318281195b5a82e1daee2b6747d4",
        "urls": [
            f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_TAG}/geo.sqlite",
        ],
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name: str, info: dict, out: Path) -> bool:
    tmp = out.with_suffix(".part")
    for url in info["urls"]:
        try:
            print(f"  下载 {name} <- {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "pm-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            got = sha256_of(tmp)
            if got == info["sha256"]:
                tmp.replace(out)
                print(f"  OK 校验通过 {out}")
                return True
            print(f"  校验失败: {got[:16]}... 换源")
        except Exception as e:
            print(f"  失败: {e}")
    tmp.unlink(missing_ok=True)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 AI 模型（人脸/CLIP/geo，带 sha256 校验）")
    ap.add_argument("--models", default=str(MODELS_DIR), help="模型输出目录（根）")
    ap.add_argument("--skip-release", action="store_true",
                    help="跳过 models-v1 大模型（CLIP/geo），只补人脸/OCR 模型")
    args = ap.parse_args()
    out_dir = Path(args.models)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    groups: list[dict] = [MODELS]
    if not args.skip_release:
        groups.append(RELEASE_ASSETS)
    for group in groups:
        for rel, info in group.items():
            out = out_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() and out.stat().st_size == info["size"] and sha256_of(out) == info["sha256"]:
                print(f"已存在且校验通过: {rel}")
                continue
            if not download(rel, info, out):
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
