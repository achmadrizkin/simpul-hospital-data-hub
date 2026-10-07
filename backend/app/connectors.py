"""Read-only connectors, one per hospital system.

Every connector returns plain records:
    {"type": "patient" | "event", "key": <id in that system>, "data": {...}}
They never write back to the hospital system.
"""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Callable

from . import hl7
from .db import BASE_DIR
from .normalize import hl7_name

SIM_DIR = BASE_DIR / "simulator"
SIMRS_DB = SIM_DIR / "simrs.db"
BILLING_DB = SIM_DIR / "billing.db"
LIS_INBOX = SIM_DIR / "lis_inbox"
FARMASI_DROP = SIM_DIR / "farmasi_drop"

# Sources with a simulated outage (demo only).
OUTAGES: set[str] = set()

VISIT_TYPES = {"RJ": "Rawat jalan", "RI": "Rawat inap", "IGD": "IGD"}

SOURCES = [
    {
        "code": "simrs",
        "name": "SIMRS",
        "description": "Pendaftaran pasien, kunjungan, dan diagnosis dokter",
        "method": "sql",
        "method_label": "Baca database (hanya-baca)",
        "interval_min": 2,
        "has_nik": 1,
    },
    {
        "code": "lis",
        "name": "Laboratorium",
        "description": "Hasil pemeriksaan lab dari alat analyzer",
        "method": "hl7",
        "method_label": "Pesan HL7 otomatis",
        "interval_min": 0.5,
        "has_nik": 1,
    },
    {
        "code": "farmasi",
        "name": "Farmasi",
        "description": "Resep dan obat yang diberikan ke pasien",
        "method": "file",
        "method_label": "File CSV harian",
        "interval_min": 1,
        "has_nik": 0,
    },
    {
        "code": "billing",
        "name": "Kasir & Tagihan",
        "description": "Tagihan tindakan, obat, dan layanan",
        "method": "sql",
        "method_label": "Baca database (hanya-baca)",
        "interval_min": 5,
        "has_nik": 0,
    },
]

FetchResult = tuple[list[dict], str | None, Callable[[], None]]


def _noop() -> None:
    return None


def _read_db(path: Path) -> sqlite3.Connection:
    # mode=ro: the connector physically cannot write to the hospital database.
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_simrs(watermark: str | None) -> FetchResult:
    wm = watermark or ""
    records: list[dict] = []
    newest = wm
    with closing(_read_db(SIMRS_DB)) as conn:
        for row in conn.execute("SELECT * FROM m_pasien WHERE updated_at > ? ORDER BY updated_at", (wm,)):
            records.append({
                "type": "patient",
                "key": row["no_rm"],
                "data": {
                    "local_id": row["no_rm"],
                    "name": row["nama"],
                    "nik": row["nik"],
                    "birth_date": row["tgl_lahir"],
                    "sex": row["jk"],
                    "address": row["alamat"],
                    "phone": row["no_hp"],
                },
            })
            newest = max(newest, row["updated_at"])
        for row in conn.execute("SELECT * FROM t_kunjungan WHERE updated_at > ? ORDER BY updated_at", (wm,)):
            visit_key = f"KJ-{row['id_kunjungan']}"
            records.append({
                "type": "event",
                "key": visit_key,
                "data": {
                    "local_patient_id": row["no_rm"],
                    "kind": "visit",
                    "occurred_at": row["tgl_masuk"],
                    "title": f"{VISIT_TYPES.get(row['jenis'], row['jenis'])} · {row['poli']}",
                    "detail": row["dokter"],
                    "visit_key": visit_key,
                },
            })
            if row["kd_diag"]:
                records.append({
                    "type": "event",
                    "key": f"{visit_key}-DX",
                    "data": {
                        "local_patient_id": row["no_rm"],
                        "kind": "diagnosis",
                        "occurred_at": row["tgl_masuk"],
                        "title": row["ket_diag"],
                        "code_system": "dx",
                        "local_code": row["kd_diag"],
                        "local_text": row["ket_diag"],
                        "visit_key": visit_key,
                    },
                })
            newest = max(newest, row["updated_at"])
    return records, newest or watermark, _noop


