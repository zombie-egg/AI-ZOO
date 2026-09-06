from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
from PIL import Image, ImageEnhance, ImageFilter

from .config import Settings
from .security import assert_provider_call_allowed


class ProviderError(RuntimeError):
    pass


class ImageProvider(ABC):
    name: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        init_image: bytes | None,
        size: str,
        reference_images: list[bytes] | None = None,
    ) -> bytes: ...


class GuardedProvider(ImageProvider):
    def generate(
        self,
        prompt: str,
        init_image: bytes | None,
        size: str,
        reference_images: list[bytes] | None = None,
    ) -> bytes:
        assert_provider_call_allowed()
        return self._generate(prompt, init_image, size, reference_images or [])

    @abstractmethod
    def _generate(
        self, prompt: str, init_image: bytes | None, size: str, reference_images: list[bytes]
    ) -> bytes: ...


class MockProvider(GuardedProvider):
    name = "mock"

    def __init__(self, drift: bool = False, fail: bool = False):
        self.drift = drift
        self.fail = fail
        self.calls = 0

    def _generate(
        self, prompt: str, init_image: bytes | None, size: str, reference_images: list[bytes]
    ) -> bytes:
        self.calls += 1
        if self.fail:
            raise ProviderError("MockProvider 故意失败")
        source_bytes = init_image or (reference_images[0] if reference_images else None)
        if not source_bytes:
            image = Image.new("RGB", (1024, 1536), (215, 225, 205))
        else:
            with Image.open(io.BytesIO(source_bytes)) as source:
                image = source.convert("RGB")
        image = ImageEnhance.Contrast(image).enhance(1.03)
        image = ImageEnhance.Color(image).enhance(1.04)
        image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
        if self.drift:
            overlay = Image.new("RGB", image.size, (180, 80, 120))
            image = Image.blend(image, overlay, 0.65)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=94)
        return buffer.getvalue()


class OpenAICompatibleProvider(GuardedProvider):
    def __init__(self, settings: Settings, model: str, name: str):
        self.settings = settings
        self.model = model
        self.name = name

    def _decode_response(self, response: httpx.Response) -> bytes:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"图片网关返回了非 JSON（HTTP {response.status_code}）") from exc
        if response.is_error:
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = error.get("message") or payload.get("message") or f"HTTP {response.status_code}"
            raise ProviderError(f"图片网关拒绝请求：{message}")
        try:
            item = payload["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("图片网关响应缺少 data[0]") from exc
        if item.get("b64_json"):
            try:
                return base64.b64decode(item["b64_json"], validate=True)
            except ValueError as exc:
                raise ProviderError("图片网关返回的 Base64 无效") from exc
        if item.get("url"):
            with httpx.Client(timeout=self.settings.gpt_timeout_s, follow_redirects=True) as client:
                image_response = client.get(item["url"])
                image_response.raise_for_status()
                return image_response.content
        raise ProviderError("图片网关既未返回 b64_json，也未返回 url")

    def _generate(
        self, prompt: str, init_image: bytes | None, size: str, reference_images: list[bytes]
    ) -> bytes:
        token = self.settings.provider_token
        if not token:
            raise ProviderError("未配置 NEWAPI_TOKEN/GPT_IMAGE_API_KEY")
        base = self.settings.provider_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"}
        timeout = httpx.Timeout(self.settings.gpt_timeout_s)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            if init_image is not None or reference_images:
                files: list[tuple[str, tuple[str, bytes, str]]] = []
                if init_image is not None:
                    files.append(("image[]", ("edit-source.jpg", init_image, "image/jpeg")))
                files.extend(
                    ("image[]", (f"visitor-reference-{index}.jpg", reference, "image/jpeg"))
                    for index, reference in enumerate(reference_images, 1)
                )
                response = client.post(
                    f"{base}/images/edits",
                    headers=headers,
                    data={
                        "model": self.model,
                        "prompt": prompt,
                        "size": size,
                        "quality": "high",
                        "output_format": "jpeg",
                    },
                    files=files,
                )
            else:
                response = client.post(
                    f"{base}/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "size": size,
                        "quality": "high",
                        "output_format": "jpeg",
                    },
                )
        return self._decode_response(response)


class GptImage2Provider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings):
        super().__init__(settings, settings.gpt_image_model.strip(), "gpt-image-2")


