from __future__ import annotations

import json
import secrets
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import Body, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings, load_settings
from .db import Database, now_iso
from .face_engine import FaceEngine, build_face_engine
from .pipelines import run_direct_generation_pipeline
from .providers import build_provider
from .quality import QualityInspector
from .scene_catalog import (
    compose_generation_prompt,
    composed_prompt_hash,
    composed_prompt_version,
    get_pose,
    get_scene,
    public_poses,
    public_scenes,
)
from .schemas import DirectGenerationRequest
from .security import (
    constant_time_equal,
    require_internal_token,
    require_luna_token,
    validate_delivery_signature,
)
from .storage import signed_delivery_url


def _numeric_id() -> str:
    return str(secrets.randbelow(8_999_999_999) + 1_000_000_000)


class ImageForgeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.prepare_directories()
        self.db = Database(settings.database_path)
        self.quality = QualityInspector(settings)
        self.face_engine: FaceEngine = build_face_engine(settings)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="imageforge-direct")
        self._submitted: set[str] = set()
        self._lock = threading.Lock()

    def submit_generation(self, job_id: str) -> None:
        marker = f"generation:{job_id}"
        with self._lock:
            if marker in self._submitted:
                return
            self._submitted.add(marker)

        def runner() -> None:
            try:
                job = self.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
                if not job:
                    return
                scene = get_scene(job["scene_id"])
                pose = get_pose(job["pose_id"])
                participants = json.loads(job.get("participants_json") or "[]")
                participant_count = len(participants) or 1
                provider = build_provider(self.settings)
                run_direct_generation_pipeline(
                    job_id,
                    self.db,
                    self.settings,
                    self.face_engine,
                    provider,
                    compose_generation_prompt(scene, pose, participant_count),
                )
            except Exception as exc:
                self.db.update_generation(
                    job_id,
                    status="failed",
                    progress=100,
                    eta_seconds=0,
                    error_msg=str(exc)[:500],
                )
            finally:
                with self._lock:
                    self._submitted.discard(marker)

        self.executor.submit(runner)

    def recover_queued(self) -> None:
        rows = self.db.all(
            """SELECT id FROM generation_job
            WHERE status IN ('queued','generating','qa') ORDER BY created_at ASC"""
        )
        for row in rows:
            self.submit_generation(row["id"])

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)


