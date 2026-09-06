from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    imageforge_secret: str = "change-me"
    imageforge_secret_key: str = "change-me-too"
    imageforge_access_token: str = "change-access-token"
    imageforge_internal_token: str = "change-internal-token"

    public_base_url: str = "http://localhost:8000"
    cors_allowed_origins: str = "http://127.0.0.1:4175,http://localhost:4175"
    database_path: Path = Path("./data/imageforge.db")
    private_dir: Path = Path("./data/private")

    lock_threshold: float = Field(default=0.55, ge=0, le=1)
    # 现场采集只拦截完全不可用的画面。轻微虚焦、眼镜反光和侧脸交给后续多图流程处理。
    dark_threshold: float = 15
    overexposed_threshold: float = 245
    blur_threshold: float = 3

    # 直连生成默认一次；只有真实人脸引擎判定身份漂移时才进行第二次付费尝试。
    gpt_attempts: int = Field(default=2, ge=1, le=2)
    gpt_timeout_s: int = Field(default=120, ge=5)
    newapi_base_url: str = "http://127.0.0.1:3000/v1"
    newapi_token: str = ""
    gpt_image_api_key: str = ""
    gpt_image_base_url: str = ""
    gpt_image_model: str = "gpt-image-2"
    image_provider_override: str = ""

    # 第二图片供应商只在主供应商请求失败时启用。
    fallback_image_base_url: str = ""
    fallback_image_api_key: str = ""
    fallback_image_model: str = "gemini-3.1-flash-image-preview"

    face_engine: str = "local"
    facefusion_python: str = "python"
    facefusion_root: Path = Path("/opt/facefusion")

    signed_url_ttl_s: int = Field(default=86400, ge=60)
    signing_secret: str = "change-signing-secret"
    storage_mode: str = "local"
    gpt_image_estimated_cost_cents: int = Field(default=30, ge=0)

    def prepare_directories(self) -> None:
        for directory in (self.database_path.parent, self.private_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def provider_token(self) -> str:
        # 兼容用户已保存的 GPT_IMAGE_API_KEY，也兼容规范里的 NEWAPI_TOKEN。
        return (self.newapi_token or self.gpt_image_api_key).strip()

    @property
    def provider_base_url(self) -> str:
        return (self.gpt_image_base_url or self.newapi_base_url).strip()

    @property
    def fallback_provider_configured(self) -> bool:
        return bool(self.fallback_image_base_url.strip() and self.fallback_image_api_key.strip())

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


def load_settings() -> Settings:
    settings = Settings()
    settings.prepare_directories()
    return settings
