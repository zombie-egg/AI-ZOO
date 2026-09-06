from __future__ import annotations

import base64
import io

import httpx
import pytest
from PIL import Image

from app.providers import GeminiGenerateContentProvider, ProviderError, build_provider
from app.security import generation_provider_scope


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), "navy").save(buffer, "JPEG")
    return buffer.getvalue()


def test_gemini_provider_uses_native_multimodal_request(settings, monkeypatch):
    settings.fallback_image_base_url = "https://relay.example"
    settings.fallback_image_api_key = "test-key"
    settings.fallback_image_model = "gemini-image-test"
    generated = _jpeg_bytes()
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/jpeg",
                                        "data": base64.b64encode(generated).decode("ascii"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("app.providers.httpx.Client", client_factory)
    provider = GeminiGenerateContentProvider(settings)
    references = [_jpeg_bytes() for _ in range(4)]
    with generation_provider_scope("provider-test"):
        result = provider.generate("keep the same person", None, "1024x1536", references)

    assert result == generated
    assert captured["url"].endswith(
        "/v1beta/models/gemini-image-test:generateContent"
    )
    assert captured["authorization"] == "Bearer test-key"
    body = __import__("json").loads(captured["body"])
    assert len(body["contents"][0]["parts"]) == 5
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "2:3"


def test_build_provider_can_use_gemini_as_primary(settings):
    settings.image_provider_override = "gemini"
    settings.fallback_image_base_url = "https://relay.example"
    settings.fallback_image_api_key = "test-key"

    provider = build_provider(settings)

    assert isinstance(provider, GeminiGenerateContentProvider)
    assert provider.name == "gemini-image"


def test_build_provider_rejects_unconfigured_gemini(settings):
    settings.image_provider_override = "gemini"
    settings.fallback_image_base_url = ""
    settings.fallback_image_api_key = ""

    with pytest.raises(ProviderError, match="Gemini 生图未配置"):
        build_provider(settings)
