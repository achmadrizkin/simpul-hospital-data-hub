"""Sync one source: fetch -> staging -> normalise -> MPI -> code mapping."""

import hashlib
import json
import sqlite3

from . import alerts, connectors
from .db import now_iso, session, write_lock
from .mpi import match_new_record
from .normalize import clean_name, clean_nik, clean_phone, clean_sex, parse_date
from .terminology import ensure_mapping


def register_sources() -> None:
    with session() as conn:
        alerts.register_rules(conn)
        for src in connectors.SOURCES:
            conn.execute(
                """
                INSERT INTO sources (code, name, description, method, method_label, interval_min, has_nik)
                VALUES (:code, :name, :description, :method, :method_label, :interval_min, :has_nik)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name, description = excluded.description, method = excluded.method,
                    method_label = excluded.method_label, interval_min = excluded.interval_min,
                    has_nik = excluded.has_nik
                """,
                src,
            )


def sync_source(code: str) -> dict:
    with write_lock, session() as conn:
        source = conn.execute("SELECT * FROM sources WHERE code = ?", (code,)).fetchone()
        started = now_iso()
        run_id = conn.execute(
            "INSERT INTO sync_runs (source_code, started_at, status) VALUES (?, ?, 'berjalan')",
            (code, started),
        ).lastrowid
        try:
            records, watermark, on_success = connectors.fetch(code, source["watermark"])
            changed = _stage(conn, code, records)
            _process(conn, code)
            raised = alerts.evaluate(conn)["raised"] if changed else []
            on_success()
            status, message = "sukses", f"{len(records)} data dibaca, {changed} data baru/berubah"
            if raised:
                message += f", {len(raised)} peringatan klinis baru"
        except Exception as exc:  # report every failure on the dashboard instead of crashing
            records, watermark, changed = [], source["watermark"], 0
            status, message = "gagal", str(exc)

        finished = now_iso()
        conn.execute(
            """
            UPDATE sync_runs SET finished_at = ?, records_in = ?, records_new = ?, status = ?, message = ?
            WHERE id = ?
            """,
            (finished, len(records), changed, status, message, run_id),
        )
        conn.execute(
            """
            UPDATE sources SET watermark = ?, last_sync_at = ?, last_status = ?, last_message = ?
            WHERE code = ?
            """,
            (watermark, finished, status, message, code),
        )
        return {"source": code, "status": status, "message": message, "records_new": changed}


def _stage(conn: sqlite3.Connection, code: str, records: list[dict]) -> int:
    changed = 0
    received = now_iso()
    for rec in records:
        payload = json.dumps(rec["data"], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha1(payload.encode()).hexdigest()
        cur = conn.execute(
            """
            INSERT INTO staging_records (source_code, record_type, source_key, payload, hash, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_code, record_type, source_key) DO UPDATE SET
                payload = excluded.payload, hash = excluded.hash,
                received_at = excluded.received_at, processed = 0
            WHERE staging_records.hash != excluded.hash
            """,
            (code, rec["type"], rec["key"], payload, digest, received),
        )
        changed += cur.rowcount
    return changed


def _process(conn: sqlite3.Connection, code: str) -> None:
    rows = conn.execute(
        """
        SELECT * FROM staging_records WHERE source_code = ? AND processed = 0
        ORDER BY CASE record_type WHEN 'patient' THEN 0 ELSE 1 END, id
        """,
        (code,),
    ).fetchall()
    for row in rows:
        data = json.loads(row["payload"])
        if row["record_type"] == "patient":
            _upsert_patient(conn, code, data)
        else:
            _upsert_event(conn, code, row["source_key"], data)
        conn.execute("UPDATE staging_records SET processed = 1 WHERE id = ?", (row["id"],))


def _upsert_patient(conn: sqlite3.Connection, code: str, data: dict) -> None:
    values = {
        "source_code": code,
        "local_id": data["local_id"],
        "raw_name": data.get("name"),
        "name": clean_name(data.get("name")),
        "raw_nik": data.get("nik"),
        "nik": clean_nik(data.get("nik")),
        "raw_birth_date": data.get("birth_date"),
        "birth_date": parse_date(data.get("birth_date")),
        "sex": clean_sex(data.get("sex")),
        "phone": clean_phone(data.get("phone")),
        "address": data.get("address"),
        "updated_at": now_iso(),
    }
    existing = conn.execute(
        "SELECT id FROM source_patients WHERE source_code = ? AND local_id = ?",
        (code, data["local_id"]),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE source_patients SET raw_name = :raw_name, name = :name, raw_nik = :raw_nik, nik = :nik,
                raw_birth_date = :raw_birth_date, birth_date = :birth_date, sex = :sex, phone = :phone,
                address = :address, updated_at = :updated_at
            WHERE source_code = :source_code AND local_id = :local_id
            """,
            values,
        )
        return
    cur = conn.execute(
        """
        INSERT INTO source_patients (source_code, local_id, raw_name, name, raw_nik, nik, raw_birth_date,
            birth_date, sex, phone, address, updated_at)
        VALUES (:source_code, :local_id, :raw_name, :name, :raw_nik, :nik, :raw_birth_date,
            :birth_date, :sex, :phone, :address, :updated_at)
        """,
        values,
    )
    match_new_record(conn, cur.lastrowid)


EVENT_FIELDS = (
    "local_patient_id", "kind", "occurred_at", "title", "detail", "code_system", "local_code",
    "local_text", "value", "unit", "ref_range", "flag", "amount", "visit_key",
)


def _upsert_event(conn: sqlite3.Connection, code: str, key: str, data: dict) -> None:
    if data.get("code_system") and data.get("local_code"):
        ensure_mapping(conn, data["code_system"], data["local_code"], data.get("local_text"))
    values = {field: data.get(field) for field in EVENT_FIELDS}
    values.update(source_code=code, source_key=key)
    columns = ", ".join(values)
    marks = ", ".join(f":{c}" for c in values)
    updates = ", ".join(f"{c} = excluded.{c}" for c in EVENT_FIELDS)
    conn.execute(
        f"""
        INSERT INTO events ({columns}) VALUES ({marks})
        ON CONFLICT(source_code, source_key) DO UPDATE SET {updates}
        """,
        values,
    )