def _generation_response(service: ImageForgeService, job: dict[str, Any]) -> dict[str, Any]:
    response: dict[str, Any] = {
        "generation_id": job["id"],
        "order_no": job["order_no"],
        "scene_id": job["scene_id"],
        "pose_id": job["pose_id"],
        "participant_count": len(json.loads(job.get("participants_json") or "[]")) or 1,
        "prompt_version": job["prompt_version"],
        "prompt_hash": job["prompt_hash"],
        "reference_count": len(json.loads(job["source_paths_json"])),
        "status": job["status"],
        "progress": job["progress"],
        "eta_seconds": job["eta_seconds"],
        "cost_cents": job["cost_cents"],
        "error_msg": job.get("error_msg"),
    }
    if job.get("final_path"):
        response["final_url"] = signed_delivery_url(
            service.settings, job["id"], Path(job["final_path"]).name
        )
    if job["status"] == "done" and job.get("print_payload_path"):
        response["print_payload"] = signed_delivery_url(
            service.settings, job["id"], Path(job["print_payload_path"]).name
        )
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or load_settings()
    service = ImageForgeService(current)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        service.recover_queued()
        yield
        service.close()

    app = FastAPI(title="ImageForge Direct", version="0.5.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current.cors_allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.state.imageforge = service

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": 4000 + exc.status_code, "msg": str(exc.detail), "detail": None},
        )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        usage = shutil.disk_usage(current.private_dir)
        active_provider = build_provider(current)
        return {
            "ok": usage.free > 256 * 1024 * 1024,
            "database": "ok",
            "queue_depth": service.db.queue_depth(),
            "disk_free_mb": round(usage.free / 1024 / 1024),
            "pipeline": f"{active_provider.name}-direct-multi-reference",
            "reference_count": "4 per participant",
            "max_participants": 4,
            "templates_enabled": False,
            "free_preview_enabled": False,
            "face_engine": service.face_engine.name,
            "face_engine_production_ready": service.face_engine.production_ready,
            "provider_configured": (
                current.fallback_provider_configured
                if active_provider.name == "gemini-image"
                else bool(current.provider_token)
            ),
            "active_provider": active_provider.name,
            "fallback_provider_configured": current.fallback_provider_configured,
            "fallback_provider_model": (
                current.fallback_image_model if current.fallback_provider_configured else None
            ),
        }

    @app.post("/api/app/authentication")
    def luna_auth(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        valid = constant_time_equal(str(payload.get("secret", "")), current.imageforge_secret)
        valid = valid and constant_time_equal(
            str(payload.get("secretKey", "")), current.imageforge_secret_key
        )
        if not valid:
            return {"code": 4001, "message": "ImageForge 凭据错误", "data": None}
        return {
            "code": 1,
            "message": "success",
            "data": {"accessToken": current.imageforge_access_token},
        }

    @app.post("/api/userMessage/checkUserImageUpload")
    async def luna_upload(
        file: UploadFile = File(...),
        jwt_header: str | None = Header(default=None, alias="JWTHEADER"),
    ) -> dict[str, Any]:
        require_luna_token(current, jwt_header)
        extension = Path(file.filename or "photo.jpg").suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            return {"code": 9001, "message": "仅支持 JPG、PNG、WEBP 图片", "data": None}
        payload = await file.read()
        if not payload or len(payload) > 16 * 1024 * 1024:
            return {"code": 9001, "message": "图片为空或超过 16MB", "data": None}
        file_id, face_id = _numeric_id(), _numeric_id()
        upload_path = current.private_dir / "uploads" / f"{file_id}{extension}"
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        upload_path.write_bytes(payload)
        inspected = service.quality.inspect(upload_path)
        if not inspected.ok:
            upload_path.unlink(missing_ok=True)
            code = 9001 if inspected.face_count == 0 else 9007
            return {"code": code, "message": "；".join(inspected.reasons), "data": None}
        service.db.execute(
            """INSERT INTO uploaded_asset(file_id, face_id, path, quality_json, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (
                file_id,
                face_id,
                str(upload_path),
                json.dumps(inspected.to_dict(), ensure_ascii=False),
                now_iso(),
            ),
        )
        return {
            "code": 1,
            "message": "success",
            "data": {
                "id": int(file_id),
                "fileFaceList": [{"id": int(face_id), "is_default": 1}],
                "quality": inspected.to_dict(),
            },
        }

    @app.get("/v4/scenes")
    def scenes(x_internal_token: str | None = Header(default=None)) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        return {"scenes": public_scenes(), "poses": public_poses()}

    @app.get("/v4/gallery")
    def generated_gallery(
        limit: int = Query(default=60, ge=1, le=100),
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        jobs = service.db.all(
            """SELECT * FROM generation_job
            WHERE final_path IS NOT NULL AND final_path <> ''
              AND status IN ('review_required', 'done')
            ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        )
        photos = []
        for job in jobs:
            final_path = Path(job["final_path"])
            if not final_path.is_file():
                continue
            photos.append(
                {
                    "src": signed_delivery_url(current, job["id"], final_path.name),
                    "label": job["scene_id"],
                    "scene_id": job["scene_id"],
                    "pose_id": job["pose_id"],
                    "order_no": job["order_no"],
                    "created_at": job["created_at"],
                }
            )
        return {"photos": photos}

    @app.post("/v4/generations")
    def create_generation(
        payload: DirectGenerationRequest,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        try:
            scene = get_scene(payload.scene_id)
            pose = get_pose(payload.pose_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        requested_groups = payload.participants
        if not requested_groups and payload.face_ids:
            requested_groups = [{"slot": 1, "face_ids": payload.face_ids}]
        if not requested_groups:
            raise HTTPException(status_code=422, detail="至少需要一位参与者的四张参考照片")
        normalized_groups = [
            group.model_dump() if hasattr(group, "model_dump") else dict(group)
            for group in requested_groups
        ]
        slots = [int(group["slot"]) for group in normalized_groups]
        if sorted(slots) != list(range(1, len(normalized_groups) + 1)):
            raise HTTPException(status_code=422, detail="参与者编号必须从 1 连续排列")
        all_face_ids = [str(face_id) for group in normalized_groups for face_id in group["face_ids"]]
        if len(set(all_face_ids)) != len(all_face_ids):
            raise HTTPException(status_code=422, detail="不同参与者的参考照片不能重复或混用")
        source_paths: list[str] = []
        stored_participants: list[dict[str, Any]] = []
        for group in normalized_groups:
            group_paths: list[str] = []
            for face_id in group["face_ids"]:
                asset = service.db.one(
                    "SELECT path FROM uploaded_asset WHERE face_id = ?", (str(face_id),)
                )
                if not asset:
                    raise HTTPException(status_code=422, detail=f"参考照片不存在：{face_id}")
                source_paths.append(asset["path"])
                group_paths.append(asset["path"])
            stored_participants.append({"slot": int(group["slot"]), "source_paths": group_paths})
        participant_count = len(stored_participants)

        existing = service.db.one(
            "SELECT * FROM generation_job WHERE order_no = ?", (payload.order_no,)
        )
        if existing:
            response = _generation_response(service, existing)
            response["idempotent"] = True
            return response

        job_id = secrets.token_hex(12)
        created = service.db.create_generation(
            {
                "id": job_id,
                "order_no": payload.order_no,
                "scene_id": scene.scene_id,
                "pose_id": pose.pose_id,
                "prompt_version": composed_prompt_version(scene, pose, participant_count),
                "prompt_hash": composed_prompt_hash(scene, pose, participant_count),
                "source_paths": source_paths,
                "participants": stored_participants,
                "sku": payload.sku,
                "eta_seconds": 90,
                "provider": current.gpt_image_model,
            }
        )
        if not created:
            existing = service.db.one(
                "SELECT * FROM generation_job WHERE order_no = ?", (payload.order_no,)
            )
            if not existing:
                raise HTTPException(status_code=409, detail="订单生成任务创建冲突")
            response = _generation_response(service, existing)
            response["idempotent"] = True
            return response
        service.submit_generation(job_id)
        job = service.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
        response = _generation_response(service, job)
        response["idempotent"] = False
        return response

    @app.get("/v4/generations/{job_id}")
    def generation_status(
        job_id: str,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        job = service.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
        if not job:
            raise HTTPException(status_code=404, detail="直连生成任务不存在")
        return _generation_response(service, job)

    @app.post("/v4/generations/{job_id}/approve")
    def approve_generation(
        job_id: str,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        job = service.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
        if not job:
            raise HTTPException(status_code=404, detail="直连生成任务不存在")
        if job["status"] not in {"review_required", "done"}:
            raise HTTPException(status_code=409, detail="成品尚未生成，不能确认打印")
        if job["status"] != "done":
            service.db.update_generation(job_id, status="done")
            job = service.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
        return _generation_response(service, job)

    @app.get("/v4/generations/{job_id}/debug")
    def generation_debug(
        job_id: str,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        job = service.db.one("SELECT * FROM generation_job WHERE id = ?", (job_id,))
        if not job:
            raise HTTPException(status_code=404, detail="直连生成任务不存在")
        return {
            "generation_id": job["id"],
            "order_no": job["order_no"],
            "scene_id": job["scene_id"],
            "pose_id": job["pose_id"],
            "participant_count": len(json.loads(job.get("participants_json") or "[]")) or 1,
            "prompt_version": job["prompt_version"],
            "prompt_hash": job["prompt_hash"],
            "reference_count": len(json.loads(job["source_paths_json"])),
            "status": job["status"],
            "attempts": json.loads(job["attempts_json"]),
            "qa": json.loads(job["qa_json"]),
            "cost_cents": job["cost_cents"],
            "error_msg": job["error_msg"],
        }

    @app.get("/internal/provider-capability")
    def provider_capability(
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        if not current.provider_token:
            return {
                "configured": False,
                "reachable": False,
                "model_visible": False,
                "references_per_participant": 4,
                "max_participants": 4,
            }
        try:
            response = httpx.get(
                f"{current.provider_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {current.provider_token}"},
                timeout=10,
            )
            payload = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            models = (
                [str(item.get("id", "")) for item in payload.get("data", [])]
                if isinstance(payload, dict)
                else []
            )
            return {
                "configured": True,
                "reachable": response.status_code < 500,
                "http_status": response.status_code,
                "model_visible": current.gpt_image_model in models,
                "model_count": len(models),
                "references_per_participant": 4,
                "max_participants": 4,
                "single_image_fallback": False,
            }
        except (httpx.HTTPError, ValueError):
            return {
                "configured": True,
                "reachable": False,
                "model_visible": False,
                "references_per_participant": 4,
                "max_participants": 4,
                "single_image_fallback": False,
            }

    @app.delete("/internal/orders/{order_no}")
    def delete_order_media(
        order_no: str,
        x_internal_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_internal_token(current, x_internal_token)
        jobs = service.db.all("SELECT * FROM generation_job WHERE order_no = ?", (order_no,))
        deleted_files = 0

        def remove_managed_file(value: str | None) -> None:
            nonlocal deleted_files
            if not value:
                return
            candidate = Path(value).resolve()
            root = current.private_dir.resolve()
            if candidate != root and not candidate.is_relative_to(root):
                raise HTTPException(status_code=409, detail="拒绝删除非 ImageForge 私有目录文件")
            if candidate.is_file():
                candidate.unlink()
                deleted_files += 1

        for job in jobs:
            source_paths = json.loads(job["source_paths_json"])
            for source_path in source_paths:
                remove_managed_file(source_path)
                service.db.execute("DELETE FROM uploaded_asset WHERE path = ?", (source_path,))
            remove_managed_file(job.get("final_path"))
            remove_managed_file(job.get("print_payload_path"))
            job_dir = current.private_dir / "generation" / job["id"]
            if job_dir.is_dir():
                for child in job_dir.iterdir():
                    remove_managed_file(str(child))
                job_dir.rmdir()
            service.db.execute("DELETE FROM generation_job WHERE id = ?", (job["id"],))
        return {"deleted": True, "order_no": order_no, "deleted_files": deleted_files}

    @app.get("/private-delivery/{job_id}/{filename}")
    def private_delivery(
        job_id: str,
        filename: str,
        expires: int = Query(...),
        sig: str = Query(...),
    ) -> FileResponse:
        safe_name = Path(filename).name
        if safe_name != filename or not validate_delivery_signature(
            current.signing_secret, job_id, safe_name, expires, sig
        ):
            raise HTTPException(status_code=403, detail="下载链接无效或已过期")
        job = service.db.one(
            "SELECT final_path, print_payload_path FROM generation_job WHERE id = ?", (job_id,)
        )
        if not job:
            raise HTTPException(status_code=404, detail="直连生成任务不存在")
        allowed = {
            str(Path(item).resolve())
            for item in (job.get("final_path"), job.get("print_payload_path"))
            if item
        }
        candidate = (current.private_dir / "generation" / job_id / safe_name).resolve()
        if str(candidate) not in allowed or not candidate.exists():
            raise HTTPException(status_code=404, detail="交付文件不存在")
        media = "text/html; charset=utf-8" if candidate.suffix == ".html" else "image/jpeg"
        return FileResponse(candidate, media_type=media, filename=safe_name)

    return app


app = create_app()
