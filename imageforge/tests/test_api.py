from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from app.db import now_iso
from app.main import create_app

from conftest import FixtureFaceEngine, FixtureQuality, make_portrait


def _internal(settings):
    return {"X-Internal-Token": settings.imageforge_internal_token}


def _seed_four_references(service, settings, prefix: str) -> list[str]:
    face_ids: list[str] = []
    for index in range(4):
        file_id = f"{prefix}{index}01"
        face_id = f"{prefix}{index}11"
        source = make_portrait(
            settings.private_dir / "uploads" / f"{file_id}.jpg",
            (170 + index * 3, 140 + index * 2, 110 + index),
        )
        service.db.execute(
            """INSERT INTO uploaded_asset(file_id, face_id, path, quality_json, created_at)
            VALUES (?,?,?,?,?)""",
            (file_id, face_id, str(source), "{}", now_iso()),
        )
        face_ids.append(face_id)
    return face_ids


def test_direct_four_reference_generation_and_approval(settings):
    app = create_app(settings)
    service = app.state.imageforge
    service.face_engine = FixtureFaceEngine([0.82] * 12)
    service.quality = FixtureQuality(True)
    face_ids = _seed_four_references(service, settings, "91")

    with TestClient(app) as client:
        catalog = client.get("/v4/scenes", headers=_internal(settings))
        assert catalog.status_code == 200
        scene = catalog.json()["scenes"][0]
        pose = catalog.json()["poses"][1]
        assert "prompt" not in scene
        assert pose["pose_id"] == "SIDE"

        created = client.post(
            "/v4/generations",
            headers=_internal(settings),
            json={
                "order_no": "DIRECT-ORDER-1",
                "scene_id": scene["scene_id"],
                "pose_id": pose["pose_id"],
                "face_ids": face_ids,
                "sku": "print_1",
            },
        )
        assert created.status_code == 200
        job_id = created.json()["generation_id"]
        assert created.json()["reference_count"] == 4
        assert created.json()["pose_id"] == "SIDE"
        assert "+side-pose-v1" in created.json()["prompt_version"]

        for _ in range(100):
            state = client.get(f"/v4/generations/{job_id}", headers=_internal(settings)).json()
            if state["status"] in {"review_required", "failed"}:
                break
            time.sleep(0.01)
        assert state["status"] == "review_required"
        assert "final_url" in state
        assert "print_payload" not in state

        approved = client.post(
            f"/v4/generations/{job_id}/approve", headers=_internal(settings)
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "done"
        assert "print_payload" in approved.json()
        print_payload = client.get(
            approved.json()["print_payload"],
            headers={"Origin": "http://127.0.0.1:4175"},
        )
        assert print_payload.status_code == 200
        assert print_payload.headers["access-control-allow-origin"] == "http://127.0.0.1:4175"


def test_generation_is_idempotent_per_order(settings):
    app = create_app(settings)
    service = app.state.imageforge
    service.face_engine = FixtureFaceEngine([0.82] * 12)
    face_ids = _seed_four_references(service, settings, "92")
    payload = {
        "order_no": "DIRECT-IDEMPOTENT-1",
        "scene_id": "PANDA_CASUAL_01",
        "pose_id": "BACK",
        "face_ids": face_ids,
        "sku": "print_1",
    }
    with TestClient(app) as client:
        first = client.post("/v4/generations", headers=_internal(settings), json=payload)
        second = client.post("/v4/generations", headers=_internal(settings), json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["generation_id"] == second.json()["generation_id"]
        assert second.json()["idempotent"] is True


def test_generation_requires_four_distinct_references(settings):
    app = create_app(settings)
    service = app.state.imageforge
    face_ids = _seed_four_references(service, settings, "93")
    with TestClient(app) as client:
        response = client.post(
            "/v4/generations",
            headers=_internal(settings),
            json={
                "order_no": "DIRECT-BAD-COUNT",
                "scene_id": "PANDA_CASUAL_01",
                "face_ids": [face_ids[0]] * 4,
            },
        )
        assert response.status_code == 422
        assert "不能重复" in response.json()["msg"]


def test_direct_endpoints_require_internal_token(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/v4/scenes").status_code == 401
        assert client.get("/v4/generations/not-found").status_code == 401


def test_generation_rejects_unknown_pose(settings):
    app = create_app(settings)
    service = app.state.imageforge
    face_ids = _seed_four_references(service, settings, "94")
    with TestClient(app) as client:
        response = client.post(
            "/v4/generations",
            headers=_internal(settings),
            json={
                "order_no": "DIRECT-BAD-POSE",
                "scene_id": "PANDA_CASUAL_01",
                "pose_id": "UPSIDE_DOWN",
                "face_ids": face_ids,
            },
        )
        assert response.status_code == 422
        assert "姿势" in response.json()["msg"]


def test_two_participants_are_stored_as_separate_reference_groups(settings):
    app = create_app(settings)
    service = app.state.imageforge
    service.face_engine = FixtureFaceEngine([0.82] * 24)
    first = _seed_four_references(service, settings, "95")
    second = _seed_four_references(service, settings, "96")
    with TestClient(app) as client:
        response = client.post(
            "/v4/generations",
            headers=_internal(settings),
            json={
                "order_no": "DIRECT-TWO-PEOPLE",
                "scene_id": "PANDA_CASUAL_01",
                "pose_id": "FRONT",
                "participants": [
                    {"slot": 1, "face_ids": first},
                    {"slot": 2, "face_ids": second},
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["participant_count"] == 2
        assert response.json()["reference_count"] == 8
        assert "+group-2-v1" in response.json()["prompt_version"]
        job = service.db.one(
            "SELECT participants_json FROM generation_job WHERE id = ?",
            (response.json()["generation_id"],),
        )
        groups = json.loads(job["participants_json"])
        assert [group["slot"] for group in groups] == [1, 2]
        assert all(len(group["source_paths"]) == 4 for group in groups)


def test_participant_slots_must_be_contiguous(settings):
    app = create_app(settings)
    service = app.state.imageforge
    first = _seed_four_references(service, settings, "97")
    second = _seed_four_references(service, settings, "98")
    with TestClient(app) as client:
        response = client.post(
            "/v4/generations",
            headers=_internal(settings),
            json={
                "order_no": "DIRECT-BAD-SLOTS",
                "scene_id": "PANDA_CASUAL_01",
                "participants": [
                    {"slot": 1, "face_ids": first},
                    {"slot": 3, "face_ids": second},
                ],
            },
        )
        assert response.status_code == 422
        assert "连续排列" in response.json()["msg"]
