"""Master Patient Index: decide which local patient records belong to the same person.

The score is a weighted sum of simple, explainable signals so the medical records team
can see exactly why two records were linked.
"""

import json
import sqlite3
from difflib import SequenceMatcher

from .db import now_iso
from .normalize import birth_date_problem, clean_address, nik_is_valid

WEIGHTS = {"dob": 0.35, "name": 0.30, "phone": 0.15, "sex": 0.10, "address": 0.10}
AUTO_LINK = 0.90
REVIEW = 0.70

FIELD_LABELS = {
    "nik": "NIK",
    "dob": "Tanggal lahir",
    "name": "Nama",
    "phone": "Nomor HP",
    "sex": "Jenis kelamin",
    "address": "Alamat",
}


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    direct = _ratio(a, b)
    sorted_tokens = _ratio(" ".join(sorted(a.split())), " ".join(sorted(b.split())))
    return max(direct, sorted_tokens)


def address_similarity(a: str, b: str) -> float:
    a, b = clean_address(a), clean_address(b)
    if not a or not b:
        return 0.0
    short, long_ = sorted((set(a.split()), set(b.split())), key=len)
    containment = 0.9 if short and short <= long_ else 0.0
    return max(_ratio(a, b), containment)


def dob_similarity(a: str, b: str) -> tuple[float, str]:
    if a == b:
        return 1.0, "sama"
    ya, ma, da = a.split("-")
    yb, mb, db = b.split("-")
    if ya == yb and ma == db and da == mb:
        return 0.6, "mirip (hari dan bulan tertukar)"
    return 0.0, "beda"


def _verdict(sim: float) -> str:
    if sim >= 0.97:
        return "sama"
    if sim >= 0.75:
        return "mirip"
    return "beda"


def compare(a: sqlite3.Row, b: sqlite3.Row) -> tuple[float, list[dict]]:
    reasons: list[dict] = []
    if nik_is_valid(a["nik"]) and nik_is_valid(b["nik"]):
        if a["nik"] == b["nik"]:
            reasons.append({"field": "nik", "label": "NIK", "result": "sama", "weight": 1.0})
            return 1.0, reasons
        reasons.append({"field": "nik", "label": "NIK", "result": "beda", "weight": 1.0})
        return 0.0, reasons

    total = 0.0
    available = 0.0
    exact_dob = False

    def add(field: str, sim: float, result: str | None = None) -> None:
        nonlocal total, available
        weight = WEIGHTS[field]
        total += weight * sim
        available += weight
        reasons.append({
            "field": field,
            "label": FIELD_LABELS[field],
            "result": result or _verdict(sim),
            "weight": weight,
            "similarity": round(sim, 2),
        })

    dob_a = None if birth_date_problem(a["birth_date"]) else a["birth_date"]
    dob_b = None if birth_date_problem(b["birth_date"]) else b["birth_date"]
    if dob_a and dob_b:
        sim, result = dob_similarity(dob_a, dob_b)
        exact_dob = sim == 1.0
        add("dob", sim, result)
    else:
        reasons.append({"field": "dob", "label": "Tanggal lahir", "result": "tidak bisa dibandingkan"})

    name_sim = name_similarity(a["name"], b["name"])
    add("name", name_sim)

    for field, col in (("sex", "sex"), ("phone", "phone")):
        if a[col] and b[col]:
            add(field, 1.0 if a[col] == b[col] else 0.0)
        else:
            reasons.append({"field": field, "label": FIELD_LABELS[field], "result": "tidak ada"})

    if a["address"] and b["address"]:
        add("address", address_similarity(a["address"], b["address"]))
    else:
        reasons.append({"field": "address", "label": "Alamat", "result": "tidak ada"})

    score = total / available if available else 0.0
    # Never link automatically without an exact birth date, a near-identical name and enough evidence.
    if not exact_dob or name_sim < 0.85 or available < 0.6:
        score = min(score, AUTO_LINK - 0.01)
    return round(score, 2), reasons


