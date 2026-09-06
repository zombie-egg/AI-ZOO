from __future__ import annotations

import re
import os
import asyncio
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import socketio


TERMINAL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
MAX_HTML_CHARS = 15 * 1024 * 1024
PUBLIC_HOST = urlparse(
    os.getenv("PUBLIC_BASE_URL", "https://ai-zoo-zombie.zeabur.app")
).hostname
PRIVATE_ROOT = Path(os.getenv("PRIVATE_DIR", "/data/imageforge/private"))
PRINT_FRAGMENT_CHARS = 48 * 1024
PRINT_FRAGMENT_ACK_TIMEOUT_SECONDS = 30
PRINT_FRAGMENT_RETRIES = 6


def _valid_print_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 4096:
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == PUBLIC_HOST
        and parsed.path.startswith("/private-delivery/")
        and parsed.path.endswith("/print_payload.html")
        and bool(parsed.query)
    )


def _generation_id_from_print_url(value: str) -> str | None:
    if not _valid_print_url(value):
        return None
    match = re.fullmatch(
        r"/private-delivery/([A-Za-z0-9_-]{8,128})/print_payload\.html",
        urlparse(value).path,
    )
    return match.group(1) if match else None

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    max_http_buffer_size=16 * 1024 * 1024,
    ping_interval=20,
    ping_timeout=20,
)

agents: dict[str, str] = {}
connections: dict[str, tuple[str, str]] = {}
kiosks: dict[str, set[str]] = defaultdict(set)


def _identity(auth: Any) -> tuple[str, str] | None:
    if not isinstance(auth, dict):
        return None
    role = str(auth.get("role", ""))
    terminal_id = str(auth.get("terminalId", ""))
    if role not in {"agent", "kiosk"} or not TERMINAL_ID_RE.fullmatch(terminal_id):
        return None
    return role, terminal_id


async def _notify_agent_status(terminal_id: str, online: bool) -> None:
    await sio.emit(
        "agentStatus",
        {"online": online},
        room=f"kiosk:{terminal_id}",
    )


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool:
    identity = _identity(auth)
    if identity is None:
        return False

    role, terminal_id = identity
    connections[sid] = identity
    await sio.enter_room(sid, f"{role}:{terminal_id}")

    if role == "agent":
        previous = agents.get(terminal_id)
        agents[terminal_id] = sid
        if previous and previous != sid:
            await sio.disconnect(previous)
        await _notify_agent_status(terminal_id, True)
    else:
        kiosks[terminal_id].add(sid)
        agent_sid = agents.get(terminal_id)
        await sio.emit("agentStatus", {"online": bool(agent_sid)}, to=sid)
        if agent_sid:
            await sio.emit("refreshPrinterList", to=agent_sid)
    return True


@sio.event
async def disconnect(sid: str) -> None:
    identity = connections.pop(sid, None)
    if identity is None:
        return
    role, terminal_id = identity
    if role == "agent" and agents.get(terminal_id) == sid:
        agents.pop(terminal_id, None)
        await _notify_agent_status(terminal_id, False)
    elif role == "kiosk":
        kiosks[terminal_id].discard(sid)
        if not kiosks[terminal_id]:
            kiosks.pop(terminal_id, None)


def _agent_for_kiosk(sid: str) -> str | None:
    identity = connections.get(sid)
    if not identity or identity[0] != "kiosk":
        return None
    return agents.get(identity[1])


def _terminal_for_agent(sid: str) -> str | None:
    identity = connections.get(sid)
    if not identity or identity[0] != "agent":
        return None
    return identity[1]


