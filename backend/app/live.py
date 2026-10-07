"""Background scheduler plus a simulator that keeps the demo hospital 'alive'."""

import asyncio
import csv
import io
import json
import random
from datetime import datetime

from .connectors import FARMASI_DROP, LIS_INBOX
from .db import session
from .pipeline import sync_source
from .seed import CONDITIONS, STATE_FILE, _flag, _lab_value, hl7_message

LIVE = {"enabled": True, "interval_sec": 40}


def _load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


LAB_PANELS = [
    [c for c in CONDITIONS["DM2"]["labs"]][:1],
    CONDITIONS["DHF"]["labs"],
    CONDITIONS["DISLIP"]["labs"],
    CONDITIONS["CHF"]["labs"],
]


def send_lab_message() -> dict:
    """Simulate the lab analyzer sending one new HL7 result message."""
    rng = random.Random()
    state = _load_state()
    patient = rng.choice(state["lis_patients"])
    panel = rng.choice(LAB_PANELS)
    now = datetime.now().replace(microsecond=0)
    results = []
    for code, text, unit, ref, value_range in panel:
        value = _lab_value(rng, value_range)
        results.append({"code": code, "text": text, "unit": unit, "ref": ref,
                        "value": value, "flag": _flag(value, ref)})
    state["next_lab_msg"] += 1
    control_id = f"LAB{state['next_lab_msg']:06d}"
    LIS_INBOX.mkdir(parents=True, exist_ok=True)
    (LIS_INBOX / f"ORU_{state['next_lab_msg']:06d}.hl7").write_text(
        hl7_message(control_id, patient, now, results), encoding="utf-8"
    )
    _save_state(state)
    return {"patient": patient["hl7_name"], "tests": [r["text"] for r in results]}


def sample_farmasi_csv() -> str:
    """Today's pharmacy export: a few known patients plus one first-time patient."""
    rng = random.Random()
    state = _load_state()
    now = datetime.now().replace(microsecond=0)
    out = io.StringIO()
    fields = ["tgl_resep", "no_resep", "no_rm_farmasi", "nama_pasien", "tgl_lahir", "jk",
              "nama_obat", "aturan_pakai", "jumlah"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    picks = rng.sample(state["farmasi_patients"], k=3)
    picks.append({"local_id": f"F9{rng.randint(1000, 9999)}", "name": "Yohana Simatupang",
                  "dob": "14-02-1994", "sex": "P"})
    meds = [("PCT 500", "3x1 bila demam", 10), ("Amox 500", "3x1 dihabiskan", 15),
            ("Omz 20", "2x1 sebelum makan", 14), ("Vit B Kompleks", "1x1", 30)]
    for patient in picks:
        state["next_resep"] += 1
        med, rule, qty = rng.choice(meds)
        writer.writerow({
            "tgl_resep": now.isoformat(), "no_resep": f"R{state['next_resep']}",
            "no_rm_farmasi": patient["local_id"], "nama_pasien": patient["name"],
            "tgl_lahir": patient["dob"], "jk": patient["sex"], "nama_obat": med,
            "aturan_pakai": rule, "jumlah": qty,
        })
    _save_state(state)
    return out.getvalue()


def save_farmasi_upload(filename: str, content: bytes) -> None:
    FARMASI_DROP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-") or "upload.csv"
    (FARMASI_DROP / f"{stamp}_{safe}").write_bytes(content)


def _due_sources() -> list[str]:
    now = datetime.now()
    due = []
    with session() as conn:
        for src in conn.execute("SELECT code, interval_min, last_sync_at FROM sources"):
            if not src["last_sync_at"]:
                due.append(src["code"])
                continue
            elapsed = (now - datetime.fromisoformat(src["last_sync_at"])).total_seconds()
            if elapsed >= src["interval_min"] * 60:
                due.append(src["code"])
    return due


async def scheduler_loop() -> None:
    last_lab = datetime.now()
    while True:
        await asyncio.sleep(10)
        try:
            if LIVE["enabled"] and (datetime.now() - last_lab).total_seconds() >= LIVE["interval_sec"]:
                await asyncio.to_thread(send_lab_message)
                last_lab = datetime.now()
            for code in await asyncio.to_thread(_due_sources):
                await asyncio.to_thread(sync_source, code)
        except Exception as exc:  # keep the scheduler alive no matter what
            print(f"[scheduler] {exc}")
