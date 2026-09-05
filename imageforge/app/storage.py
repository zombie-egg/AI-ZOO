from __future__ import annotations

import base64
import html
import io
import time
from pathlib import Path

from PIL import Image, ImageOps

from .config import Settings
from .security import sign_delivery


def load_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def save_jpeg(image: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def upscale_long_edge(image: Image.Image, long_edge: int) -> Image.Image:
    ratio = long_edge / max(image.size)
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    return image.resize(size, Image.Resampling.LANCZOS)


def create_print_payload(
    image_url: str, order_no: str, destination: Path, image_path: Path | None = None
) -> None:
    # 打印代理会把此片段注入自己的页面，不能再嵌套 html/body，否则 Chromium 会错误分页。
    # 优先内嵌图片，避免打印瞬间的网络请求造成空白页。
    source = html.escape(image_url)
    if image_path is not None:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        source = f"data:image/jpeg;base64,{encoded}"
    content = f"""<style>
@page{{size:100mm 148mm;margin:0}}
html,body,#printElement{{margin:0!important;padding:0!important;width:100%!important;height:100%!important;overflow:hidden!important}}
.photo-print-sheet{{box-sizing:border-box;width:100%;height:100%;padding:3mm 3mm 5mm;background:#fff;display:flex;flex-direction:column;overflow:hidden;break-after:avoid;page-break-after:avoid}}
.photo-print-sheet img{{display:block;min-width:0;width:100%;height:calc(100% - 4mm);object-fit:cover}}
.photo-print-sheet footer{{flex:0 0 4mm;height:4mm;font:2mm/4mm sans-serif;text-align:center;color:#555;overflow:hidden}}
</style><main class="photo-print-sheet hiprint-printPaper"><img src="{source}" alt="AI 终图"><footer>{html.escape(order_no)}</footer></main>"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def signed_delivery_url(settings: Settings, job_id: str, filename: str) -> str:
    expires = int(time.time()) + settings.signed_url_ttl_s
    signature = sign_delivery(settings.signing_secret, job_id, filename, expires)
    return (
        f"{settings.public_base_url.rstrip('/')}/private-delivery/{job_id}/{filename}"
        f"?expires={expires}&sig={signature}"
    )


def image_bytes_to_rgb(payload: bytes) -> Image.Image:
    with Image.open(io.BytesIO(payload)) as image:
        return ImageOps.exif_transpose(image).convert("RGB")
