from __future__ import annotations

import hashlib
import hmac
import time
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Iterator

from fastapi import Header, HTTPException, status

from .config import Settings


_provider_scope: ContextVar[str | None] = ContextVar("provider_scope", default=None)


def constant_time_equal(given: str | None, expected: str) -> bool:
    return bool(given) and hmac.compare_digest(given.encode(), expected.encode())


def require_luna_token(settings: Settings, jwt_header: str | None) -> None:
    if not constant_time_equal(jwt_header, settings.imageforge_access_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ImageForge 鉴权失败")


def require_internal_token(settings: Settings, token: str | None) -> None:
    if not constant_time_equal(token, settings.imageforge_internal_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="仅允许业务内网调用")


@contextmanager
def generation_provider_scope(job_id: str) -> Iterator[None]:
    marker = _provider_scope.set(f"generation:{job_id}")
    try:
        yield
    finally:
        _provider_scope.reset(marker)


def assert_provider_call_allowed() -> None:
    scope = _provider_scope.get()
    if not scope or not scope.startswith("generation:"):
        raise AssertionError("图片 provider 只能由受控的付费生成 worker 调用")


def sign_delivery(secret: str, job_id: str, filename: str, expires: int) -> str:
    message = f"{job_id}:{filename}:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def validate_delivery_signature(
    secret: str,
    job_id: str,
    filename: str,
    expires: int,
    signature: str,
) -> bool:
    if expires < int(time.time()):
        return False
    expected = sign_delivery(secret, job_id, filename, expires)
    return hmac.compare_digest(expected, signature)


def internal_header(x_internal_token: str | None = Header(default=None)) -> str | None:
    return x_internal_token
