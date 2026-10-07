"""HTTP API for the dashboard."""

import csv
import io
import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from . import alerts, connectors, live, mpi, seed
from .db import now_iso, session, write_lock
from .normalize import birth_date_problem, clean_name, display_name, mask_nik, mask_phone
from .pipeline import sync_source
from .quality import RULES, collect_issues, report
from .reference import SYSTEM_LABELS, catalog, std_text

router = APIRouter(prefix="/api")

HOSPITAL = {"name": "RS Sehat Sentosa", "city": "Jakarta Timur", "note": "Rumah sakit fiktif untuk demo"}
SOURCE_PRIORITY = ["simrs", "lis", "billing", "farmasi"]
OPERATOR = "Petugas Rekam Medis"


# ---------- helpers ----------

def _source_names(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM sources")}


def _age(birth_date: str | None) -> int | None:
    if not birth_date or birth_date_problem(birth_date):
        return None
    dob = date.fromisoformat(birth_date)
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _source_status(src: sqlite3.Row) -> str:
    if src["code"] in connectors.OUTAGES or src["last_status"] == "gagal":
        return "gagal"
    if not src["last_sync_at"]:
        return "belum"
    elapsed = (datetime.now() - datetime.fromisoformat(src["last_sync_at"])).total_seconds()
    if elapsed > max(src["interval_min"] * 60 * 3, 180):
        return "terlambat"
    return "lancar"


def _golden_label(gid: int) -> str:
    return f"SPL-{gid:06d}"


def _identity(records: list[sqlite3.Row]) -> dict:
    """Best value for each field across all linked records."""
    ordered = sorted(records, key=lambda r: SOURCE_PRIORITY.index(r["source_code"]))

    def first(field, valid=lambda v: bool(v)):
        for r in ordered:
            if valid(r[field]):
                return r[field]
        return None

    birth_dates = [r["birth_date"] for r in ordered if r["birth_date"] and not birth_date_problem(r["birth_date"])]
    birth_date = max(set(birth_dates), key=birth_dates.count) if birth_dates else None
    name = first("name") or ""
    nik = first("nik", lambda v: bool(v) and len(v) == 16)
    return {
        "name": display_name(name),
        "sex": first("sex"),
        "birth_date": birth_date,
        "age": _age(birth_date),
        "nik": mask_nik(nik),
        "has_nik": bool(nik),
        "phone": mask_phone(first("phone")),
        "address": first("address"),
    }


def _mapping_index(conn: sqlite3.Connection) -> dict:
    return {(r["system"], r["local_code"]): r for r in conn.execute("SELECT * FROM code_mappings")}


def _sp_summary(conn: sqlite3.Connection, sp: sqlite3.Row, names: dict) -> dict:
    events = conn.execute(
        "SELECT kind, COUNT(*) n FROM events WHERE source_code = ? AND local_patient_id = ? GROUP BY kind",
        (sp["source_code"], sp["local_id"]),
    ).fetchall()
    return {
        "id": sp["id"],
        "source": sp["source_code"],
        "source_name": names.get(sp["source_code"], sp["source_code"]),
        "local_id": sp["local_id"],
        "name": sp["raw_name"],
        "birth_date_raw": sp["raw_birth_date"],
        "birth_date": sp["birth_date"],
        "sex": sp["sex"],
        "nik": mask_nik(sp["nik"]),
        "phone": mask_phone(sp["phone"]),
        "address": sp["address"],
        "golden_id": sp["golden_id"],
        "golden_label": _golden_label(sp["golden_id"]) if sp["golden_id"] else None,
        "linked_by": sp["linked_by"],
        "events": {r["kind"]: r["n"] for r in events},
    }


# ---------- overview ----------

@router.get("/overview")
def overview():
    with session() as conn:
        names = _source_names(conn)
        today = date.today().isoformat()
        sources = []
        for src in conn.execute("SELECT * FROM sources ORDER BY rowid"):
            today_count = conn.execute(
                "SELECT COUNT(*) FROM staging_records WHERE source_code = ? AND received_at >= ?",
                (src["code"], today),
            ).fetchone()[0]
            sources.append({
                "code": src["code"],
                "name": src["name"],
                "description": src["description"],
                "status": _source_status(src),
                "last_sync_at": src["last_sync_at"],
                "last_message": src["last_message"],
                "records_today": today_count,
            })
        q = report(conn)
        pending = conn.execute("SELECT COUNT(*) FROM mpi_candidates WHERE status = 'pending'").fetchone()[0]
        unmapped = conn.execute("SELECT COUNT(*) FROM code_mappings WHERE status != 'confirmed'").fetchone()[0]
        local_records = conn.execute("SELECT COUNT(*) FROM source_patients").fetchone()[0]
        open_alerts = conn.execute("SELECT COUNT(*) FROM clinical_alerts WHERE status = 'open'").fetchone()[0]
        patients = conn.execute("SELECT COUNT(*) FROM patients WHERE merged_into IS NULL").fetchone()[0]
        auto_linked = conn.execute(
            "SELECT COUNT(*) FROM source_patients WHERE linked_by = 'otomatis'"
        ).fetchone()[0]
        activity = [
            {**dict(r), "source_name": names.get(r["source_code"])}
            for r in conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 8")
        ]
        return {
            "hospital": HOSPITAL,
            "now": now_iso(),
            "sources": sources,
            "totals": {
                "patients": patients,
                "local_records": local_records,
                "auto_linked": auto_linked,
                "pending_duplicates": pending,
                "unmapped_codes": unmapped,
                "open_alerts": open_alerts,
                "quality_score": q["score"],
                "issues": q["issues"],
            },
            "top_problems": [r for r in q["rules"] if r["count"]][:4],
            "activity": activity,
            "live": live.LIVE,
        }


# ---------- sources ----------

@router.get("/sources")
def list_sources():
    with session() as conn:
        result = []
        for src in conn.execute("SELECT * FROM sources ORDER BY rowid"):
            patients = conn.execute(
                "SELECT COUNT(*) FROM source_patients WHERE source_code = ?", (src["code"],)
            ).fetchone()[0]
            events = conn.execute(
                "SELECT COUNT(*) FROM events WHERE source_code = ?", (src["code"],)
            ).fetchone()[0]
            runs = conn.execute(
                "SELECT * FROM sync_runs WHERE source_code = ? ORDER BY id DESC LIMIT 6", (src["code"],)
            ).fetchall()
            result.append({
                **{k: src[k] for k in src.keys() if k != "watermark"},
                "status": _source_status(src),
                "outage": src["code"] in connectors.OUTAGES,
                "patients": patients,
                "events": events,
                "runs": [dict(r) for r in runs],
            })
        return {"sources": result, "live": live.LIVE}


@router.post("/sources/{code}/sync")
def sync_now(code: str):
    if code not in connectors.FETCHERS:
        raise HTTPException(404, "Sumber data tidak dikenal")
    return sync_source(code)


class OutageBody(BaseModel):
    on: bool


@router.post("/sources/{code}/outage")
def set_outage(code: str, body: OutageBody):
    if code not in connectors.FETCHERS:
        raise HTTPException(404, "Sumber data tidak dikenal")
    if body.on:
        connectors.OUTAGES.add(code)
    else:
        connectors.OUTAGES.discard(code)
    return sync_source(code)


@router.post("/sources/farmasi/upload")
async def upload_farmasi(file: UploadFile = File(...)):
    content = await file.read()
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "File harus berformat CSV (.csv).")
    header = content.decode("utf-8-sig", errors="ignore").splitlines()[:1]
    required = {"tgl_resep", "no_resep", "no_rm_farmasi", "nama_pasien", "tgl_lahir", "jk", "nama_obat"}
    missing = required - set(header[0].split(",")) if header else required
    if missing:
        raise HTTPException(400, f"Kolom berikut tidak ada di file: {', '.join(sorted(missing))}.")
    live.save_farmasi_upload(file.filename, content)
    return sync_source("farmasi")


