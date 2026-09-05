from __future__ import annotations

import json
from pathlib import Path

from app.db import Database
from app.pipelines import run_direct_generation_pipeline
from app.providers import FallbackProvider, MockProvider
from app.scene_catalog import compose_generation_prompt, get_pose, get_scene

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


def test_scene_prompt_requests_visible_smart_beauty_retouching():
    prompt = compose_generation_prompt(get_scene("PANDA_CASUAL_01"), get_pose("FRONT"))
    assert "clearly visible, strong yet" in prompt
    assert "visibly brighten and whiten" in prompt
    assert "noticeable, even skin smoothing" in prompt
    assert "approximately 10–15%" in prompt
    assert "must not look wider or heavier" in prompt
    assert "noticeably reduce dark circles" in prompt
    assert "Never create an extreme" in prompt


def test_each_pose_has_distinct_coherent_instruction_and_keeps_beauty():
    scene = get_scene("PANDA_CASUAL_01")
    front = compose_generation_prompt(scene, get_pose("FRONT"))
    side = compose_generation_prompt(scene, get_pose("SIDE"))
    back = compose_generation_prompt(scene, get_pose("BACK"))
    assert "shoulders nearly parallel" in front
    assert "45–60 degrees" in side
    assert "20–35 degrees" in back
    for prompt in (front, side, back):
        assert "FACE SLIMMING AND CONTOUR — HIGH PRIORITY" in prompt
        assert "SKIN WHITENING AND TONE" in prompt


def test_multi_person_prompt_locks_each_identity_and_group_layout():
    prompt = compose_generation_prompt(
        get_scene("PANDA_CASUAL_01"), get_pose("SIDE"), participant_count=3
    )
    assert "exactly 3 human visitors" in prompt
    assert "PERSON 1: use ONLY reference group 1" in prompt
    assert "PERSON 2: use ONLY reference group 2" in prompt
    assert "PERSON 3: use ONLY reference group 3" in prompt
    assert "three visitors in a shallow triangular arrangement" in prompt
    assert "10–15% face-slimming treatment independently to every visible face" in prompt


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
