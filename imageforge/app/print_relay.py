from __future__ import annotations

import re
import os
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import socketio


TERMINAL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
MAX_HTML_CHARS = 15 * 1024 * 1024
PUBLIC_HOST = urlparse(
    os.getenv("PUBLIC_BASE_URL", "https://ai-zoo-zombie.zeabur.app")
).hostname


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
    await sio.emit("news", safe_payload, to=agent_sid)


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
