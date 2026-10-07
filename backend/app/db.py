"""SQLite storage for the demo. Swap the connection for PostgreSQL in production."""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "simpul.db"

# One writer at a time: syncs, merges and mapping changes all take this lock.
write_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    method TEXT NOT NULL,
    method_label TEXT NOT NULL,
    interval_min REAL NOT NULL,
    has_nik INTEGER NOT NULL DEFAULT 0,
    watermark TEXT,
    last_sync_at TEXT,
    last_status TEXT,
    last_message TEXT
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    records_in INTEGER DEFAULT 0,
    records_new INTEGER DEFAULT 0,
    status TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS staging_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL,
    record_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    hash TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_code, record_type, source_key)
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    merged_into INTEGER
);

CREATE TABLE IF NOT EXISTS source_patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL,
    local_id TEXT NOT NULL,
    raw_name TEXT,
    name TEXT,
    raw_nik TEXT,
    nik TEXT,
    raw_birth_date TEXT,
    birth_date TEXT,
    sex TEXT,
    phone TEXT,
    address TEXT,
    golden_id INTEGER REFERENCES patients(id),
    match_score REAL,
    linked_by TEXT,
    updated_at TEXT,
    UNIQUE (source_code, local_id)
);

CREATE TABLE IF NOT EXISTS mpi_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sp_a INTEGER NOT NULL REFERENCES source_patients(id),
    sp_b INTEGER NOT NULL REFERENCES source_patients(id),
    score REAL NOT NULL,
    reasons TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    undo_info TEXT,
    UNIQUE (sp_a, sp_b)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL,
    source_key TEXT NOT NULL,
    local_patient_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    title TEXT,
    detail TEXT,
    code_system TEXT,
    local_code TEXT,
    local_text TEXT,
    value TEXT,
    unit TEXT,
    ref_range TEXT,
    flag TEXT,
    amount REAL,
    visit_key TEXT,
    UNIQUE (source_code, source_key)
);

CREATE TABLE IF NOT EXISTS code_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system TEXT NOT NULL,
    local_code TEXT NOT NULL,
    local_text TEXT,
    std_code TEXT,
    std_text TEXT,
    status TEXT NOT NULL,
    suggested_by TEXT,
    confirmed_by TEXT,
    confirmed_at TEXT,
    UNIQUE (system, local_code)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    sources TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clinical_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    golden_id INTEGER NOT NULL REFERENCES patients(id),
    rule_code TEXT NOT NULL REFERENCES alert_rules(code),
    detail TEXT NOT NULL,
    evidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    handled_by TEXT,
    handled_at TEXT,
    note TEXT,
    UNIQUE (golden_id, rule_code)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON clinical_alerts(status);
CREATE INDEX IF NOT EXISTS idx_sp_golden ON source_patients(golden_id);
CREATE INDEX IF NOT EXISTS idx_events_patient ON events(source_code, local_patient_id);
CREATE INDEX IF NOT EXISTS idx_events_code ON events(code_system, local_code);
"""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)


def reset_db() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        if path.exists():
            path.unlink()
    init_db()
