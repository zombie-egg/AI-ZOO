from __future__ import annotations

import json
from pathlib import Path

from app.db import Database
from app.pipelines import run_direct_generation_pipeline
from app.providers import FallbackProvider, MockProvider
from app.prompt_builder import LEGACY_PROMPT_VERSION, NATURAL_EXPRESSION_PROMPT_VERSION
from app.scene_catalog import POSES, SCENES, compose_generation_prompt, get_pose, get_scene

from conftest import FixtureFaceEngine, make_portrait


def _seed(settings, db: Database, job_id: str, order_no: str) -> list[Path]:
    sources = [
        make_portrait(settings.private_dir / "uploads" / f"{job_id}-{index}.jpg")
        for index in range(4)
    ]
    scene = get_scene("PANDA_CASUAL_01")
    assert db.create_generation(
        {
            "id": job_id,
            "order_no": order_no,
            "scene_id": scene.scene_id,
            "prompt_version": scene.prompt_version,
            "prompt_hash": scene.prompt_hash,
            "source_paths": [str(path) for path in sources],
            "sku": "print_1",
            "provider": "mock",
        }
    )
    return sources


def test_direct_pipeline_never_uses_template_and_requires_review(settings):
    db = Database(settings.database_path)
    _seed(settings, db, "direct-1", "ORDER-DIRECT-1")
    states: list[str] = []
    provider = MockProvider()
    run_direct_generation_pipeline(
        "direct-1",
        db,
        settings,
        FixtureFaceEngine([0.8] * 8),
        provider,
        get_scene("PANDA_CASUAL_01").full_prompt,
        sleep=lambda _: None,
        on_state=states.append,
    )
    job = db.one("SELECT * FROM generation_job WHERE id = ?", ("direct-1",))
    assert job["status"] == "review_required"
    assert provider.calls == 1
    assert Path(job["final_path"]).exists()
    assert Path(job["print_payload_path"]).exists()
    attempts = json.loads(job["attempts_json"])
    assert attempts[0]["reference_count"] == 4
    assert states == ["generating", "qa", "review_required"]


def test_natural_expression_prompt_separates_identity_from_expression():
    prompt = compose_generation_prompt(get_scene("PANDA_CASUAL_01"), get_pose("FRONT"))
    assert "FACIAL EXPRESSION — gentle_camera_smile" in prompt
    assert "Preserve identity while allowing natural changes" in prompt
    assert "small, easy smile" in prompt
    assert "heavy beauty retouching" in prompt
    assert "face slimming" in prompt
    assert "must retain full recognizability" not in prompt
    assert "moderate, natural brightening and whitening" not in prompt


def test_each_pose_has_one_distinct_expression_and_coherent_gaze():
    scene = get_scene("PANDA_CASUAL_01")
    front = compose_generation_prompt(scene, get_pose("FRONT"))
    side = compose_generation_prompt(scene, get_pose("SIDE"))
    back = compose_generation_prompt(scene, get_pose("BACK"))
    assert "attention rests on the camera" in front
    assert "45–60 degrees" in side
    assert "20–35 degrees" in back
    assert "FACIAL EXPRESSION — gentle_camera_smile" in front
    assert "FACIAL EXPRESSION — spontaneous_warmth" in side
    assert "FACIAL EXPRESSION — attentive_interest" in back
    assert "The gaze follows the lens" in side
    assert "The eyes follow that animal" in back
    for prompt in (front, side, back):
        assert prompt.count("FACIAL EXPRESSION —") == 1
        assert "full required skin beauty and face-slimming" not in prompt


def test_multi_person_prompt_locks_each_identity_and_group_layout():
    prompt = compose_generation_prompt(
        get_scene("PANDA_CASUAL_01"), get_pose("SIDE"), participant_count=3
    )
    assert "exactly 3 human visitors" in prompt
    assert "PERSON 1: body and outfit anchor" in prompt
    assert "PERSON 2: primary front-face identity view" in prompt
    assert "PERSON 3: right three-quarter identity view" in prompt
    assert "three visitors in a shallow triangular arrangement" in prompt
    assert "Never merge, average, duplicate, omit, or exchange" in prompt


