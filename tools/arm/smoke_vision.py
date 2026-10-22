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
"""aarch64 视觉链路冒烟：YuNet 人脸检测 + SFace 特征提取（opencv + onnxruntime + 模型文件）"""
import os
import numpy as np
import cv2

MODEL_DIR = "/models"
IMG = "/data/face_test.jpg"

y = cv2.FaceDetectorYN_create(
    os.path.join(MODEL_DIR, "face_detection_yunet_2023mar.onnx"),
    "", (320, 320), 0.6, 0.3, 5000
)
s = cv2.FaceRecognizerSF_create(
    os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx"), ""
)

img = cv2.imread(IMG)
print("image:", img.shape)

faces = None
for _ in range(1):  # 固定尺度（冒烟用）
    h, w = img.shape[:2]
    y.setInputSize((w, h))
    _, faces = y.detect(img)
    if faces is not None:
        break

if faces is None or len(faces) == 0:
    print("NO FACE DETECTED")
    raise SystemExit(1)

print("faces detected:", len(faces))
box = faces[0]
face = s.alignCrop(img, box)
feat = s.feature(face)
print("descriptor:", feat.shape, "norm:", float(np.linalg.norm(feat)))
print("=== VISION SMOKE OK ===")
