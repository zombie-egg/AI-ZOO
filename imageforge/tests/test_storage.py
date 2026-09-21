from __future__ import annotations

import io

from PIL import Image

from app.storage import create_print_payload, normalize_reference_bytes

from conftest import make_portrait


def test_print_payload_is_embedded_and_single_page(settings):
    image_path = make_portrait(settings.private_dir / "print-source.jpg")
    destination = settings.private_dir / "print-payload.html"
    create_print_payload(
        "http://127.0.0.1:8000/private-delivery/example.jpg",
        "ORDER-PRINT-1",
        destination,
        image_path=image_path,
    )
    payload = destination.read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in payload
    assert "http://127.0.0.1:8000" not in payload
    assert "<html" not in payload
    assert "<body" not in payload
    assert 'class="photo-print-sheet hiprint-printPaper"' in payload
    assert "@page{size:89mm 119mm;margin:0}" in payload
    assert "page-break-after:avoid" in payload


def test_reference_normalization_applies_exif_orientation_and_size_limit():
    source = Image.new("RGB", (1200, 800), "navy")
    exif = Image.Exif()
    exif[274] = 6
    buffer = io.BytesIO()
    source.save(buffer, "JPEG", quality=95, exif=exif)

    normalized = normalize_reference_bytes(buffer.getvalue(), max_edge=600)

    with Image.open(io.BytesIO(normalized)) as result:
        assert result.size == (400, 600)
        assert result.getexif().get(274) is None
