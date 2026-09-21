from __future__ import annotations

import json

from app.db import Database
from app.prompt_builder import NATURAL_EXPRESSION_PROMPT_VERSION
from app.references import build_reference_manifest, public_reference_labels
from app.scene_catalog import (
    compose_generation_prompt,
    composed_prompt_hash,
    composed_prompt_version,
    get_pose,
    get_scene,
)

from conftest import make_portrait


def _participants(settings, count: int) -> list[dict]:
    groups = []
    for slot in range(1, count + 1):
        paths = [
            str(make_portrait(settings.private_dir / "refs" / f"{slot}-{index}.jpg"))
            for index in range(4)
        ]
        groups.append({"slot": slot, "source_paths": paths})
    return groups


def test_four_people_use_symmetric_twelve_reference_manifest(settings):
    settings.image_provider_override = "gemini"
    settings.fallback_image_model = "gemini-3.1-flash-image-preview"
    manifest = build_reference_manifest(_participants(settings, 4), settings)
    assert len(manifest) == 12
    assert [item["participant_slot"] for item in manifest].count(1) == 3
    assert [item["participant_slot"] for item in manifest].count(4) == 3
    assert {item["shot_role"] for item in manifest} == {
        "body_anchor",
        "front_smile",
        "left_three_quarter",
    }


def test_prompt_text_and_reference_manifest_are_frozen_on_job(settings):
    settings.generation_prompt_version = NATURAL_EXPRESSION_PROMPT_VERSION
    groups = _participants(settings, 1)
    manifest = build_reference_manifest(groups, settings)
    scene = get_scene("PANDA_CASUAL_01")
    pose = get_pose("SIDE")
    labels = public_reference_labels(manifest)
    prompt = compose_generation_prompt(
        scene,
        pose,
        prompt_version=settings.generation_prompt_version,
        reference_roles=labels,
    )
    db = Database(settings.database_path)
    assert db.create_generation(
        {
            "id": "frozen-prompt-1",
            "order_no": "FROZEN-PROMPT-1",
            "scene_id": scene.scene_id,
            "pose_id": pose.pose_id,
            "prompt_version": composed_prompt_version(
                scene, pose, prompt_version=settings.generation_prompt_version
            ),
            "prompt_hash": composed_prompt_hash(
                scene,
                pose,
                prompt_version=settings.generation_prompt_version,
                reference_roles=labels,
            ),
            "prompt_text": prompt,
            "source_paths": groups[0]["source_paths"],
            "participants": groups,
            "reference_manifest": manifest,
            "provider": "gemini-3.1-flash-image-preview",
        }
    )
    row = db.one("SELECT * FROM generation_job WHERE id = ?", ("frozen-prompt-1",))
    assert row["prompt_text"] == prompt
    assert row["prompt_version"].startswith(NATURAL_EXPRESSION_PROMPT_VERSION)
    assert json.loads(row["reference_manifest_json"]) == manifest
    assert "PERSON 1" in row["prompt_text"]
