from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings


SHOT_ROLES = (
    "body_anchor",
    "front_smile",
    "left_three_quarter",
    "right_three_quarter",
)

ROLE_DESCRIPTIONS = {
    "body_anchor": "body and outfit anchor; also supports identity, but does not set the target expression",
    "front_smile": "primary front-face identity view; its smile is optional, not a required target expression",
    "left_three_quarter": "left three-quarter identity and facial-depth view",
    "right_three_quarter": "right three-quarter identity and facial-depth view",
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


def _selected_roles(participant_count: int, limit: int) -> tuple[str, ...]:
    required = participant_count * len(SHOT_ROLES)
    if required <= limit:
        return SHOT_ROLES
    # Keep the same identity evidence for every participant rather than giving later people weaker
    # coverage. Body/outfit + front identity + one angled identity view is the minimum supported set.
    if participant_count * 3 <= limit:
        return SHOT_ROLES[:3]
    raise ValueError(
        f"当前模型参考图上限 {limit} 无法为 {participant_count} 位参与者提供至少三张身份参考"
    )


def build_reference_manifest(
    participant_groups: list[dict[str, Any]],
    settings: Settings,
) -> list[dict[str, Any]]:
    participant_count = len(participant_groups)
    if participant_count < 1 or participant_count > 4:
        raise ValueError("参与者数量必须为 1 至 4 人")
    roles = _selected_roles(participant_count, reference_image_limit(settings))
    manifest: list[dict[str, Any]] = []
    for group in participant_groups:
        paths = [str(path) for path in group.get("source_paths", [])]
        if len(paths) != len(SHOT_ROLES):
            raise ValueError("每位参与者必须有按既定顺序上传的四张参考图")
        slot = int(group["slot"])
        by_role = dict(zip(SHOT_ROLES, paths, strict=True))
        for role in roles:
            manifest.append(
                {
                    "participant_slot": slot,
                    "shot_role": role,
                    "path": by_role[role],
                    "label": f"PERSON {slot} — {ROLE_DESCRIPTIONS[role]}",
                }
            )
    return manifest


def legacy_reference_manifest(participant_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for group in participant_groups:
        slot = int(group.get("slot", 1))
        paths = [str(path) for path in group.get("source_paths", [])]
        for role, path in zip(SHOT_ROLES, paths):
            manifest.append(
                {
                    "participant_slot": slot,
                    "shot_role": role,
                    "path": path,
                    "label": f"PERSON {slot} — {ROLE_DESCRIPTIONS[role]}",
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
        if not Path(item["path"]).is_file():
            raise ValueError("参考图文件不存在")