def _new_golden(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO patients (created_at) VALUES (?)", (now_iso(),))
    return cur.lastrowid


def match_new_record(conn: sqlite3.Connection, sp_id: int) -> None:
    sp = conn.execute("SELECT * FROM source_patients WHERE id = ?", (sp_id,)).fetchone()
    year = (sp["birth_date"] or "")[:4]
    first = (sp["name"] or "").split(" ")[0][:3]
    others = conn.execute(
        """
        SELECT * FROM source_patients
        WHERE id != ? AND golden_id IS NOT NULL
          AND (nik = ? OR substr(birth_date, 1, 4) = ? OR substr(name, 1, 3) = ? OR phone = ?)
        """,
        (sp_id, sp["nik"] or "-", year or "-", first or "-", sp["phone"] or "-"),
    ).fetchall()

    best_by_golden: dict[int, tuple[float, sqlite3.Row, list]] = {}
    for other in others:
        score, reasons = compare(sp, other)
        current = best_by_golden.get(other["golden_id"])
        if current is None or score > current[0]:
            best_by_golden[other["golden_id"]] = (score, other, reasons)

    ranked = sorted(best_by_golden.items(), key=lambda item: item[1][0], reverse=True)
    if ranked and ranked[0][1][0] >= AUTO_LINK:
        golden_id, (score, _other, _reasons) = ranked[0]
        conn.execute(
            "UPDATE source_patients SET golden_id = ?, match_score = ?, linked_by = 'otomatis' WHERE id = ?",
            (golden_id, score, sp_id),
        )
        return

    golden_id = _new_golden(conn)
    conn.execute(
        "UPDATE source_patients SET golden_id = ?, match_score = NULL, linked_by = 'baru' WHERE id = ?",
        (golden_id, sp_id),
    )
    for _gid, (score, other, reasons) in ranked[:3]:
        if score < REVIEW:
            break
        conn.execute(
            """
            INSERT OR IGNORE INTO mpi_candidates (sp_a, sp_b, score, reasons, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (other["id"], sp_id, score, json.dumps(reasons), now_iso()),
        )


def merge(conn: sqlite3.Connection, candidate_id: int, decided_by: str) -> dict:
    cand = conn.execute("SELECT * FROM mpi_candidates WHERE id = ?", (candidate_id,)).fetchone()
    a = conn.execute("SELECT golden_id FROM source_patients WHERE id = ?", (cand["sp_a"],)).fetchone()
    b = conn.execute("SELECT golden_id FROM source_patients WHERE id = ?", (cand["sp_b"],)).fetchone()
    keep, drop = a["golden_id"], b["golden_id"]
    moved: list[int] = []
    if keep != drop:
        moved = [r["id"] for r in conn.execute(
            "SELECT id FROM source_patients WHERE golden_id = ?", (drop,)
        )]
        conn.execute(
            "UPDATE source_patients SET golden_id = ?, linked_by = 'petugas' WHERE golden_id = ?",
            (keep, drop),
        )
        conn.execute("UPDATE patients SET merged_into = ? WHERE id = ?", (keep, drop))
    conn.execute(
        """
        UPDATE mpi_candidates SET status = 'merged', decided_at = ?, decided_by = ?, undo_info = ?
        WHERE id = ?
        """,
        (now_iso(), decided_by, json.dumps({"from_golden": drop, "moved": moved}), candidate_id),
    )
    _close_resolved(conn)
    return {"golden_id": keep}


def reject(conn: sqlite3.Connection, candidate_id: int, decided_by: str) -> None:
    conn.execute(
        "UPDATE mpi_candidates SET status = 'rejected', decided_at = ?, decided_by = ? WHERE id = ?",
        (now_iso(), decided_by, candidate_id),
    )


def undo(conn: sqlite3.Connection, candidate_id: int) -> None:
    cand = conn.execute("SELECT * FROM mpi_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if cand["status"] == "merged" and cand["undo_info"]:
        info = json.loads(cand["undo_info"])
        if info["moved"]:
            marks = ",".join("?" * len(info["moved"]))
            conn.execute(
                f"UPDATE source_patients SET golden_id = ?, linked_by = 'baru' WHERE id IN ({marks})",
                (info["from_golden"], *info["moved"]),
            )
            conn.execute("UPDATE patients SET merged_into = NULL WHERE id = ?", (info["from_golden"],))
            conn.execute(
                """
                UPDATE mpi_candidates SET status = 'pending', decided_at = NULL, decided_by = NULL
                WHERE status = 'merged' AND decided_by = 'otomatis (ikut tergabung)'
                """
            )
    conn.execute(
        """
        UPDATE mpi_candidates SET status = 'pending', decided_at = NULL, decided_by = NULL, undo_info = NULL
        WHERE id = ?
        """,
        (candidate_id,),
    )
    _close_resolved(conn)


def _close_resolved(conn: sqlite3.Connection) -> None:
    """Pending pairs whose two records already share one patient need no decision."""
    conn.execute(
        """
        UPDATE mpi_candidates SET status = 'merged', decided_at = ?, decided_by = 'otomatis (ikut tergabung)'
        WHERE status = 'pending' AND (
            SELECT golden_id FROM source_patients WHERE id = sp_a
        ) = (
            SELECT golden_id FROM source_patients WHERE id = sp_b
        )
        """,
        (now_iso(),),
    )