# ---------- demo controls ----------

@router.get("/demo/sample-farmasi.csv")
def sample_farmasi():
    name = f"contoh_farmasi_{date.today().isoformat()}.csv"
    return Response(
        live.sample_farmasi_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/demo/lab-message")
def demo_lab_message():
    sent = live.send_lab_message()
    result = sync_source("lis")
    return {**sent, **result}


class LiveBody(BaseModel):
    enabled: bool


@router.post("/demo/live")
def demo_live(body: LiveBody):
    live.LIVE["enabled"] = body.enabled
    return live.LIVE


@router.post("/demo/reset")
def demo_reset():
    return seed.run()


# ---------- patients ----------

@router.get("/patients")
def search_patients(q: str = ""):
    q = q.strip()
    with session() as conn:
        if q:
            like = f"%{clean_name(q)}%" if clean_name(q) else "%__none__%"
            raw = f"%{q}%"
            gid_from_label = None
            if q.upper().startswith("SPL-") and q[4:].isdigit():
                gid_from_label = int(q[4:])
            rows = conn.execute(
                """
                SELECT DISTINCT golden_id FROM source_patients
                WHERE name LIKE ? OR nik LIKE ? OR local_id LIKE ? OR golden_id = ?
                LIMIT 50
                """,
                (like, raw, raw, gid_from_label or -1),
            ).fetchall()
            gids = [r["golden_id"] for r in rows]
        else:
            rows = conn.execute(
                """
                SELECT sp.golden_id, MAX(e.occurred_at) last FROM events e
                JOIN source_patients sp ON sp.source_code = e.source_code AND sp.local_id = e.local_patient_id
                GROUP BY sp.golden_id ORDER BY last DESC LIMIT 25
                """
            ).fetchall()
            gids = [r["golden_id"] for r in rows]

        names = _source_names(conn)
        pending_by_golden = defaultdict(int)
        for r in conn.execute(
            """
            SELECT a.golden_id ga, b.golden_id gb FROM mpi_candidates c
            JOIN source_patients a ON a.id = c.sp_a JOIN source_patients b ON b.id = c.sp_b
            WHERE c.status = 'pending'
            """
        ):
            pending_by_golden[r["ga"]] += 1
            pending_by_golden[r["gb"]] += 1

        results = []
        for gid in gids:
            records = conn.execute("SELECT * FROM source_patients WHERE golden_id = ?", (gid,)).fetchall()
            if not records:
                continue
            last = conn.execute(
                """
                SELECT MAX(e.occurred_at) FROM events e JOIN source_patients sp
                ON sp.source_code = e.source_code AND sp.local_id = e.local_patient_id
                WHERE sp.golden_id = ?
                """,
                (gid,),
            ).fetchone()[0]
            results.append({
                "id": gid,
                "label": _golden_label(gid),
                **_identity(records),
                "sources": sorted({names[r["source_code"]] for r in records},
                                  key=lambda n: list(names.values()).index(n)),
                "last_activity": last,
                "pending_duplicates": pending_by_golden.get(gid, 0),
            })
        return {"query": q, "results": results}


KIND_LABELS = {
    "visit": "Kunjungan",
    "diagnosis": "Diagnosis",
    "lab": "Hasil lab",
    "medication": "Obat",
    "charge": "Tagihan",
}


@router.get("/patients/{gid}")
def patient_detail(gid: int):
    with session() as conn:
        target = conn.execute("SELECT * FROM patients WHERE id = ?", (gid,)).fetchone()
        if not target:
            raise HTTPException(404, "Pasien tidak ditemukan")
        if target["merged_into"]:
            return {"redirect_to": target["merged_into"]}

        names = _source_names(conn)
        records = conn.execute("SELECT * FROM source_patients WHERE golden_id = ?", (gid,)).fetchall()
        mappings = _mapping_index(conn)
        keys = [(r["source_code"], r["local_id"]) for r in records]
        events = []
        for source_code, local_id in keys:
            events += conn.execute(
                "SELECT * FROM events WHERE source_code = ? AND local_patient_id = ?",
                (source_code, local_id),
            ).fetchall()
        events.sort(key=lambda e: e["occurred_at"] or "", reverse=True)

        timeline = []
        for e in events:
            mapping = mappings.get((e["code_system"], e["local_code"])) if e["code_system"] else None
            confirmed = mapping is not None and mapping["status"] == "confirmed"
            timeline.append({
                "id": e["id"],
                "kind": e["kind"],
                "kind_label": KIND_LABELS.get(e["kind"], e["kind"]),
                "occurred_at": e["occurred_at"],
                "title": e["title"],
                "detail": e["detail"],
                "source": e["source_code"],
                "source_name": names.get(e["source_code"]),
                "local_code": e["local_code"],
                "std_code": mapping["std_code"] if confirmed else None,
                "std_text": mapping["std_text"] if confirmed else None,
                "std_system": SYSTEM_LABELS[e["code_system"]][1] if e["code_system"] else None,
                "value": e["value"],
                "unit": e["unit"],
                "ref_range": e["ref_range"],
                "flag": e["flag"],
                "amount": e["amount"],
            })

        diagnoses = {}
        for item in timeline:
            if item["kind"] == "diagnosis":
                key = item["std_code"] or item["local_code"]
                if key not in diagnoses:
                    diagnoses[key] = {
                        "code": item["std_code"],
                        "local_code": item["local_code"],
                        "text": item["std_text"] or item["title"],
                        "last_seen": item["occurred_at"],
                    }
        latest_labs = {}
        for item in timeline:
            if item["kind"] == "lab" and item["local_code"] not in latest_labs:
                latest_labs[item["local_code"]] = item
        recent_cut = (date.today() - timedelta(days=90)).isoformat()
        medications = {}
        for item in timeline:
            if item["kind"] == "medication" and item["occurred_at"] >= recent_cut:
                medications.setdefault(item["title"], item)
        total_charges = sum(item["amount"] or 0 for item in timeline if item["kind"] == "charge")

        sp_ids = [r["id"] for r in records]
        marks = ",".join("?" * len(sp_ids))
        pending = conn.execute(
            f"""
            SELECT * FROM mpi_candidates WHERE status = 'pending' AND (sp_a IN ({marks}) OR sp_b IN ({marks}))
            """,
            (*sp_ids, *sp_ids),
        ).fetchall()
        issues = [i for i in collect_issues(conn) if i["golden_id"] == gid]
        for issue in issues:
            issue["label"] = RULES[issue["rule"]]["label"]
            issue["severity"] = RULES[issue["rule"]]["severity"]
            issue["source_name"] = names.get(issue["source"])

        visits = [t for t in timeline if t["kind"] == "visit"]
        patient_alerts = [
            _alert_dict(a, names, {})
            for a in conn.execute(
                """
                SELECT ca.*, ar.title, ar.severity, ar.sources FROM clinical_alerts ca
                JOIN alert_rules ar ON ar.code = ca.rule_code
                WHERE ca.golden_id = ? AND ca.status != 'resolved'
                ORDER BY ca.status, CASE ar.severity WHEN 'tinggi' THEN 0 ELSE 1 END, ca.created_at DESC
                """,
                (gid,),
            )
        ]
        return {
            "alerts": patient_alerts,
            "id": gid,
            "label": _golden_label(gid),
            "identity": _identity(records),
            "records": [_sp_summary(conn, r, names) for r in sorted(
                records, key=lambda r: SOURCE_PRIORITY.index(r["source_code"]))],
            "name_variants": sorted({r["raw_name"] for r in records if r["raw_name"]}),
            "summary": {
                "visits": len(visits),
                "last_visit": visits[0]["occurred_at"] if visits else None,
                "diagnoses": list(diagnoses.values()),
                "latest_labs": list(latest_labs.values()),
                "medications": list(medications.values()),
                "total_charges": total_charges,
            },
            "pending_duplicates": [c["id"] for c in pending],
            "issues": issues,
            "timeline": timeline,
        }


# ---------- MPI ----------

@router.get("/mpi/candidates")
def mpi_candidates(status: str = "pending"):
    with session() as conn:
        names = _source_names(conn)
        if status == "pending":
            where, order = "status = 'pending'", "score DESC, id"
        else:
            where, order = "status != 'pending'", "decided_at DESC"
        rows = conn.execute(f"SELECT * FROM mpi_candidates WHERE {where} ORDER BY {order}").fetchall()
        counts = {
            "pending": conn.execute("SELECT COUNT(*) FROM mpi_candidates WHERE status = 'pending'").fetchone()[0],
            "decided": conn.execute("SELECT COUNT(*) FROM mpi_candidates WHERE status != 'pending'").fetchone()[0],
        }
        items = []
        for c in rows:
            a = conn.execute("SELECT * FROM source_patients WHERE id = ?", (c["sp_a"],)).fetchone()
            b = conn.execute("SELECT * FROM source_patients WHERE id = ?", (c["sp_b"],)).fetchone()
            items.append({
                "id": c["id"],
                "score": c["score"],
                "status": c["status"],
                "decided_by": c["decided_by"],
                "decided_at": c["decided_at"],
                "reasons": json.loads(c["reasons"]),
                "a": _sp_summary(conn, a, names),
                "b": _sp_summary(conn, b, names),
            })
        return {"counts": counts, "items": items}


@router.post("/mpi/candidates/{cid}/merge")
def mpi_merge(cid: int):
    with write_lock, session() as conn:
        _require_candidate(conn, cid, "pending")
        result = mpi.merge(conn, cid, OPERATOR)
        changes = alerts.evaluate(conn)
        result["new_alerts"] = [a for a in changes["raised"] if a["golden_id"] == result["golden_id"]]
        return result


@router.post("/mpi/candidates/{cid}/reject")
def mpi_reject(cid: int):
    with write_lock, session() as conn:
        _require_candidate(conn, cid, "pending")
        mpi.reject(conn, cid, OPERATOR)
        return {"ok": True}


@router.post("/mpi/candidates/{cid}/undo")
def mpi_undo(cid: int):
    with write_lock, session() as conn:
        _require_candidate(conn, cid, None)
        mpi.undo(conn, cid)
        alerts.evaluate(conn)
        return {"ok": True}


def _require_candidate(conn: sqlite3.Connection, cid: int, status: str | None) -> None:
    row = conn.execute("SELECT status FROM mpi_candidates WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise HTTPException(404, "Data tidak ditemukan")
    if status and row["status"] != status:
        raise HTTPException(409, "Pasangan ini sudah diputuskan oleh petugas lain. Muat ulang halaman.")


# ---------- code mappings ----------

@router.get("/mappings")
def list_mappings(status: str = "todo"):
    with session() as conn:
        where = "m.status != 'confirmed'" if status == "todo" else "m.status = 'confirmed'"
        rows = conn.execute(
            f"""
            SELECT m.*, COUNT(e.id) AS usage, COUNT(DISTINCT e.source_code || e.local_patient_id) AS patients,
                   GROUP_CONCAT(DISTINCT e.source_code) AS sources
            FROM code_mappings m
            LEFT JOIN events e ON e.code_system = m.system AND e.local_code = m.local_code
            WHERE {where}
            GROUP BY m.id ORDER BY usage DESC
            """
        ).fetchall()
        names = _source_names(conn)
        counts = {
            "todo": conn.execute("SELECT COUNT(*) FROM code_mappings WHERE status != 'confirmed'").fetchone()[0],
            "done": conn.execute("SELECT COUNT(*) FROM code_mappings WHERE status = 'confirmed'").fetchone()[0],
        }
        return {
            "counts": counts,
            "items": [
                {
                    **dict(r),
                    "system_label": SYSTEM_LABELS[r["system"]][0],
                    "standard": SYSTEM_LABELS[r["system"]][1],
                    "source_names": [names.get(s, s) for s in (r["sources"] or "").split(",") if s],
                }
                for r in rows
            ],
        }


@router.get("/mappings/catalog")
def mapping_catalog(system: str, q: str = ""):
    q = q.lower().strip()
    items = [
        {"code": code, "text": text}
        for code, text in catalog(system)
        if not q or q in code.lower() or q in text.lower()
    ]
    return {"items": items[:30]}


class ConfirmBody(BaseModel):
    std_code: str


@router.post("/mappings/{mid}/confirm")
def confirm_mapping(mid: int, body: ConfirmBody):
    with write_lock, session() as conn:
        row = conn.execute("SELECT * FROM code_mappings WHERE id = ?", (mid,)).fetchone()
        if not row:
            raise HTTPException(404, "Kode tidak ditemukan")
        text = std_text(row["system"], body.std_code)
        if not text:
            raise HTTPException(400, "Kode standar tidak ada di katalog.")
        conn.execute(
            """
            UPDATE code_mappings SET std_code = ?, std_text = ?, status = 'confirmed', confirmed_by = ?,
                confirmed_at = ? WHERE id = ?
            """,
            (body.std_code, text, OPERATOR, now_iso(), mid),
        )
        changes = alerts.evaluate(conn)
        return {"ok": True, "new_alerts": len(changes["raised"]), "resolved_alerts": len(changes["resolved"])}


@router.post("/mappings/{mid}/reset")
def reset_mapping(mid: int):
    with write_lock, session() as conn:
        conn.execute(
            "UPDATE code_mappings SET status = 'suggested', confirmed_by = NULL, confirmed_at = NULL WHERE id = ?",
            (mid,),
        )
        alerts.evaluate(conn)
        return {"ok": True}


# ---------- quality ----------

@router.get("/quality")
def quality():
    with session() as conn:
        return report(conn)


def _issues(conn: sqlite3.Connection, rule: str | None, source: str | None) -> list[dict]:
    names = _source_names(conn)
    issues = collect_issues(conn)
    out = []
    for i in issues:
        if rule and i["rule"] != rule:
            continue
        if source and i["source"] != source:
            continue
        out.append({
            **i,
            "label": RULES[i["rule"]]["label"],
            "severity": RULES[i["rule"]]["severity"],
            "fix": RULES[i["rule"]]["fix"],
            "source_name": names.get(i["source"]),
            "golden_label": _golden_label(i["golden_id"]) if i["golden_id"] else None,
        })
    return out


@router.get("/quality/issues")
def quality_issues(rule: str | None = None, source: str | None = None, limit: int = 100):
    with session() as conn:
        items = _issues(conn, rule, source)
        return {"total": len(items), "items": items[:limit]}


@router.get("/quality/issues.csv")
def quality_issues_csv(rule: str | None = None, source: str | None = None):
    with session() as conn:
        items = _issues(conn, rule, source)
    out = io.StringIO()
    out.write("﻿")  # so Excel opens it as UTF-8
    writer = csv.writer(out)
    writer.writerow(["Masalah", "Tingkat", "Sistem", "ID di sistem", "Nama pasien", "Keterangan",
                     "ID Simpul", "Cara memperbaiki"])
    for i in items:
        writer.writerow([i["label"], i["severity"], i["source_name"], i["ref"], i["patient"] or "",
                         i["detail"], i["golden_label"] or "", i["fix"]])
    filename = f"daftar_perbaikan_data_{date.today().isoformat()}.csv"
    return PlainTextResponse(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- clinical alerts ----------

ALERT_STATUS = ("open", "handled", "resolved")


def _alert_dict(row: sqlite3.Row, names: dict, identities: dict) -> dict:
    evidence = json.loads(row["evidence"])
    for item in evidence:
        item["source_name"] = names.get(item["source"], item["source"])
    return {
        "id": row["id"],
        "golden_id": row["golden_id"],
        "golden_label": _golden_label(row["golden_id"]),
        "patient": identities.get(row["golden_id"]),
        "rule": row["rule_code"],
        "title": row["title"],
        "severity": row["severity"],
        "sources": [names.get(s, s) for s in json.loads(row["sources"])],
        "detail": row["detail"],
        "evidence": evidence,
        "status": row["status"],
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
        "handled_by": row["handled_by"],
        "handled_at": row["handled_at"],
        "note": row["note"],
    }


@router.get("/alerts")
def list_alerts(status: str = "open"):
    if status not in ALERT_STATUS:
        raise HTTPException(400, "Status tidak dikenal")
    with session() as conn:
        names = _source_names(conn)
        rows = conn.execute(
            """
            SELECT ca.*, ar.title, ar.severity, ar.sources FROM clinical_alerts ca
            JOIN alert_rules ar ON ar.code = ca.rule_code
            WHERE ca.status = ?
            ORDER BY CASE ar.severity WHEN 'tinggi' THEN 0 ELSE 1 END, ca.created_at DESC
            """,
            (status,),
        ).fetchall()
        identities = {}
        for gid in {r["golden_id"] for r in rows}:
            records = conn.execute("SELECT * FROM source_patients WHERE golden_id = ?", (gid,)).fetchall()
            if records:
                identities[gid] = _identity(records)
        counts = {
            s: conn.execute("SELECT COUNT(*) FROM clinical_alerts WHERE status = ?", (s,)).fetchone()[0]
            for s in ALERT_STATUS
        }
        return {"counts": counts, "items": [_alert_dict(r, names, identities) for r in rows]}


@router.get("/alerts/rules")
def alert_rules():
    with session() as conn:
        names = _source_names(conn)
        rows = conn.execute(
            """
            SELECT ar.*, (SELECT COUNT(*) FROM clinical_alerts ca
                          WHERE ca.rule_code = ar.code AND ca.status = 'open') AS open_count
            FROM alert_rules ar
            """
        ).fetchall()
        return {
            "items": [
                {
                    **{k: r[k] for k in r.keys() if k != "sources"},
                    "enabled": bool(r["enabled"]),
                    "sources": [names.get(s, s) for s in json.loads(r["sources"])],
                }
                for r in rows
            ]
        }


class RuleToggle(BaseModel):
    enabled: bool


@router.post("/alerts/rules/{code}")
def toggle_rule(code: str, body: RuleToggle):
    with write_lock, session() as conn:
        cur = conn.execute("UPDATE alert_rules SET enabled = ? WHERE code = ?", (int(body.enabled), code))
        if cur.rowcount == 0:
            raise HTTPException(404, "Aturan tidak ditemukan")
        changes = alerts.evaluate(conn)
        return {"ok": True, "new_alerts": len(changes["raised"]), "resolved_alerts": len(changes["resolved"])}


class HandleBody(BaseModel):
    note: str = ""


@router.post("/alerts/{aid}/handle")
def handle_alert(aid: int, body: HandleBody):
    with write_lock, session() as conn:
        row = conn.execute("SELECT status FROM clinical_alerts WHERE id = ?", (aid,)).fetchone()
        if not row:
            raise HTTPException(404, "Peringatan tidak ditemukan")
        if row["status"] != "open":
            raise HTTPException(409, "Peringatan ini sudah ditindaklanjuti. Muat ulang halaman.")
        conn.execute(
            """
            UPDATE clinical_alerts SET status = 'handled', handled_by = ?, handled_at = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (OPERATOR, now_iso(), body.note.strip()[:500] or None, now_iso(), aid),
        )
        return {"ok": True}


@router.post("/alerts/{aid}/reopen")
def reopen_alert(aid: int):
    with write_lock, session() as conn:
        cur = conn.execute(
            """
            UPDATE clinical_alerts SET status = 'open', handled_by = NULL, handled_at = NULL, note = NULL,
                updated_at = ? WHERE id = ? AND status = 'handled'
            """,
            (now_iso(), aid),
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "Peringatan ini tidak bisa dibuka kembali.")
        return {"ok": True}
