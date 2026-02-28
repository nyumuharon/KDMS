"""
database.py — SQLite setup and async query helpers for KDMS
"""
import aiosqlite  # type: ignore[import]
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "kdms.db")


async def get_db():
    return await aiosqlite.connect(DB_PATH)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS counties (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                region      TEXT,
                lat         REAL,
                lng         REAL,
                risk_score  INTEGER DEFAULT 0,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS disasters (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                type            TEXT NOT NULL,
                severity        TEXT DEFAULT 'Medium',
                county_id       INTEGER REFERENCES counties(id),
                location        TEXT,
                lat             REAL,
                lng             REAL,
                affected_people INTEGER DEFAULT 0,
                description     TEXT,
                source          TEXT DEFAULT 'manual',
                status          TEXT DEFAULT 'active',
                reported_at     TEXT DEFAULT (datetime('now')),
                resolved_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS refuge_sites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                county_id   INTEGER REFERENCES counties(id),
                lat         REAL,
                lng         REAL,
                capacity    INTEGER DEFAULT 500,
                type        TEXT DEFAULT 'Camp'
            );

            CREATE TABLE IF NOT EXISTS workers (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                role                TEXT,
                phone               TEXT,
                county_id           INTEGER REFERENCES counties(id),
                status              TEXT DEFAULT 'available',
                current_disaster_id INTEGER,
                lat                 REAL,
                lng                 REAL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                disaster_id      INTEGER REFERENCES disasters(id),
                message_en       TEXT,
                message_sw       TEXT,
                recipients_count INTEGER DEFAULT 0,
                sent_at          TEXT DEFAULT (datetime('now')),
                status           TEXT DEFAULT 'sent'
            );

            CREATE TABLE IF NOT EXISTS ai_cache (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key    TEXT UNIQUE,
                analysis_json TEXT,
                generated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()
    print("[DB] ✅ Database initialised")


# ── Generic helpers ──────────────────────────────────────────────────────────

async def fetchall(query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            result = [dict(r) for r in rows]
    return result


async def fetchone(query: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
    row_result: Optional[Dict[str, Any]] = None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            row_result = dict(row) if row else None
    return row_result


async def execute(query: str, params: Tuple[Any, ...] = ()) -> Optional[int]:
    last_id: Optional[int] = None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        last_id = cur.lastrowid
    return last_id


# ── County helpers ───────────────────────────────────────────────────────────

async def get_all_counties():
    return await fetchall("SELECT * FROM counties ORDER BY name")


async def update_county_risk(county_id: int, risk_score: int):
    await execute(
        "UPDATE counties SET risk_score=?, last_updated=? WHERE id=?",
        (risk_score, datetime.utcnow().isoformat(), county_id)
    )


# ── Disaster helpers ─────────────────────────────────────────────────────────

async def get_all_disasters(status: Optional[str] = None) -> List[Dict[str, Any]]:
    if status:
        result: List[Dict[str, Any]] = await fetchall(
            "SELECT d.*, c.name as county_name FROM disasters d "
            "LEFT JOIN counties c ON d.county_id=c.id WHERE d.status=? ORDER BY reported_at DESC",
            (status,)
        )
    else:
        result = await fetchall(
            "SELECT d.*, c.name as county_name FROM disasters d "
            "LEFT JOIN counties c ON d.county_id=c.id ORDER BY reported_at DESC"
        )
    return result


async def insert_disaster(data: Dict[str, Any]) -> Optional[int]:
    return await execute(
        """INSERT INTO disasters (type, severity, county_id, location, lat, lng,
           affected_people, description, source, status)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            data.get("type"), data.get("severity", "Medium"),
            data.get("county_id"), data.get("location"), data.get("lat"),
            data.get("lng"), data.get("affected_people", 0),
            data.get("description"), data.get("source", "manual"),
            data.get("status", "active")
        )
    )


# ── Worker helpers ───────────────────────────────────────────────────────────

async def get_all_workers():
    return await fetchall(
        "SELECT w.*, c.name as county_name FROM workers w "
        "LEFT JOIN counties c ON w.county_id=c.id ORDER BY w.name"
    )


async def dispatch_worker(worker_id: int, disaster_id: int):
    await execute(
        "UPDATE workers SET status='deployed', current_disaster_id=? WHERE id=?",
        (disaster_id, worker_id)
    )


# ── Alert helpers ────────────────────────────────────────────────────────────

async def insert_alert(disaster_id: int, msg_en: str, msg_sw: str, count: int):
    return await execute(
        "INSERT INTO alerts (disaster_id, message_en, message_sw, recipients_count) VALUES (?,?,?,?)",
        (disaster_id, msg_en, msg_sw, count)
    )


async def get_alerts():
    return await fetchall("SELECT * FROM alerts ORDER BY sent_at DESC")


# ── Refuge helpers ───────────────────────────────────────────────────────────

async def get_refuges_for_county(county_id: int):
    return await fetchall(
        "SELECT * FROM refuge_sites WHERE county_id=?", (county_id,)
    )


# ── AI Cache ────────────────────────────────────────────────────────────────

async def get_cached(key: str):
    row = await fetchone("SELECT analysis_json FROM ai_cache WHERE cache_key=?", (key,))
    if row:
        return json.loads(row["analysis_json"])
    return None


async def set_cached(key: str, data: Any) -> None:
    await execute(
        """INSERT INTO ai_cache (cache_key, analysis_json) VALUES (?,?)
           ON CONFLICT(cache_key) DO UPDATE SET analysis_json=excluded.analysis_json,
           generated_at=datetime('now')""",
        (key, json.dumps(data))
    )
