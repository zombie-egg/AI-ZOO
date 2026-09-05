from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Callable

from .config import Settings
from .db import Database
from .face_engine import FaceEngine
from .providers import ImageProvider
from .security import generation_provider_scope
from .storage import (
    create_print_payload,
    image_bytes_to_rgb,
    load_rgb,
    save_jpeg,
    signed_delivery_url,
    upscale_long_edge,
)


class PipelineError(RuntimeError):
    pass


def run_direct_generation_pipeline(
    job_id: str,
    db: Database,
    settings: Settings,
    face_engine: FaceEngine,
    provider: ImageProvider,
    prompt: str,
    sleep: Callable[[float], None] = time.sleep,
    on_state: Callable[[str], None] | None = None,
) -> None:
    """Use four original photos per participant; no template, local swap, or degraded fallback."""
    job = db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
    if not job:
        raise PipelineError("直连生成任务不存在")
    source_paths = [Path(item) for item in json.loads(job["source_paths_json"])]
    participant_groups = json.loads(job.get("participants_json") or "[]")
    if not participant_groups:
        participant_groups = [{"slot": 1, "source_paths": [str(path) for path in source_paths]}]
    participant_count = len(participant_groups)
    valid_groups = all(
        len(group.get("source_paths", [])) == 4 for group in participant_groups
    )
    if not valid_groups or len(source_paths) != participant_count * 4 or any(not path.is_file() for path in source_paths):
        db.update_generation(
            job_id,
            status="failed",
            progress=100,
            eta_seconds=0,
            error_msg="必须为每位参与者提供按固定顺序拍摄的四张有效原图",
        )
        return

    output_dir = settings.private_dir / "generation" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    best_candidate: Path | None = None
    best_score = -1.0
    cost_cents = 0

    for attempt_no in range(1, settings.gpt_attempts + 1):
        db.update_generation(job_id, status="generating", progress=15, eta_seconds=90)
        if on_state:
            on_state("generating")
        record: dict = {
            "attempt": attempt_no,
            "provider": provider.name,
            "participant_count": participant_count,
            "reference_count": len(source_paths),
            "prompt_hash": job["prompt_hash"],
        }
        try:
            with generation_provider_scope(job_id):
                result = provider.generate(
                    prompt,
                    None,
                    "1024x1536",
                    reference_images=[path.read_bytes() for path in source_paths],
                )
            record["provider"] = getattr(provider, "last_provider_name", provider.name)
            if getattr(provider, "used_fallback", False):
                record["fallback"] = True
            cost_cents += settings.gpt_image_estimated_cost_cents
            candidate = output_dir / f"candidate-{attempt_no}.jpg"
            save_jpeg(image_bytes_to_rgb(result), candidate, quality=95)
            db.update_generation(job_id, status="qa", progress=78, eta_seconds=15)
            if on_state:
                on_state("qa")

            if face_engine.production_ready:
                participant_scores = []
                for group in participant_groups:
                    group_sources = [Path(item) for item in group["source_paths"]]
                    scores = [face_engine.similarity(source, candidate) for source in group_sources]
                    top_scores = sorted(scores, reverse=True)[:2]
                    participant_scores.append({
                        "slot": int(group["slot"]),
                        "scores": [round(score, 4) for score in scores],
                        "identity_score": round(float(statistics.mean(top_scores)), 4),
                    })
                identity_score = min(item["identity_score"] for item in participant_scores)
                record.update(
                    participant_identity=participant_scores,
                    identity_score=round(identity_score, 4),
                    identity_threshold=settings.lock_threshold,
                )
            else:
                identity_score = 1.0
                record.update(
                    identity_score=None,
                    identity_qa="manual-review-required",
                    reason="本机 local-dev 不具备真人身份验收资格",
                )

            if identity_score > best_score:
                best_candidate = candidate
                best_score = identity_score
            if not face_engine.production_ready or identity_score >= settings.lock_threshold:
                record["result"] = "candidate-ready"
                attempts.append(record)
                break
            record["result"] = "identity-drift"
            attempts.append(record)
            if attempt_no < settings.gpt_attempts:
                sleep(2)
        except Exception as exc:
            record.update(result="error", error=type(exc).__name__, message=str(exc)[:300])
            attempts.append(record)
            if attempt_no < settings.gpt_attempts:
                sleep(2)

    if best_candidate is None:
        db.update_generation(
            job_id,
            status="failed",
            progress=100,
            eta_seconds=0,
            attempts_json=json.dumps(attempts, ensure_ascii=False),
            cost_cents=cost_cents,
            error_msg="主图片服务及 Gemini 兜底连续生成失败；系统未交付伪造降级图",
        )
        if on_state:
            on_state("failed")
        return

    final_path = output_dir / "gpt-image-2-final.jpg"
    print_path = output_dir / "print_payload.html"
    # 保留模型原始成品，只做无损比例放大；不再叠加任何角标或文字。
    final_image = upscale_long_edge(load_rgb(best_candidate), 2048)
    save_jpeg(final_image, final_path, quality=95)
    final_url = signed_delivery_url(settings, job_id, final_path.name)
    create_print_payload(final_url, job["order_no"], print_path, image_path=final_path)
    qa_payload = {
        "manual_review_required": True,
        "identity_engine": face_engine.name,
        "identity_engine_production_ready": face_engine.production_ready,
        "best_identity_score": None if not face_engine.production_ready else round(best_score, 4),
        "participant_count": participant_count,
        "reference_count": len(source_paths),
        "participant_review_required": list(range(1, participant_count + 1)),
    }
    db.update_generation(
        job_id,
        status="review_required",
        progress=100,
        eta_seconds=0,
        final_path=str(final_path),
        print_payload_path=str(print_path),
        attempts_json=json.dumps(attempts, ensure_ascii=False),
        qa_json=json.dumps(qa_payload, ensure_ascii=False),
        cost_cents=cost_cents,
        error_msg=None,
    )
    if on_state:
        on_state("review_required")
