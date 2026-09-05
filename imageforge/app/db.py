from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS uploaded_asset (
    file_id TEXT PRIMARY KEY,
    face_id TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    quality_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_job (
    id TEXT PRIMARY KEY,
    order_no TEXT NOT NULL UNIQUE,
    scene_id TEXT NOT NULL,
    pose_id TEXT NOT NULL DEFAULT 'FRONT',
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    source_paths_json TEXT NOT NULL,
    participants_json TEXT NOT NULL DEFAULT '[]',
    sku TEXT,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    eta_seconds INTEGER NOT NULL DEFAULT 0,
    provider TEXT,
    final_path TEXT,
    print_payload_path TEXT,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    attempts_json TEXT NOT NULL DEFAULT '[]',
    qa_json TEXT NOT NULL DEFAULT '{}',
    error_msg TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_status ON generation_job(status, created_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(generation_job)")}
            if "pose_id" not in columns:
                conn.execute(
                    "ALTER TABLE generation_job ADD COLUMN pose_id TEXT NOT NULL DEFAULT 'FRONT'"
                )
            if "participants_json" not in columns:
                conn.execute(
                    "ALTER TABLE generation_job ADD COLUMN participants_json TEXT NOT NULL DEFAULT '[]'"
                )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock, self.connection() as conn:
            conn.execute(sql, params)

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def create_generation(self, values: dict[str, Any]) -> bool:
        timestamp = now_iso()
        try:
            self.execute(
                """INSERT INTO generation_job
                (id, order_no, scene_id, pose_id, prompt_version, prompt_hash, source_paths_json, participants_json,
                 sku, status, progress, eta_seconds, provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, ?)""",
                (
                    values["id"],
                    values["order_no"],
                    values["scene_id"],
                    values.get("pose_id", "FRONT"),
                    values["prompt_version"],
                    values["prompt_hash"],
                    json.dumps(values["source_paths"], ensure_ascii=False),
                    json.dumps(values.get("participants", []), ensure_ascii=False),
                    values.get("sku"),
                    values.get("eta_seconds", 90),
                    values.get("provider"),
                    timestamp,
                    timestamp,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_generation(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = now_iso()
        clauses = ", ".join(f"{key} = ?" for key in fields)
        self.execute(
            f"UPDATE generation_job SET {clauses} WHERE id = ?",  # noqa: S608
            tuple(fields.values()) + (job_id,),
        )

    def queue_depth(self) -> int:
        with self.connection() as conn:
            generation = conn.execute(
                "SELECT COUNT(*) FROM generation_job WHERE status IN ('queued','generating','qa')"
            ).fetchone()[0]
        return int(generation)