def test_all_scene_pose_combinations_are_compiled_without_placeholders_or_conflicts():
    assert len(POSES) == 3
    for scene in SCENES:
        for pose in POSES:
            prompt = compose_generation_prompt(scene, pose)
            assert scene.scene_id in prompt
            assert pose.pose_id in prompt
            assert prompt.count("SELECTED SCENE —") == 1
            assert prompt.count("SELECTED POSE —") == 1
            assert prompt.count("FACIAL EXPRESSION —") == 1
            assert "{{" not in prompt and "}}" not in prompt
            assert "undefined" not in prompt.lower()
            assert "null" not in prompt.lower()
            assert "Keep both lips comfortably and naturally closed" not in prompt
            assert "full required skin beauty and face-slimming" not in prompt


def test_legacy_prompt_remains_available_as_exact_rollback_baseline():
    prompt = compose_generation_prompt(
        get_scene("PANDA_CASUAL_01"),
        get_pose("FRONT"),
        prompt_version=LEGACY_PROMPT_VERSION,
    )
    assert "NATURAL FACIAL EXPRESSION — OVERRIDES" in prompt
    assert "Keep both lips comfortably and naturally closed" in prompt
    assert "SELECTED VISITOR POSE" in prompt
    assert NATURAL_EXPRESSION_PROMPT_VERSION not in prompt


def test_identity_drift_gets_only_one_paid_retry(settings):
    db = Database(settings.database_path)
    _seed(settings, db, "direct-2", "ORDER-DIRECT-2")
    provider = MockProvider(drift=True)
    run_direct_generation_pipeline(
        "direct-2",
        db,
        settings,
        FixtureFaceEngine([0.1] * 12),
        provider,
        get_scene("PANDA_CASUAL_01").full_prompt,
        sleep=lambda _: None,
    )
    job = db.one("SELECT * FROM generation_job WHERE id = ?", ("direct-2",))
    assert job["status"] == "review_required"
    assert provider.calls == 2
    assert len(json.loads(job["attempts_json"])) == 2


def test_provider_failure_is_failed_without_local_fallback(settings):
    db = Database(settings.database_path)
    _seed(settings, db, "direct-3", "ORDER-DIRECT-3")
    provider = MockProvider(fail=True)
    run_direct_generation_pipeline(
        "direct-3",
        db,
        settings,
        FixtureFaceEngine(),
        provider,
        get_scene("PANDA_CASUAL_01").full_prompt,
        sleep=lambda _: None,
    )
    job = db.one("SELECT * FROM generation_job WHERE id = ?", ("direct-3",))
    assert job["status"] == "failed"
    assert provider.calls == 2
    assert job["final_path"] is None
    assert "未交付伪造降级图" in job["error_msg"]


def test_provider_failure_uses_remote_fallback(settings):
    db = Database(settings.database_path)
    _seed(settings, db, "direct-4", "ORDER-DIRECT-4")
    primary = MockProvider(fail=True)
    fallback = MockProvider()
    fallback.name = "gemini-image-fallback"
    provider = FallbackProvider(primary, fallback)
    run_direct_generation_pipeline(
        "direct-4",
        db,
        settings,
        FixtureFaceEngine([0.8] * 8),
        provider,
        get_scene("PANDA_CASUAL_01").full_prompt,
        sleep=lambda _: None,
    )
    job = db.one("SELECT * FROM generation_job WHERE id = ?", ("direct-4",))
    assert job["status"] == "review_required"
    assert primary.calls == 1
    assert fallback.calls == 1
    attempt = json.loads(job["attempts_json"])[0]
    assert attempt["provider"] == "gemini-image-fallback"
    assert attempt["fallback"] is True
