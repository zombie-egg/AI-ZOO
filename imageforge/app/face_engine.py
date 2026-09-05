from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

import cv2

from .config import Settings


class FaceEngineError(RuntimeError):
    pass


class FaceEngine(ABC):
    """Identity QA only. V4 never swaps, relocks, or retouches the generated face."""

    name: str
    production_ready: bool = False

    @abstractmethod
    def similarity(self, source: Path, candidate: Path) -> float: ...


class LocalFaceEngine(FaceEngine):
    """开发期只返回粗略信号；production_ready=False 会强制人工验图。"""

    name = "local-dev"
    production_ready = False

    def similarity(self, source: Path, candidate: Path) -> float:
        first = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        second = cv2.imread(str(candidate), cv2.IMREAD_GRAYSCALE)
        if first is None or second is None:
            return 0.0
        first = cv2.resize(first, (128, 128))
        second = cv2.resize(second, (128, 128))
        first_hist = cv2.calcHist([first], [0], None, [64], [0, 256])
        second_hist = cv2.calcHist([second], [0], None, [64], [0, 256])
        score = cv2.compareHist(first_hist, second_hist, cv2.HISTCMP_CORREL)
        return float(max(0.0, min(1.0, (score + 1) / 2)))


class FaceFusionCliEngine(FaceEngine):
    name = "insightface-arcface-qa"
    production_ready = True

    def __init__(self, settings: Settings):
        self.settings = settings
        self.entrypoint = settings.facefusion_root / "facefusion.py"
        if not self.entrypoint.exists():
            raise FaceEngineError(f"FaceFusion 入口不存在：{self.entrypoint}")

    def similarity(self, source: Path, candidate: Path) -> float:
        # FaceFusion 的 ArcFace 模型由独立脚本读取，避免在服务进程重复初始化整套 CLI。
        script = Path(__file__).resolve().parents[1] / "scripts" / "facefusion_similarity.py"
        result = subprocess.run(
            [self.settings.facefusion_python, str(script), str(source), str(candidate), str(self.settings.facefusion_root)],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode != 0:
            raise FaceEngineError(f"ArcFace 相似度计算失败：{result.stderr[-800:]}")
        try:
            return float(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise FaceEngineError("ArcFace 相似度输出格式错误") from exc


def build_face_engine(settings: Settings) -> FaceEngine:
    if settings.face_engine.lower() == "facefusion":
        return FaceFusionCliEngine(settings)
    return LocalFaceEngine()