def fetch_billing(watermark: str | None) -> FetchResult:
    wm = watermark or ""
    records: list[dict] = []
    newest = wm
    with closing(_read_db(BILLING_DB)) as conn:
        for row in conn.execute("SELECT * FROM pasien WHERE updated_at > ? ORDER BY updated_at", (wm,)):
            records.append({
                "type": "patient",
                "key": row["id_pasien"],
                "data": {
                    "local_id": row["id_pasien"],
                    "name": row["nama_pasien"],
                    "nik": None,
                    "birth_date": row["tgl_lahir"],
                    "sex": row["jenis_kelamin"],
                    "address": row["alamat"],
                    "phone": row["telp"],
                },
            })
            newest = max(newest, row["updated_at"])
        for row in conn.execute("SELECT * FROM tagihan WHERE updated_at > ? ORDER BY updated_at", (wm,)):
            records.append({
                "type": "event",
                "key": f"TG-{row['id_tagihan']}",
                "data": {
                    "local_patient_id": row["id_pasien"],
                    "kind": "charge",
                    "occurred_at": row["tanggal"],
                    "title": row["uraian"],
                    "amount": row["jumlah"],
                },
            })
            newest = max(newest, row["updated_at"])
    return records, newest or watermark, _noop


def fetch_lis(_watermark: str | None) -> FetchResult:
    LIS_INBOX.mkdir(parents=True, exist_ok=True)
    done_dir = LIS_INBOX / "processed"
    done_dir.mkdir(exist_ok=True)
    files = sorted(LIS_INBOX.glob("*.hl7"))
    records: list[dict] = []
    for path in files:
        msg = hl7.parse(path.read_text(encoding="utf-8"))
        pid, obr, msh = msg["pid"], msg["obr"], msg["msh"]
        local_id = pid["ids"].get("MR")
        records.append({
            "type": "patient",
            "key": local_id,
            "data": {
                "local_id": local_id,
                "name": hl7_name(pid["name"]),
                "nik": pid["ids"].get("NI"),
                "birth_date": pid["birth_date"],
                "sex": pid["sex"],
                "address": pid["address"],
                "phone": pid["phone"],
            },
        })
        for obx in msg["obx"]:
            records.append({
                "type": "event",
                "key": f"{msh['control_id']}-{obx['set_id']}",
                "data": {
                    "local_patient_id": local_id,
                    "kind": "lab",
                    "occurred_at": hl7.hl7_datetime(obr["observed_at"]),
                    "title": obx["text"],
                    "code_system": "lab",
                    "local_code": obx["code"],
                    "local_text": obx["text"],
                    "value": obx["value"],
                    "unit": obx["unit"],
                    "ref_range": obx["ref_range"],
                    "flag": obx["flag"],
                },
            })

    def archive() -> None:
        for path in files:
            path.replace(done_dir / path.name)

    return records, None, archive


def fetch_farmasi(_watermark: str | None) -> FetchResult:
    FARMASI_DROP.mkdir(parents=True, exist_ok=True)
    done_dir = FARMASI_DROP / "processed"
    done_dir.mkdir(exist_ok=True)
    files = sorted(FARMASI_DROP.glob("*.csv"))
    records: list[dict] = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                local_id = row["no_rm_farmasi"].strip()
                records.append({
                    "type": "patient",
                    "key": local_id,
                    "data": {
                        "local_id": local_id,
                        "name": row["nama_pasien"],
                        "nik": None,
                        "birth_date": row["tgl_lahir"],
                        "sex": row["jk"],
                        "address": None,
                        "phone": None,
                    },
                })
                records.append({
                    "type": "event",
                    "key": f"{row['no_resep']}-{row['nama_obat']}",
                    "data": {
                        "local_patient_id": local_id,
                        "kind": "medication",
                        "occurred_at": row["tgl_resep"],
                        "title": row["nama_obat"],
                        "detail": f"{row['aturan_pakai']} · {row['jumlah']} buah",
                        "code_system": "obat",
                        "local_code": row["nama_obat"],
                        "local_text": row["nama_obat"],
                    },
                })

    def archive() -> None:
        for path in files:
            path.replace(done_dir / path.name)

    return records, None, archive


FETCHERS = {
    "simrs": fetch_simrs,
    "billing": fetch_billing,
    "lis": fetch_lis,
    "farmasi": fetch_farmasi,
}

OUTAGE_MESSAGES = {
    "simrs": "Tidak bisa terhubung ke database SIMRS (waktu tunggu habis setelah 10 detik).",
    "billing": "Tidak bisa terhubung ke database Kasir (waktu tunggu habis setelah 10 detik).",
    "lis": "Koneksi dari alat lab terputus.",
    "farmasi": "Folder file farmasi tidak bisa dibuka.",
}


def fetch(code: str, watermark: str | None) -> FetchResult:
    if code in OUTAGES:
        raise ConnectionError(OUTAGE_MESSAGES[code])
    return FETCHERS[code](watermark)
