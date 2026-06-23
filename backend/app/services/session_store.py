import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.speech import (
    LlmModuleResponse,
    SessionResponse,
    SessionTurn,
    SpeechAnalysisResponse,
)


SESSION_DB_PATH = os.getenv("SESSION_DB_PATH", ":memory:")
_LOCK = threading.Lock()
_CONNECTION: sqlite3.Connection | None = None


def new_turn_id() -> str:
    return f"turn_{uuid4().hex[:12]}"


def create_session(*, scenario_id: str, child_id: str) -> SessionResponse:
    now = datetime.now(timezone.utc)
    session = SessionResponse(
        session_id=f"session_{uuid4().hex[:12]}",
        child_id=child_id,
        scenario_id=scenario_id,
        started_at=now,
        status="active",
    )
    with _LOCK:
        connection = get_connection()
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, child_id, scenario_id, status,
                created_at, updated_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                session.session_id,
                child_id,
                scenario_id,
                session.status,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        connection.commit()
    return session


def read_session(session_id: str) -> SessionResponse | None:
    with _LOCK:
        row = get_connection().execute(
            """
            SELECT session_id, child_id, scenario_id, status,
                   created_at, ended_at
            FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return session_row_to_model(row)


def end_session(session_id: str, status: str) -> SessionResponse | None:
    now = datetime.now(timezone.utc)
    with _LOCK:
        connection = get_connection()
        cursor = connection.execute(
            """
            UPDATE sessions
            SET status = ?, ended_at = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (status, now.isoformat(), now.isoformat(), session_id),
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None
        row = connection.execute(
            """
            SELECT session_id, child_id, scenario_id, status,
                   created_at, ended_at
            FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    return session_row_to_model(row)


def append_turn(
    *,
    session_id: str,
    turn_id: str,
    transcript: str,
    analysis: SpeechAnalysisResponse,
    llm: LlmModuleResponse,
    stt_model: str | None = None,
    stt_time_seconds: float | None = None,
) -> SessionTurn:
    created_at = datetime.now(timezone.utc)
    turn = SessionTurn(
        session_id=session_id,
        turn_id=turn_id,
        transcript=transcript,
        analysis=analysis,
        llm=llm,
        stt_model=stt_model,
        stt_time_seconds=stt_time_seconds,
        created_at=created_at,
    )

    now = created_at.isoformat()
    with _LOCK:
        connection = get_connection()
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, child_id, scenario_id, status, created_at, updated_at
            )
            VALUES (?, 'anonymous', 'unknown', 'active', ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (session_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO turn_logs (
                session_id,
                turn_id,
                transcript,
                analysis_json,
                llm_json,
                stt_model,
                stt_time_seconds,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, turn_id) DO UPDATE SET
                transcript = excluded.transcript,
                analysis_json = excluded.analysis_json,
                llm_json = excluded.llm_json,
                stt_model = excluded.stt_model,
                stt_time_seconds = excluded.stt_time_seconds,
                created_at = excluded.created_at
            """,
            (
                session_id,
                turn_id,
                transcript,
                json.dumps(model_to_jsonable(analysis), ensure_ascii=False),
                json.dumps(model_to_jsonable(llm), ensure_ascii=False),
                stt_model,
                stt_time_seconds,
                now,
            ),
        )
        connection.commit()

    return turn


def read_turns(session_id: str) -> list[SessionTurn]:
    with _LOCK:
        connection = get_connection()
        rows = connection.execute(
            """
            SELECT
                session_id,
                turn_id,
                transcript,
                analysis_json,
                llm_json,
                stt_model,
                stt_time_seconds,
                created_at
            FROM turn_logs
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    return [row_to_turn(row) for row in rows]


def get_connection() -> sqlite3.Connection:
    global _CONNECTION

    if _CONNECTION is None:
        _CONNECTION = sqlite3.connect(SESSION_DB_PATH, check_same_thread=False)
        _CONNECTION.row_factory = sqlite3.Row
        initialize_schema(_CONNECTION)
    return _CONNECTION


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            child_id TEXT NOT NULL DEFAULT 'anonymous',
            scenario_id TEXT NOT NULL DEFAULT 'unknown',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ended_at TEXT
        )
        """
    )
    migrate_sessions_schema(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS turn_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            transcript TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            llm_json TEXT NOT NULL,
            stt_model TEXT,
            stt_time_seconds REAL,
            created_at TEXT NOT NULL,
            UNIQUE(session_id, turn_id),
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        )
        """
    )
    connection.commit()


def migrate_sessions_schema(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
    }
    additions = {
        "child_id": "TEXT NOT NULL DEFAULT 'anonymous'",
        "scenario_id": "TEXT NOT NULL DEFAULT 'unknown'",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "ended_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE sessions ADD COLUMN {name} {definition}")


def row_to_turn(row: sqlite3.Row) -> SessionTurn:
    return SessionTurn(
        session_id=row["session_id"],
        turn_id=row["turn_id"],
        transcript=row["transcript"],
        analysis=SpeechAnalysisResponse(**json.loads(row["analysis_json"])),
        llm=LlmModuleResponse(**json.loads(row["llm_json"])),
        stt_model=row["stt_model"],
        stt_time_seconds=row["stt_time_seconds"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def session_row_to_model(row: sqlite3.Row) -> SessionResponse:
    return SessionResponse(
        session_id=row["session_id"],
        child_id=row["child_id"],
        scenario_id=row["scenario_id"],
        status=row["status"],
        started_at=datetime.fromisoformat(row["created_at"]),
        ended_at=(
            datetime.fromisoformat(row["ended_at"])
            if row["ended_at"]
            else None
        ),
    )


def model_to_jsonable(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()
