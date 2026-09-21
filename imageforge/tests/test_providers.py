from __future__ import annotations

import base64
import io

import httpx
import pytest
from PIL import Image

from app.providers import GeminiGenerateContentProvider, ProviderError, ReferenceImage, build_provider
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
    references = [
        ReferenceImage(_jpeg_bytes(), f"PERSON 1 — reference role {index}")
        for index in range(1, 5)
    ]
    with generation_provider_scope("provider-test"):
        result = provider.generate("keep the same person", None, "1024x1536", references)

    assert result == generated
    assert captured["url"].endswith(
        "/v1beta/models/gemini-image-test:generateContent"
    )
    assert captured["authorization"] == "Bearer test-key"
    body = __import__("json").loads(captured["body"])
    parts = body["contents"][0]["parts"]
    assert len(parts) == 9
    assert [parts[index]["text"] for index in (1, 3, 5, 7)] == [
        f"PERSON 1 — reference role {index}" for index in range(1, 5)
    ]
    assert all("inlineData" in parts[index] for index in (2, 4, 6, 8))
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "2:3"


def test_gemini_provider_rejects_text_only_generation(settings):
    settings.fallback_image_base_url = "https://relay.example"
    settings.fallback_image_api_key = "test-key"
    provider = GeminiGenerateContentProvider(settings)
    with generation_provider_scope("provider-no-reference"):
        with pytest.raises(ProviderError, match="缺少主体图像"):
            provider.generate("make a random person", None, "1024x1536", [])


def test_gemini_provider_rejects_declared_mime_mismatch(settings):
    settings.fallback_image_base_url = "https://relay.example"
    settings.fallback_image_api_key = "test-key"
    provider = GeminiGenerateContentProvider(settings)
    reference = ReferenceImage(
        _jpeg_bytes(),
        "SUBJECT_PRIMARY — PERSON 1",
        mime_type="image/png",
        width=40,
        height=60,
    )
    with generation_provider_scope("provider-mime-mismatch"):
        with pytest.raises(ProviderError, match="MIME"):
            provider.generate("keep this person", None, "1024x1536", [reference])


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
