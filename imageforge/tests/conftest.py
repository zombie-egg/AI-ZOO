from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.config import Settings
from app.face_engine import FaceEngine
from app.quality import QualityResult


class FixtureQuality:
    def __init__(self, ok: bool = True):
        self.ok = ok

    def inspect(self, path: Path) -> QualityResult:
        return QualityResult(self.ok, 1 if self.ok else 0, 128.0, 120.0, [] if self.ok else ["未检测到人脸"])


class FixtureFaceEngine(FaceEngine):
    name = "fixture-arcface"
    production_ready = True

    def __init__(self, similarities: list[float] | None = None):
        self.similarities = list(similarities or [0.82])
        self.swap_calls = 0

    def swap(self, source: Path, target: Path, destination: Path, attempt: int) -> None:
        self.swap_calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, destination)

    def enhance(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.convert("RGB").resize((1365, 2048)).save(destination, "JPEG", quality=92)

    def similarity(self, source: Path, candidate: Path) -> float:
        if len(self.similarities) > 1:
            return self.similarities.pop(0)
        return self.similarities[0]


def make_portrait(path: Path, color: tuple[int, int, int] = (170, 140, 110)) -> Path:
    image = Image.new("RGB", (600, 900), (80, 120, 90))
    draw = ImageDraw.Draw(image)
    draw.ellipse((210, 130, 390, 330), fill=color)
    draw.ellipse((250, 200, 265, 215), fill="black")
    draw.ellipse((335, 200, 350, 215), fill="black")
    draw.arc((260, 220, 345, 285), 10, 170, fill="black", width=5)
    draw.rectangle((180, 330, 420, 820), fill=(80, 90, 160))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=92)
    return path


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    value = Settings(
        _env_file=None,
        imageforge_secret="test-secret",
        imageforge_secret_key="test-secret-key",
        imageforge_access_token="test-access",
        imageforge_internal_token="test-internal",
        signing_secret="test-signing-secret",
        public_base_url="http://testserver",
        database_path=tmp_path / "imageforge.db",
        private_dir=tmp_path / "private",
        image_provider_override="mock",
        lock_threshold=0.55,
        blur_threshold=0,
        gpt_attempts=2,
    )
    value.prepare_directories()
    return value
