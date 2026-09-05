from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import tempfile

import cv2
import numpy as np

from .config import Settings


@dataclass(slots=True)
class QualityResult:
    ok: bool
    face_count: int
    brightness: float
    blur_score: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class QualityInspector:
    def __init__(self, settings: Settings):
        self.settings = settings
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        # OpenCV Windows 的 CascadeClassifier 无法打开含中文的安装路径，复制到纯 ASCII 临时路径。
        if any(ord(character) > 127 for character in str(cascade_path)):
            safe_path = Path(tempfile.gettempdir()) / "imageforge-haarcascade-frontalface.xml"
            if not safe_path.exists() or safe_path.stat().st_size != cascade_path.stat().st_size:
                shutil.copyfile(cascade_path, safe_path)
            cascade_path = safe_path
        self.detector = cv2.CascadeClassifier(str(cascade_path))
        if self.detector.empty():
            raise RuntimeError("OpenCV 人脸检测模型加载失败")

    def inspect(self, path: Path) -> QualityResult:
        frame = cv2.imread(str(path))
        if frame is None:
            return QualityResult(False, 0, 0, 0, ["图片无法读取"])
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        min_side = min(gray.shape[:2])
        min_face = max(24, min_side // 12)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(min_face, min_face),
        )
        warnings: list[str] = []
        blocking_reasons: list[str] = []
        if width < 320 or height < 240:
            blocking_reasons.append("照片分辨率过低")
        if len(faces) == 0:
            # Haar 正脸检测对眼镜反光、轻微虚焦和侧脸很敏感。四连拍里这些情况
            # 仍然有使用价值，因此作为提醒记录，不再直接拒绝游客照片。
            warnings.append("未稳定识别人脸，已按现场宽松模式接收")
        elif len(faces) > 1:
            warnings.append("检测到多张人脸，请在后续结果中确认主体")
        if brightness < self.settings.dark_threshold:
            blocking_reasons.append("照片严重过暗")
        if brightness > self.settings.overexposed_threshold:
            blocking_reasons.append("照片严重过曝")
        if blur_score < self.settings.blur_threshold:
            blocking_reasons.append("画面无法辨认")
        elif blur_score < 40:
            warnings.append("画面轻微模糊，已接收")
        return QualityResult(
            not blocking_reasons,
            int(len(faces)),
            brightness,
            blur_score,
            blocking_reasons + warnings,
        )
