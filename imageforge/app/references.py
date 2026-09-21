from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .config import Settings


SHOT_ROLES = (
    "body_anchor",
    "front_smile",
    "left_three_quarter",
    "right_three_quarter",
)

ROLE_DESCRIPTIONS = {
    "body_anchor": "body, outfit, hairstyle, and accessory context; it does not set the target expression",
    "front_smile": "current appearance authority and primary front-face identity view; its captured smile is optional",
    "left_three_quarter": "left three-quarter facial identity and depth view for the same person",
    "right_three_quarter": "right three-quarter facial identity and depth view for the same person",
}

SUBJECT_PRIMARY = "SUBJECT_PRIMARY"
SUBJECT_ADDITIONAL = "SUBJECT_ADDITIONAL"

_ROLE_PRIORITY_BY_POSE = {
    "FRONT": ("front_smile", "body_anchor", "left_three_quarter", "right_three_quarter"),
    "SIDE": ("front_smile", "left_three_quarter", "body_anchor", "right_three_quarter"),
    "BACK": ("front_smile", "left_three_quarter", "body_anchor", "right_three_quarter"),
}


def active_model_id(settings: Settings) -> str:
    override = settings.image_provider_override.strip().lower()
    if override in {"gemini", "gemini-image"}:
        return settings.fallback_image_model.strip()
    if override in {"qwen", "qwen-image"}:
        return "qwen-image-edit"
    if override == "mock":
        return "mock"
    return settings.gpt_image_model.strip()


def reference_image_limit(settings: Settings) -> int:
    override = settings.image_provider_override.strip().lower()
    if override not in {"gemini", "gemini-image"}:
        return settings.reference_image_limit
    model = settings.fallback_image_model.strip().lower()
    documented_limit = {
        "gemini-2.5-flash-image": 3,
        "gemini-3.1-flash-image-preview": 14,
        "gemini-3.1-flash-image": 14,
        "gemini-3-pro-image-preview": 14,
        "gemini-3-pro-image": 14,
    }.get(model, 3)
    return min(settings.reference_image_limit, documented_limit)


def _selected_roles(participant_count: int, limit: int, pose_id: str) -> tuple[str, ...]:
    priority = _ROLE_PRIORITY_BY_POSE.get(pose_id)
    if priority is None:
        raise ValueError(f"未知姿势无法选择参考图：{pose_id}")
    required = participant_count * len(SHOT_ROLES)
    if required <= limit:
        return priority
    # Keep the same evidence for every participant. Primary appearance is always first, followed by
    # one pose-relevant angle and the body/outfit context, instead of weakening later participants.
    if participant_count * 3 <= limit:
        return priority[:3]
    raise ValueError(
        f"当前模型参考图上限 {limit} 无法为 {participant_count} 位参与者提供至少三张身份参考"
    )


def build_reference_manifest(
    participant_groups: list[dict[str, Any]],
    settings: Settings,
    pose_id: str = "FRONT",
) -> list[dict[str, Any]]:
    participant_count = len(participant_groups)
    if participant_count < 1 or participant_count > 4:
        raise ValueError("参与者数量必须为 1 至 4 人")
    roles = _selected_roles(participant_count, reference_image_limit(settings), pose_id)
    manifest: list[dict[str, Any]] = []
    for group in participant_groups:
        paths = [str(path) for path in group.get("source_paths", [])]
        if len(paths) != len(SHOT_ROLES):
            raise ValueError("每位参与者必须有按既定顺序上传的四张参考图")
        slot = int(group["slot"])
        by_role = dict(zip(SHOT_ROLES, paths, strict=True))
        for role in roles:
            path = by_role[role]
            metadata = inspect_reference_file(Path(path))
            reference_role = SUBJECT_PRIMARY if role == "front_smile" else SUBJECT_ADDITIONAL
            manifest.append(
                {
                    "participant_slot": slot,
                    "shot_role": role,
                    "reference_role": reference_role,
                    "path": path,
                    "label": f"{reference_role} — PERSON {slot} — {ROLE_DESCRIPTIONS[role]}",
                    **metadata,
                }
            )
    return manifest


def legacy_reference_manifest(participant_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for group in participant_groups:
        slot = int(group.get("slot", 1))
        paths = [str(path) for path in group.get("source_paths", [])]
        for role, path in zip(SHOT_ROLES, paths):
            metadata = inspect_reference_file(Path(path)) if Path(path).is_file() else {}
            reference_role = SUBJECT_PRIMARY if role == "front_smile" else SUBJECT_ADDITIONAL
            manifest.append(
                {
                    "participant_slot": slot,
                    "shot_role": role,
                    "reference_role": reference_role,
                    "path": path,
                    "label": f"{reference_role} — PERSON {slot} — {ROLE_DESCRIPTIONS[role]}",
                    **metadata,
                }
            )
    return manifest


def public_reference_labels(manifest: list[dict[str, Any]]) -> list[str]:
    return [str(item["label"]) for item in manifest]


def validate_reference_manifest(manifest: list[dict[str, Any]]) -> None:
    if not manifest:
        raise ValueError("参考图清单为空")
    for item in manifest:
        if not item.get("label") or not item.get("shot_role") or not item.get("path"):
            raise ValueError("参考图清单包含空标签或空路径")
        if item["shot_role"] not in SHOT_ROLES:
            raise ValueError(f"未知参考图角色：{item['shot_role']}")
        if not item.get("reference_role") and item["shot_role"] in SHOT_ROLES:
            item["reference_role"] = (
                SUBJECT_PRIMARY if item["shot_role"] == "front_smile" else SUBJECT_ADDITIONAL
            )
        if item.get("reference_role") not in {SUBJECT_PRIMARY, SUBJECT_ADDITIONAL}:
            raise ValueError("参考图未标记为 SUBJECT_PRIMARY 或 SUBJECT_ADDITIONAL")
        path = Path(item["path"])
        if not path.is_file():
            raise ValueError("参考图文件不存在")
        actual = inspect_reference_file(path)
        for key in ("width", "height", "mime_type", "decoded"):
            if key not in item:
                item[key] = actual[key]
            elif item[key] != actual[key]:
                raise ValueError(f"参考图诊断信息与实际文件不一致：{item['label']}")


def inspect_reference_file(path: Path) -> dict[str, Any]:
    """Return non-sensitive metadata and fail closed when an input cannot be decoded."""
    try:
        with Image.open(path) as image:
            image.load()
            image_format = (image.format or "").upper()
            oriented = ImageOps.exif_transpose(image)
            width, height = oriented.size
    except (OSError, ValueError) as exc:
        raise ValueError("参考图无法解码") from exc
    mime_type = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }.get(image_format)
    if mime_type is None:
        raise ValueError(f"参考图格式不受支持：{image_format or 'unknown'}")
    if width < 1 or height < 1:
        raise ValueError("参考图尺寸无效")
    return {
        "width": width,
        "height": height,
        "mime_type": mime_type,
        "decoded": True,
    }


def public_reference_diagnostics(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude paths and image contents from diagnostics returned to trusted callers."""
    return [
        {
            "participant_slot": int(item["participant_slot"]),
            "reference_role": str(item["reference_role"]),
            "shot_role": str(item["shot_role"]),
            "width": int(item["width"]),
            "height": int(item["height"]),
            "mime_type": str(item["mime_type"]),
            "decoded": bool(item["decoded"]),
        }
        for item in manifest
    ]
