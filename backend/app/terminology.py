"""Map local codes (diagnosis, lab, medicine) to standard code sets."""

import sqlite3
from difflib import SequenceMatcher

from .db import now_iso
from .reference import KNOWN_ABBREVIATIONS, STARTER_DICTIONARY, catalog, std_text


def suggest(system: str, local_code: str, local_text: str | None) -> tuple[str | None, str]:
    known = KNOWN_ABBREVIATIONS.get(system, {}).get(local_code)
    if known:
        return known, "singkatan yang dikenali"
    text = (local_text or local_code).lower()
    best_code, best_score = None, 0.0
    for code, name in catalog(system):
        score = SequenceMatcher(None, text, name.lower()).ratio()
        if score > best_score:
            best_code, best_score = code, score
    if best_score >= 0.55:
        return best_code, "kemiripan teks"
    return None, "tidak ada saran"


def ensure_mapping(conn: sqlite3.Connection, system: str, local_code: str, local_text: str | None) -> None:
    if not local_code:
        return
    exists = conn.execute(
        "SELECT 1 FROM code_mappings WHERE system = ? AND local_code = ?", (system, local_code)
    ).fetchone()
    if exists:
        return

    if std_text(system, local_code):
        code, status, by, confirmed_by = local_code, "confirmed", "sudah kode standar", "Sistem"
    elif local_code in STARTER_DICTIONARY.get(system, {}):
        code = STARTER_DICTIONARY[system][local_code]
        status, by, confirmed_by = "confirmed", "kamus awal RS", "Kamus awal RS"
    else:
        code, by = suggest(system, local_code, local_text)
        status, confirmed_by = ("suggested" if code else "unmapped"), None

    conn.execute(
        """
        INSERT INTO code_mappings
            (system, local_code, local_text, std_code, std_text, status, suggested_by, confirmed_by, confirmed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            system, local_code, local_text, code, std_text(system, code), status, by,
            confirmed_by, now_iso() if confirmed_by else None,
        ),
    )
