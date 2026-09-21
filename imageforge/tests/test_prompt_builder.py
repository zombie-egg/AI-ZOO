from __future__ import annotations

import json

from app.db import Database
import pytest

from app.prompt_builder import (
    NATURAL_EXPRESSION_PROMPT_VERSION,
    REFERENCE_FAITHFUL_PROMPT_VERSION,
)
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


def test_primary_reference_is_first_and_every_reference_has_safe_diagnostics(settings):
    manifest = build_reference_manifest(_participants(settings, 1), settings, pose_id="BACK")
    assert [item["shot_role"] for item in manifest] == [
        "front_smile",
        "left_three_quarter",
        "body_anchor",
        "right_three_quarter",
    ]
    assert manifest[0]["reference_role"] == "SUBJECT_PRIMARY"
    assert all(item["decoded"] is True for item in manifest)
    assert all((item["width"], item["height"]) == (600, 900) for item in manifest)
    assert all(item["mime_type"] == "image/jpeg" for item in manifest)


def test_reference_manifest_fails_closed_for_an_undecodable_image(settings):
    groups = _participants(settings, 1)
    broken = settings.private_dir / "refs" / "broken.jpg"
    broken.write_bytes(b"not-an-image")
    groups[0]["source_paths"][1] = str(broken)
    with pytest.raises(ValueError, match="无法解码"):
        build_reference_manifest(groups, settings)


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


def test_reference_faithful_prompt_uses_the_sample_requirement_only_when_resolved():
    sample_requirement = (
        "The subject is not wearing glasses. Keep the dense fringe covering the forehead as shown "
        "in the primary subject reference, adapted naturally to the selected head angle."
    )
    sample_expression = (
        "Keep a relaxed neutral expression consistent with the subject reference, with a comfortable "
        "mouth and naturally attentive eyes. Do not introduce a smile for this test."
    )
    sample = compose_generation_prompt(
        get_scene("RED_PANDA_VIEW_01"),
        get_pose("BACK"),
        prompt_version=REFERENCE_FAITHFUL_PROMPT_VERSION,
        resolved_appearance_requirements=[sample_requirement],
        resolved_expression=sample_expression,
    )
    other_user = compose_generation_prompt(
        get_scene("RED_PANDA_VIEW_01"),
        get_pose("BACK"),
        prompt_version=REFERENCE_FAITHFUL_PROMPT_VERSION,
    )
    assert sample_requirement in sample
    assert sample_expression in sample
    assert sample.count("EXPRESSION —") == 1
    assert sample_requirement not in other_user
    assert "follow SUBJECT_PRIMARY" in other_user
    assert "Do not invent or remove glasses" in other_user


def test_reference_faithful_prompt_compiles_all_real_scene_pose_combinations():
    from app.scene_catalog import POSES, SCENES

    assert len(SCENES) == 9
    assert len(POSES) == 3
    for scene in SCENES:
        for pose in POSES:
            prompt = compose_generation_prompt(
                scene,
                pose,
                prompt_version=REFERENCE_FAITHFUL_PROMPT_VERSION,
            )
            assert scene.scene_id in prompt
            assert pose.pose_id in prompt
            assert prompt.count("EXPRESSION —") == 1
            assert "SUBJECT_PRIMARY" in prompt
            assert "SCENE_REFERENCE or POSE_REFERENCE" in prompt
            assert "{{" not in prompt and "}}" not in prompt
            assert "face-slimming treatment" not in prompt
            assert "moderate, natural brightening and whitening" not in prompt