async def _send_print_fragment_with_ack(
    terminal_id: str,
    fragment_payload: dict[str, Any],
) -> None:
    last_error: Exception | None = None
    for attempt in range(PRINT_FRAGMENT_RETRIES):
        agent_sid = agents.get(terminal_id)
        if not agent_sid:
            last_error = RuntimeError("本机打印服务已离线")
            await asyncio.sleep(min(2 + attempt, 5))
            continue
        try:
            response = await sio.call(
                "printByFragments",
                fragment_payload,
                to=agent_sid,
                timeout=PRINT_FRAGMENT_ACK_TIMEOUT_SECONDS,
            )
            if isinstance(response, dict) and response.get("ok") is True:
                return
            message = response.get("message") if isinstance(response, dict) else None
            last_error = RuntimeError(message or "本机打印服务未确认排版分片")
        except Exception as error:
            last_error = error
        await asyncio.sleep(min(1 + attempt, 5))
    raise RuntimeError(f"打印排版传输失败：{last_error or '本机打印服务无响应'}")


@sio.on("refreshPrinterList")
async def refresh_printer_list(sid: str) -> None:
    agent_sid = _agent_for_kiosk(sid)
    if agent_sid:
        await sio.emit("refreshPrinterList", to=agent_sid)


@sio.on("getClientInfo")
async def get_client_info(sid: str) -> None:
    agent_sid = _agent_for_kiosk(sid)
    if agent_sid:
        await sio.emit("getClientInfo", to=agent_sid)


@sio.on("news")
async def print_job(sid: str, payload: Any) -> None:
    agent_sid = _agent_for_kiosk(sid)
    if not agent_sid:
        await sio.emit(
            "error",
            {"message": "此终端的后台打印服务未连接"},
            to=sid,
        )
        return
    if not isinstance(payload, dict):
        await sio.emit("error", {"message": "打印任务格式无效"}, to=sid)
        return
    html = payload.get("html")
    html_url = payload.get("htmlUrl")
    has_inline_html = isinstance(html, str) and bool(html) and len(html) <= MAX_HTML_CHARS
    if not has_inline_html and not _valid_print_url(html_url):
        await sio.emit("error", {"message": "打印内容或签名下载地址无效"}, to=sid)
        return

    safe_payload = dict(payload)
    safe_payload["copies"] = 1
    safe_payload["pageRanges"] = {"from": 0, "to": 0}
    if has_inline_html:
        await sio.emit("news", safe_payload, to=agent_sid)
        return

    generation_id = _generation_id_from_print_url(str(html_url))
    print_path = PRIVATE_ROOT / "generation" / str(generation_id) / "print_payload.html"
    try:
        print_html = await asyncio.to_thread(print_path.read_text, encoding="utf-8")
    except (OSError, UnicodeError) as error:
        await sio.emit(
            "error",
            {"templateId": payload.get("templateId"), "message": f"服务器读取打印排版失败：{error}"},
            to=sid,
        )
        return
    if not print_html or len(print_html) > MAX_HTML_CHARS:
        await sio.emit(
            "error",
            {"templateId": payload.get("templateId"), "message": "服务器打印排版为空或过大"},
            to=sid,
        )
        return

    safe_payload.pop("htmlUrl", None)
    fragment_id = uuid.uuid4().hex
    fragments = [
        print_html[index : index + PRINT_FRAGMENT_CHARS]
        for index in range(0, len(print_html), PRINT_FRAGMENT_CHARS)
    ]
    identity = connections.get(sid)
    terminal_id = identity[1] if identity and identity[0] == "kiosk" else None
    if not terminal_id:
        return
    try:
        for index, fragment in enumerate(fragments):
            await _send_print_fragment_with_ack(
                terminal_id,
                {
                    **safe_payload,
                    "id": fragment_id,
                    "total": len(fragments),
                    "index": index,
                    "htmlFragment": fragment,
                },
            )
    except RuntimeError as error:
        await sio.emit(
            "error",
            {"templateId": payload.get("templateId"), "message": str(error)},
            to=sid,
        )


for event_name in (
    "printerList",
    "clientInfo",
    "success",
    "successs",
    "error",
    "printStatus",
    "printStatusError",
):

    async def forward_from_agent(sid: str, payload: Any, event: str = event_name) -> None:
        terminal_id = _terminal_for_agent(sid)
        if terminal_id:
            await sio.emit(event, payload, room=f"kiosk:{terminal_id}")

    sio.on(event_name)(forward_from_agent)


app = socketio.ASGIApp(sio, socketio_path="socket.io")