class GeminiGenerateContentProvider(GuardedProvider):
    name = "gemini-image-fallback"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.fallback_image_model.strip()

    @staticmethod
    def _mime_type(image_bytes: bytes) -> str:
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image_format = (image.format or "JPEG").upper()
        except (OSError, ValueError):
            image_format = "JPEG"
        return {
            "PNG": "image/png",
            "WEBP": "image/webp",
            "GIF": "image/gif",
        }.get(image_format, "image/jpeg")

    @staticmethod
    def _aspect_ratio(size: str) -> str:
        try:
            width, height = (int(value) for value in size.lower().split("x", 1))
        except (TypeError, ValueError):
            return "2:3"
        ratios = {
            (1, 1): "1:1",
            (2, 3): "2:3",
            (3, 2): "3:2",
            (3, 4): "3:4",
            (4, 3): "4:3",
            (4, 5): "4:5",
            (5, 4): "5:4",
            (9, 16): "9:16",
            (16, 9): "16:9",
        }
        from math import gcd

        divisor = gcd(width, height)
        return ratios.get((width // divisor, height // divisor), "2:3")

    def _decode_response(self, response: httpx.Response) -> bytes:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(
                f"Gemini 兜底网关返回了非 JSON（HTTP {response.status_code}）"
            ) from exc
        if response.is_error:
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = (
                error.get("message") if isinstance(error, dict) else None
            ) or (payload.get("message") if isinstance(payload, dict) else None)
            raise ProviderError(f"Gemini 兜底网关拒绝请求：{message or response.status_code}")
        try:
            parts = payload["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Gemini 兜底响应缺少 candidates[0].content.parts") from exc
        for part in parts:
            inline_data = part.get("inlineData") or part.get("inline_data")
            if isinstance(inline_data, dict) and inline_data.get("data"):
                try:
                    return base64.b64decode(inline_data["data"], validate=True)
                except (ValueError, TypeError) as exc:
                    raise ProviderError("Gemini 兜底返回的图片 Base64 无效") from exc
        raise ProviderError("Gemini 兜底响应中没有图片")

    def _generate(
        self, prompt: str, init_image: bytes | None, size: str, reference_images: list[bytes]
    ) -> bytes:
        token = self.settings.fallback_image_api_key.strip()
        if not token:
            raise ProviderError("未配置 FALLBACK_IMAGE_API_KEY")
        images = ([init_image] if init_image is not None else []) + reference_images
        parts: list[dict] = [{"text": prompt}]
        parts.extend(
            {
                "inlineData": {
                    "mimeType": self._mime_type(image_bytes),
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }
            }
            for image_bytes in images
        )
        base = self.settings.fallback_image_base_url.strip().rstrip("/")
        if base.endswith("/v1beta"):
            endpoint = f"{base}/models/{self.model}:generateContent"
        else:
            endpoint = f"{base}/v1beta/models/{self.model}:generateContent"
        with httpx.Client(
            timeout=httpx.Timeout(self.settings.gpt_timeout_s), follow_redirects=True
        ) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-goog-api-key": token,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {
                        "responseModalities": ["IMAGE"],
                        "imageConfig": {"aspectRatio": self._aspect_ratio(size)},
                    },
                },
            )
        return self._decode_response(response)


class FallbackProvider(GuardedProvider):
    def __init__(self, primary: ImageProvider, fallback: ImageProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}+{fallback.name}"
        self.last_provider_name = primary.name
        self.used_fallback = False

    def _generate(
        self, prompt: str, init_image: bytes | None, size: str, reference_images: list[bytes]
    ) -> bytes:
        self.last_provider_name = self.primary.name
        self.used_fallback = False
        try:
            return self.primary.generate(prompt, init_image, size, reference_images)
        except (ProviderError, httpx.HTTPError) as primary_error:
            self.last_provider_name = self.fallback.name
            self.used_fallback = True
            try:
                return self.fallback.generate(prompt, init_image, size, reference_images)
            except (ProviderError, httpx.HTTPError) as fallback_error:
                raise ProviderError(
                    f"主图片服务失败（{primary_error}）；Gemini 兜底也失败（{fallback_error}）"
                ) from fallback_error


class QwenProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings):
        super().__init__(settings, "qwen-image-edit", "qwen-image")


def build_provider(settings: Settings) -> ImageProvider:
    override = settings.image_provider_override.strip().lower()
    if override == "mock":
        return MockProvider()
    if override in {"qwen", "qwen-image"}:
        return QwenProvider(settings)
    primary = GptImage2Provider(settings)
    if settings.fallback_provider_configured:
        return FallbackProvider(primary, GeminiGenerateContentProvider(settings))
    return primary
