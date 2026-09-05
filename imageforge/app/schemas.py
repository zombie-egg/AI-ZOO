from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FinalizeRequest(BaseModel):
    order_no: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    sku: str = Field(default="6inch", max_length=40)


class ParticipantReferences(BaseModel):
    slot: int = Field(ge=1, le=4)
    face_ids: list[str] = Field(min_length=4, max_length=4)


class DirectGenerationRequest(BaseModel):
    order_no: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    scene_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Z0-9_]+$")
    pose_id: str = Field(default="FRONT", min_length=4, max_length=32, pattern=r"^[A-Z_]+$")
    participants: list[ParticipantReferences] = Field(default_factory=list, max_length=4)
    face_ids: list[str] = Field(default_factory=list, max_length=4)
    sku: str = Field(default="print_1", max_length=40)


class ErrorPayload(BaseModel):
    code: int
    msg: str
    detail: Any | None = None
