from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ProfileRepository:
    """SQLite user_profile 저장소 (실 프로젝트 연동 전용 로컬 스텁)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT PRIMARY KEY,
                    adiga_payload TEXT NOT NULL,
                    extracted_scores TEXT NOT NULL,
                    completed_scores TEXT NOT NULL,
                    estimated_subjects TEXT NOT NULL,
                    latest_message TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_profile(
        self,
        user_id: str,
        adiga_payload: Dict[str, Any],
        extracted_scores: Dict[str, Any],
        completed_scores: Dict[str, Any],
        estimated_subjects: list[str],
        latest_message: str,
    ) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profile (
                    user_id, adiga_payload, extracted_scores, completed_scores,
                    estimated_subjects, latest_message, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    adiga_payload=excluded.adiga_payload,
                    extracted_scores=excluded.extracted_scores,
                    completed_scores=excluded.completed_scores,
                    estimated_subjects=excluded.estimated_subjects,
                    latest_message=excluded.latest_message,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    json.dumps(adiga_payload, ensure_ascii=False),
                    json.dumps(extracted_scores, ensure_ascii=False),
                    json.dumps(completed_scores, ensure_ascii=False),
                    json.dumps(estimated_subjects, ensure_ascii=False),
                    latest_message,
                    timestamp,
                ),
            )
            conn.commit()

        return {"user_id": user_id, "updated_at": timestamp}

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, adiga_payload, extracted_scores, completed_scores,
                       estimated_subjects, latest_message, updated_at
                FROM user_profile
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "user_id": row["user_id"],
            "adiga_payload": json.loads(row["adiga_payload"]),
            "extracted_scores": json.loads(row["extracted_scores"]),
            "completed_scores": json.loads(row["completed_scores"]),
            "estimated_subjects": json.loads(row["estimated_subjects"]),
            "latest_message": row["latest_message"],
            "updated_at": row["updated_at"],
        }

