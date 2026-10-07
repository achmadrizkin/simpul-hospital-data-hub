"""Cross-system clinical alerts.

Each rule needs data from at least two different hospital systems, so these alerts can only
exist once Simpul has unified the patient. Rules read standard codes (ATC, LOINC, ICD-10) via
confirmed code mappings, never local abbreviations.

These are example rules for the demo, not clinical decision support.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from .db import now_iso


@dataclass
class Rule:
    code: str
    title: str
    description: str
    severity: str
    sources: list[str]
    check: Callable[[dict], tuple[str, list[dict]] | None]


def _num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _evidence(event: dict) -> dict:
    return {
        "event_id": event["id"],
        "source": event["source_code"],
        "kind": event["kind"],
        "title": event["std_text"] or event["title"],
        "detail": event["detail"],
        "code": event["std_code"],
        "value": event["value"],
        "unit": event["unit"],
        "flag": event["flag"],
        "occurred_at": event["occurred_at"],
    }


def _recent(event: dict, days: int) -> bool:
    return event["occurred_at"][:10] >= (date.today() - timedelta(days=days)).isoformat()


def check_metformin_kidney(f: dict) -> tuple[str, list[dict]] | None:
    metformin = [e for e in f["meds"].get("A10BA02", []) if _recent(e, 180)]
    creat = f["labs"].get("2160-0")
    if not metformin or not creat or (_num(creat["value"]) or 0) <= 1.3:
        return None
    return (
        f"Pasien mendapat metformin, padahal kreatinin terakhir {creat['value']} {creat['unit']} (di atas 1,3). "
        "Fungsi ginjal yang menurun perlu dipertimbangkan sebelum melanjutkan metformin.",
        [_evidence(metformin[0]), _evidence(creat)],
    )


def check_uncontrolled_diabetes(f: dict) -> tuple[str, list[dict]] | None:
    dx = next((e for code, items in f["dx"].items() if code.startswith("E11") for e in items), None)
    if not dx:
        return None
    hba1c = f["labs"].get("4548-4")
    gds = f["labs"].get("2339-0")
    reasons, evidence = [], [_evidence(dx)]
    if hba1c and (_num(hba1c["value"]) or 0) >= 7.0:
        reasons.append(f"HbA1c {hba1c['value']}%")
        evidence.append(_evidence(hba1c))
    if gds and (_num(gds["value"]) or 0) >= 200:
        reasons.append(f"gula darah sewaktu {gds['value']} {gds['unit']}")
        evidence.append(_evidence(gds))
    if not reasons:
        return None
    return (
        f"Pasien terdiagnosis diabetes tipe 2 dan hasil lab terakhir menunjukkan gula belum terkontrol "
        f"({' dan '.join(reasons)}). Perlu evaluasi pengobatan pada kunjungan berikutnya.",
        evidence,
    )


def check_cholesterol_untreated(f: dict) -> tuple[str, list[dict]] | None:
    chol = f["labs"].get("2093-3")
    if not chol or (_num(chol["value"]) or 0) < 240:
        return None
    statin = [e for e in f["meds"].get("C10AA01", []) if _recent(e, 120)]
    if statin:
        return None
    return (
        f"Kolesterol total {chol['value']} {chol['unit']} (tinggi), tetapi tidak ada obat penurun kolesterol "
        "(statin) yang dikenali di data Farmasi dalam 4 bulan terakhir.",
        [_evidence(chol)],
    )


def check_low_platelets_no_followup(f: dict) -> tuple[str, list[dict]] | None:
    plt = f["labs"].get("777-3")
    if not plt or (_num(plt["value"]) or 999) >= 100:
        return None
    lab_day = plt["occurred_at"][:10]
    follow_up = [
        e for e in f["visits"]
        if e["occurred_at"][:10] >= lab_day and e["title"].startswith(("Rawat inap", "IGD"))
    ]
    if follow_up:
        return None
    return (
        f"Trombosit {plt['value']} {plt['unit']} (sangat rendah) pada {lab_day}, tetapi tidak ada kunjungan "
        "IGD atau rawat inap yang tercatat di SIMRS setelahnya.",
        [_evidence(plt)],
    )


RULES = [
    Rule(
        "METFORMIN_GINJAL",
        "Metformin dengan fungsi ginjal menurun",
        "Obat metformin dari Farmasi + kreatinin tinggi dari Lab.",
        "tinggi",
        ["farmasi", "lis"],
        check_metformin_kidney,
    ),
    Rule(
        "TROMBOSIT_RENDAH_TANPA_TINDAK_LANJUT",
        "Trombosit sangat rendah tanpa tindak lanjut",
        "Trombosit < 100 dari Lab, tanpa kunjungan IGD/rawat inap di SIMRS sesudahnya.",
        "tinggi",
        ["lis", "simrs"],
        check_low_platelets_no_followup,
    ),
    Rule(
        "DIABETES_TIDAK_TERKONTROL",
        "Diabetes belum terkontrol",
        "Diagnosis diabetes tipe 2 dari SIMRS + HbA1c ≥ 7% atau gula darah sewaktu ≥ 200 dari Lab.",
        "sedang",
        ["simrs", "lis"],
        check_uncontrolled_diabetes,
    ),
    Rule(
        "KOLESTEROL_TANPA_OBAT",
        "Kolesterol tinggi tanpa obat",
        "Kolesterol total ≥ 240 dari Lab, tanpa statin di Farmasi dalam 4 bulan.",
        "sedang",
        ["lis", "farmasi"],
        check_cholesterol_untreated,
    ),
]
RULES_BY_CODE = {r.code: r for r in RULES}


def register_rules(conn: sqlite3.Connection) -> None:
    for rule in RULES:
        conn.execute(
            """
            INSERT INTO alert_rules (code, title, description, severity, sources, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(code) DO UPDATE SET
                title = excluded.title, description = excluded.description,
                severity = excluded.severity, sources = excluded.sources
            """,
            (rule.code, rule.title, rule.description, rule.severity, json.dumps(rule.sources)),
        )


def _facts(conn: sqlite3.Connection, gid: int, mappings: dict) -> dict:
    rows = conn.execute(
        """
        SELECT e.* FROM events e
        JOIN source_patients sp ON sp.source_code = e.source_code AND sp.local_id = e.local_patient_id
        WHERE sp.golden_id = ?
        ORDER BY e.occurred_at DESC
        """,
        (gid,),
    ).fetchall()
    facts: dict = {"meds": {}, "labs": {}, "dx": {}, "visits": []}
    for row in rows:
        event = dict(row)
        std = mappings.get((row["code_system"], row["local_code"]))
        event["std_code"] = std[0] if std else None
        event["std_text"] = std[1] if std else None
        if row["kind"] == "visit":
            facts["visits"].append(event)
        elif row["kind"] == "medication" and std:
            facts["meds"].setdefault(std[0], []).append(event)
        elif row["kind"] == "diagnosis" and std:
            facts["dx"].setdefault(std[0], []).append(event)
        elif row["kind"] == "lab" and std:
            facts["labs"].setdefault(std[0], event)  # newest first, keep the latest
    return facts


def evaluate(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Re-check every rule for every patient. Returns alerts newly raised and newly resolved."""
    mappings = {
        (r["system"], r["local_code"]): (r["std_code"], r["std_text"])
        for r in conn.execute("SELECT * FROM code_mappings WHERE status = 'confirmed'")
    }
    enabled = {r["code"] for r in conn.execute("SELECT code FROM alert_rules WHERE enabled = 1")}
    patients = [r["id"] for r in conn.execute("SELECT id FROM patients WHERE merged_into IS NULL")]
    raised: list[dict] = []
    resolved: list[dict] = []
    now = now_iso()

    for gid in patients:
        facts = _facts(conn, gid, mappings)
        for rule in RULES:
            existing = conn.execute(
                "SELECT * FROM clinical_alerts WHERE golden_id = ? AND rule_code = ?", (gid, rule.code)
            ).fetchone()
            result = rule.check(facts) if rule.code in enabled else None
            if result:
                detail, evidence = result
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO clinical_alerts (golden_id, rule_code, detail, evidence, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 'open', ?, ?)
                        """,
                        (gid, rule.code, detail, json.dumps(evidence), now, now),
                    )
                    raised.append({"golden_id": gid, "rule": rule.code})
                elif existing["status"] == "resolved":
                    conn.execute(
                        """
                        UPDATE clinical_alerts SET status = 'open', detail = ?, evidence = ?, created_at = ?,
                            updated_at = ?, resolved_at = NULL, handled_by = NULL, handled_at = NULL, note = NULL
                        WHERE id = ?
                        """,
                        (detail, json.dumps(evidence), now, now, existing["id"]),
                    )
                    raised.append({"golden_id": gid, "rule": rule.code})
                elif existing["detail"] != detail or existing["evidence"] != json.dumps(evidence):
                    conn.execute(
                        "UPDATE clinical_alerts SET detail = ?, evidence = ?, updated_at = ? WHERE id = ?",
                        (detail, json.dumps(evidence), now, existing["id"]),
                    )
            elif existing is not None and existing["status"] != "resolved":
                conn.execute(
                    "UPDATE clinical_alerts SET status = 'resolved', resolved_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, existing["id"]),
                )
                resolved.append({"golden_id": gid, "rule": rule.code})

    # Alerts of patients that were merged into someone else no longer apply.
    conn.execute(
        """
        UPDATE clinical_alerts SET status = 'resolved', resolved_at = ?, updated_at = ?
        WHERE status != 'resolved' AND golden_id IN (SELECT id FROM patients WHERE merged_into IS NOT NULL)
        """,
        (now, now),
    )
    return {"raised": raised, "resolved": resolved}
