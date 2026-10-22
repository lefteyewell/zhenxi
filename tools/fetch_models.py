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
"""下载人脸/OCR 模型并校验 sha256（离线打包用）。"""
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
    ap = argparse.ArgumentParser(description="下载 AI 模型（带 sha256 校验与镜像回退）")
    ap.add_argument("--models", default=str(MODELS_DIR), help="模型输出目录")
    args = ap.parse_args()
    out_dir = Path(args.models)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, info in MODELS.items():
        out = out_dir / name
        if out.exists() and out.stat().st_size == info["size"] and sha256_of(out) == info["sha256"]:
            print(f"已存在且校验通过: {name}")
            continue
        if not download(name, info, out):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
