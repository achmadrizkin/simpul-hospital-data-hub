"""Build four fake hospital systems with realistic, deliberately messy synthetic data.

Run:  python -m app.seed
All people, NIKs, and phone numbers are invented.
"""

import csv
import json
import random
import shutil
import sqlite3
from datetime import date, datetime, timedelta

from . import connectors
from .connectors import BILLING_DB, FARMASI_DROP, LIS_INBOX, SIM_DIR, SIMRS_DB
from .db import reset_db, write_lock
from .pipeline import register_sources, sync_source

STATE_FILE = SIM_DIR / "state.json"

FIRST_M = ["Budi", "Agus", "Andi", "Rudi", "Hendra", "Joko", "Dedi", "Eko", "Fajar", "Arif",
           "Bambang", "Slamet", "Yusuf", "Ahmad", "Wahyu", "Teguh", "Imam", "Dimas", "Bayu", "Rizal"]
FIRST_F = ["Dewi", "Sri", "Rina", "Ani", "Wati", "Nur", "Fitri", "Yuni", "Indah", "Ratna",
           "Putri", "Maya", "Ayu", "Endang", "Kartika", "Nining", "Rahma", "Lina", "Wulan", "Sari"]
LAST = ["Santoso", "Wijaya", "Saputra", "Hidayat", "Kurniawan", "Setiawan", "Pratama", "Nugroho",
        "Susanto", "Rahayu", "Lestari", "Wulandari", "Hasanah", "Siregar", "Nasution", "Simanjuntak",
        "Harahap", "Purba", "Gunawan", "Halim", "Firmansyah", "Maulana", "Ramadhan", "Kusuma"]

# (city, NIK region code, short form, districts)
CITIES = [
    ("Jakarta Timur", "3172", "Jaktim", ["Duren Sawit", "Cakung", "Kramat Jati", "Pulo Gadung", "Matraman"]),
    ("Jakarta Selatan", "3171", "Jaksel", ["Tebet", "Pancoran", "Cilandak"]),
    ("Bekasi", "3275", "Bekasi", ["Bekasi Barat", "Rawalumbu"]),
    ("Depok", "3276", "Depok", ["Beji", "Sukmajaya"]),
]
STREETS = ["Kalimalang", "Pemuda", "Raya Bogor", "Pramuka", "Melati", "Mawar", "Swadaya", "Masjid",
           "Haji Naman", "Cipinang Indah"]

DOCTORS = {
    "Penyakit Dalam": "dr. Andini Pratiwi, Sp.PD",
    "Umum": "dr. Bagus Wicaksono",
    "Jantung": "dr. Hendro Saputra, Sp.JP",
    "Paru": "dr. Melati Kusuma, Sp.P",
    "Saraf": "dr. Yoga Prasetyo, Sp.N",
    "IGD": "dr. Citra Ananda",
}

# condition -> local diagnosis code/text, clinic, visit type, labs, medicines
CONDITIONS = {
    "DM2": {
        "dx": ("DM2", "Diabetes melitus tipe 2"), "poli": "Penyakit Dalam", "type": "RJ",
        "labs": [("GDS", "Gula Darah Sewaktu", "mg/dL", "70-140", (180, 360)),
                 ("HBA1C", "HbA1c", "%", "4.0-5.7", (7.0, 10.5))],
        "meds": [("Mtf 500", "3x1 sesudah makan", 90)], "min_age": 35,
    },
    "HT": {
        "dx": ("HT", "Hipertensi"), "poli": "Penyakit Dalam", "type": "RJ",
        "labs": [("KREA", "Kreatinin", "mg/dL", "0.6-1.2", (0.7, 1.6))],
        "meds": [("Amlo 10", "1x1 pagi", 30), ("Captopril 25", "2x1", 60)], "min_age": 35,
    },
    "ISPA": {
        "dx": ("ISPA", "Infeksi saluran pernapasan atas"), "poli": "Umum", "type": "RJ",
        "labs": [],
        "meds": [("Amox 500", "3x1 dihabiskan", 15), ("PCT 500", "3x1 bila demam", 10),
                 ("Cetirizine 10", "1x1 malam", 5)], "min_age": 0,
    },
    "GEA": {
        "dx": ("GEA", "Gastroenteritis akut"), "poli": "Umum", "type": "RJ",
        "labs": [("LEU", "Leukosit", "10^3/uL", "4-10", (9.5, 14.0))],
        "meds": [("Oralit", "setiap BAB cair", 6)], "min_age": 0,
    },
    "DHF": {
        "dx": ("DHF", "Demam berdarah dengue"), "poli": "IGD", "type": "RI",
        "labs": [("TROMBO", "Trombosit", "10^3/uL", "150-400", (40, 110)),
                 ("HB", "Hemoglobin", "g/dL", "12-16", (13.5, 17.5)),
                 ("LEU", "Leukosit", "10^3/uL", "4-10", (2.5, 4.0))],
        "meds": [("PCT 500", "3x1 bila demam", 10)], "min_age": 5,
    },
    "CHF": {
        "dx": ("CHF", "Gagal jantung kongestif"), "poli": "Jantung", "type": "RI",
        "labs": [("UREUM", "Ureum", "mg/dL", "15-40", (45, 90)),
                 ("KREA", "Kreatinin", "mg/dL", "0.6-1.2", (1.2, 2.2))],
        "meds": [("Furo inj", "2x1 ampul IV", 4)], "min_age": 50,
    },
    "DISP": {
        "dx": ("DISP", "Dispepsia"), "poli": "Umum", "type": "RJ",
        "labs": [], "meds": [("Omz 20", "2x1 sebelum makan", 14)], "min_age": 15,
    },
    "DISLIP": {
        "dx": ("DISLIP", "Dislipidemia"), "poli": "Penyakit Dalam", "type": "RJ",
        "labs": [("KOL", "Kolesterol Total", "mg/dL", "0-200", (220, 300)),
                 ("TG", "Trigliserida", "mg/dL", "0-150", (170, 320))],
        "meds": [("Simva 20", "1x1 malam", 30)], "min_age": 30,
    },
    "FEBRIS": {
        "dx": ("OBS FEBRIS", "Observasi febris"), "poli": "Umum", "type": "RJ",
        "labs": [("LEU", "Leukosit", "10^3/uL", "4-10", (6, 11)),
                 ("TROMBO", "Trombosit", "10^3/uL", "150-400", (160, 300))],
        "meds": [("PCT 500", "3x1 bila demam", 10)], "min_age": 0,
    },
    "ASMA": {
        "dx": ("ASMA", "Asma bronkial"), "poli": "Paru", "type": "RJ",
        "labs": [], "meds": [("Salbu 2", "3x1", 15)], "min_age": 5,
    },
    "GASTRITIS": {
        "dx": ("GASTRITIS", "Gastritis"), "poli": "Umum", "type": "RJ",
        "labs": [], "meds": [("Ranitidin 150", "2x1", 14)], "min_age": 15,
    },
    "ISK": {
        "dx": ("ISK", "Infeksi saluran kemih"), "poli": "Penyakit Dalam", "type": "RI",
        "labs": [("LEU", "Leukosit", "10^3/uL", "4-10", (11, 16))],
        "meds": [("Cefx 1g", "2x1 vial IV", 6)], "min_age": 15,
    },
    "CEPHALGIA": {
        "dx": ("CEPHALGIA", "Cephalgia"), "poli": "Saraf", "type": "RJ",
        "labs": [], "meds": [("PCT 500", "3x1", 10)], "min_age": 12,
    },
}


def _age(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _typo(rng: random.Random, name: str) -> str:
    swaps = [("i", "y"), ("u", "oe"), ("ph", "f"), ("dj", "j"), ("a", "aa")]
    rng.shuffle(swaps)
    for old, new in swaps:
        idx = name.lower().find(old, 1)
        if idx > 0:
            return name[:idx] + new + name[idx + len(old):]
    return name + "h"


def _nik(rng: random.Random, region: str, dob: date, sex: str) -> str:
    day = dob.day + (40 if sex == "P" else 0)
    return f"{region}{rng.randint(1, 10):02d}{day:02d}{dob.month:02d}{dob.year % 100:02d}{rng.randint(1, 9999):04d}"


def _phone(rng: random.Random) -> str:
    return "08" + rng.choice(["12", "13", "21", "52", "57", "77", "95"]) + "".join(
        str(rng.randint(0, 9)) for _ in range(8)
    )


def _person(rng: random.Random, today: date, **fixed) -> dict:
    sex = fixed.get("sex") or rng.choice("LP")
    first = rng.choice(FIRST_M if sex == "L" else FIRST_F)
    name = fixed.get("name") or f"{first} {rng.choice(LAST)}"
    dob = fixed.get("dob") or (today - timedelta(days=rng.randint(6 * 365, 82 * 365)))
    city, region, short, districts = fixed.get("city") or rng.choice(CITIES)
    district = rng.choice(districts)
    age = _age(dob, today)
    options = [c for c, meta in CONDITIONS.items() if age >= meta["min_age"]]
    conditions = fixed.get("conditions") or rng.sample(options, k=rng.choice([1, 1, 2]))
    return {
        "name": name,
        "sex": sex,
        "dob": dob,
        "nik": fixed.get("nik") or _nik(rng, region, dob, sex),
        "phone": fixed.get("phone") or _phone(rng),
        "address": fixed.get("address")
        or f"Jl. {rng.choice(STREETS)} No. {rng.randint(1, 120)}, {district}, {city}",
        "city": city,
        "city_short": short,
        "conditions": conditions,
        "overrides": fixed.get("overrides", {}),
    }


def _lab_value(rng: random.Random, low_high: tuple) -> float:
    value = rng.uniform(*low_high)
    return round(value, 1) if value < 20 else round(value)


def _flag(value: float, ref: str) -> str:
    low, high = (float(x) for x in ref.split("-"))
    if value > high:
        return "H"
    if value < low:
        return "L"
    return "N"


def build_people(rng: random.Random, today: date) -> list[dict]:
    jaktim = CITIES[0]
    depok = CITIES[3]
    people = [
        _person(
            rng, today, name="Siti Aminah", sex="P", dob=date(1967, 3, 12), city=jaktim,
            nik="3172015203670001", phone="081234567890", conditions=["DM2", "HT"],
            address="Jl. Kalimalang No. 12, Duren Sawit, Jakarta Timur",
            overrides={
                "simrs_name": "Ny. Siti Aminah", "simrs_nik": "",
                "lis_name": "AMINAH^SITI S.", "lis_dob": "19671203",
                "billing_phone": "+62 812-3456-7890", "billing_name": "SITI AMINAH",
                "visits": 3,
            },
        ),
        _person(
            rng, today, name="Muhammad Rizki", sex="L", dob=date(1990, 5, 17), city=jaktim,
            phone="081311223344", conditions=["ISPA"],
            address="Jl. Pemuda No. 7, Pulo Gadung, Jakarta Timur",
            overrides={"simrs_name": "Tn. Muhammad Rizki"},
        ),
        _person(
            rng, today, name="Muhammad Rizki", sex="L", dob=date(1990, 5, 17), city=depok,
            phone="085799887766", conditions=["GASTRITIS"],
            address="Jl. Margonda Gg. Haji No. 3, Beji, Depok",
            overrides={"simrs_nik": ""},
        ),
        _person(
            rng, today, name="Budi Santoso", sex="L", dob=date(1958, 8, 20), city=jaktim,
            phone="081298765432", conditions=["CHF", "HT"],
            address="Jl. Pramuka No. 45, Matraman, Jakarta Timur",
            overrides={"simrs_duplicate": True},
        ),
        _person(
            rng, today, name="Ratna Dewi Kusuma", sex="P", dob=date(1985, 11, 2), city=CITIES[1],
            conditions=["CEPHALGIA", "DISP"],
            overrides={"simrs_dob": "1900-01-01"},
        ),
    ]
    for _ in range(43):
        people.append(_person(rng, today))
    return people


def build_visits(rng: random.Random, today: date, people: list[dict]) -> None:
    visit_id = 1000
    for person in people:
        count = person["overrides"].get("visits") or rng.choice([1, 2, 2, 3])
        visits = []
        for i in range(count):
            condition = person["conditions"][i % len(person["conditions"])]
            meta = CONDITIONS[condition]
            days_ago = rng.randint(0, 120)
            at = datetime.combine(today - timedelta(days=days_ago), datetime.min.time()) + timedelta(
                hours=rng.randint(7, 15), minutes=rng.choice([0, 10, 20, 30, 40, 50])
            )
            visit_id += 1
            labs = [
                {
                    "code": code, "text": text, "unit": unit, "ref": ref,
                    "value": (v := _lab_value(rng, rng_range)),
                    "flag": _flag(v, ref),
                    "at": at + timedelta(minutes=45),
                }
                for code, text, unit, ref, rng_range in meta["labs"]
            ]
            visits.append({
                "id": visit_id,
                "at": at,
                "condition": condition,
                "type": "IGD" if meta["poli"] == "IGD" else meta["type"],
                "poli": meta["poli"],
                "doctor": DOCTORS[meta["poli"]],
                "dx": None if rng.random() < 0.06 else meta["dx"],
                "labs": labs,
                "meds": meta["meds"],
            })
        person["visits"] = sorted(visits, key=lambda v: v["at"])


def _simrs_dob(rng: random.Random, person: dict) -> str:
    if "simrs_dob" in person["overrides"]:
        return person["overrides"]["simrs_dob"]
    if rng.random() < 0.2:
        return person["dob"].strftime("%d/%m/%Y")
    return person["dob"].isoformat()


def write_simrs(rng: random.Random, people: list[dict], stamp: str) -> None:
    conn = sqlite3.connect(SIMRS_DB)
    conn.executescript(
        """
        CREATE TABLE m_pasien (no_rm TEXT PRIMARY KEY, nama TEXT, nik TEXT, tgl_lahir TEXT, jk TEXT,
                               alamat TEXT, no_hp TEXT, updated_at TEXT);
        CREATE TABLE t_kunjungan (id_kunjungan INTEGER PRIMARY KEY, no_rm TEXT, tgl_masuk TEXT, jenis TEXT,
                                  poli TEXT, dokter TEXT, kd_diag TEXT, ket_diag TEXT, updated_at TEXT);
        """
    )
    rm = 0
    for person in people:
        rm += 1
        person["simrs_id"] = f"RM-{rm:05d}"
        ov = person["overrides"]
        if "simrs_nik" in ov:
            nik = ov["simrs_nik"]
        elif rng.random() < 0.18:
            nik = ""
        elif rng.random() < 0.04:
            nik = person["nik"][:15]
        else:
            nik = person["nik"]
        honorific = ""
        if rng.random() < 0.4:
            honorific = "Tn. " if person["sex"] == "L" else "Ny. "
        conn.execute(
            "INSERT INTO m_pasien VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (person["simrs_id"], ov.get("simrs_name") or honorific + person["name"], nik,
             _simrs_dob(rng, person), person["sex"], person["address"], person["phone"], stamp),
        )

    duplicate_ids = {}
    for person in people:
        if person["overrides"].get("simrs_duplicate"):
            rm += 1
            duplicate_ids[id(person)] = f"RM-{rm:05d}"
            conn.execute(
                "INSERT INTO m_pasien VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (duplicate_ids[id(person)], person["name"].upper(), "", person["dob"].isoformat(),
                 person["sex"], person["address"], person["phone"], stamp),
            )

    for person in people:
        for idx, visit in enumerate(person["visits"]):
            no_rm = person["simrs_id"]
            if id(person) in duplicate_ids and idx == len(person["visits"]) - 1:
                no_rm = duplicate_ids[id(person)]
            visit["simrs_id"] = no_rm
            dx_code, dx_text = visit["dx"] or ("", "")
            conn.execute(
                "INSERT INTO t_kunjungan VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (visit["id"], no_rm, visit["at"].isoformat(), visit["type"], visit["poli"],
                 visit["doctor"], dx_code, dx_text, stamp),
            )
    conn.commit()
    conn.close()


def hl7_message(control_id: str, lis_patient: dict, at: datetime, results: list[dict]) -> str:
    stamp = at.strftime("%Y%m%d%H%M%S")
    ids = f"{lis_patient['local_id']}^^^LIS^MR"
    if lis_patient.get("nik"):
        ids += f"~{lis_patient['nik']}^^^DUKCAPIL^NI"
    lines = [
        f"MSH|^~\\&|LIS|LAB-RSSS|SIMPUL|RSSS|{stamp}||ORU^R01|{control_id}|P|2.5",
        f"PID|1||{ids}||{lis_patient['hl7_name']}||{lis_patient['dob']}|{lis_patient['sex']}|||"
        f"{lis_patient['address']}||{lis_patient.get('phone', '')}",
        f"OBR|1||{control_id}|LAB^Pemeriksaan Laboratorium|||{stamp}",
    ]
    for i, res in enumerate(results, start=1):
        lines.append(
            f"OBX|{i}|NM|{res['code']}^{res['text']}^L||{res['value']}|{res['unit']}|"
            f"{res['ref']}|{res['flag']}|||F"
        )
    return "\r".join(lines) + "\r"


def write_lis(rng: random.Random, people: list[dict]) -> list[dict]:
    LIS_INBOX.mkdir(parents=True, exist_ok=True)
    lis_patients = []
    seq = 0
    msg = 0
    for person in people:
        lab_visits = [v for v in person["visits"] if v["labs"]]
        if not lab_visits:
            continue
        seq += 1
        ov = person["overrides"]
        parts = person["name"].upper().split()
        hl7_name = ov.get("lis_name") or f"{parts[-1]}^{' '.join(parts[:-1]) or parts[-1]}"
        dob = person["dob"].strftime("%Y%m%d")
        if "lis_dob" in ov:
            dob = ov["lis_dob"]
        elif person["dob"].day <= 12 and rng.random() < 0.05:
            dob = person["dob"].strftime("%Y%d%m")
        lis_patient = {
            "local_id": f"L-{seq:05d}",
            "hl7_name": hl7_name,
            "dob": dob,
            "sex": "F" if person["sex"] == "P" else "M",
            "nik": person["nik"] if rng.random() < 0.6 or "lis_name" in ov else "",
            "address": person["city_short"],
        }
        lis_patients.append(lis_patient)
        for visit in lab_visits:
            msg += 1
            results = [dict(r) for r in visit["labs"]]
            if rng.random() < 0.04:
                results[0]["unit"] = ""
            path = LIS_INBOX / f"ORU_{msg:06d}.hl7"
            path.write_text(hl7_message(f"LAB{msg:06d}", lis_patient, visit["labs"][0]["at"], results),
                            encoding="utf-8")
    return lis_patients


def write_farmasi(rng: random.Random, people: list[dict], today: date) -> list[dict]:
    FARMASI_DROP.mkdir(parents=True, exist_ok=True)
    rows = []
    farmasi_patients = []
    seq = 0
    resep = 5000
    for person in people:
        if rng.random() < 0.15 and person["name"] != "Siti Aminah":
            continue
        seq += 1
        local_id = f"F{seq:05d}"
        name = person["name"]
        if rng.random() < 0.08 and person["name"] != "Siti Aminah":
            name = _typo(rng, name)
        farmasi_patients.append({
            "local_id": local_id, "name": name, "dob": person["dob"].strftime("%d-%m-%Y"),
            "sex": person["sex"],
        })
        for visit in person["visits"]:
            resep += 1
            for med, rule, qty in visit["meds"]:
                rows.append({
                    "tgl_resep": (visit["at"] + timedelta(hours=1)).isoformat(),
                    "no_resep": f"R{resep}",
                    "no_rm_farmasi": local_id,
                    "nama_pasien": name,
                    "tgl_lahir": person["dob"].strftime("%d-%m-%Y"),
                    "jk": person["sex"],
                    "nama_obat": med,
                    "aturan_pakai": rule,
                    "jumlah": qty,
                })
    path = FARMASI_DROP / f"export_farmasi_{today.isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return farmasi_patients


def _billing_phone(rng: random.Random, phone: str) -> str:
    style = rng.random()
    if style < 0.3:
        return "+62 " + phone[1:4] + "-" + phone[4:8] + "-" + phone[8:]
    if style < 0.5:
        return "62" + phone[1:]
    return phone


def write_billing(rng: random.Random, people: list[dict], stamp: str) -> None:
    conn = sqlite3.connect(BILLING_DB)
    conn.executescript(
        """
        CREATE TABLE pasien (id_pasien TEXT PRIMARY KEY, nama_pasien TEXT, tgl_lahir TEXT, jenis_kelamin TEXT,
                             alamat TEXT, telp TEXT, updated_at TEXT);
        CREATE TABLE tagihan (id_tagihan INTEGER PRIMARY KEY, id_pasien TEXT, tanggal TEXT, uraian TEXT,
                              jumlah INTEGER, updated_at TEXT);
        """
    )
    seq = 0
    bill = 90000
    for person in people:
        if rng.random() < 0.1 and person["name"] != "Siti Aminah":
            continue
        seq += 1
        ov = person["overrides"]
        bid = f"B-{seq:05d}"
        name = ov.get("billing_name") or (person["name"].upper() if rng.random() < 0.5 else person["name"])
        if rng.random() < 0.06 and "billing_name" not in ov:
            name = _typo(rng, name)
        address = person["address"].replace("Jakarta Timur", "Jaktim") if rng.random() < 0.5 else person["address"]
        phone = ov.get("billing_phone") or _billing_phone(rng, person["phone"])
        if "billing_phone" not in ov and rng.random() < 0.12:
            # Patient changed phone number and the cashier typed the name differently.
            phone = _phone(rng)
            parts = person["name"].split()
            name = " ".join(parts[:-1] + [parts[-1][0] + "."])
        conn.execute(
            "INSERT INTO pasien VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bid, name, person["dob"].isoformat(), "Laki-laki" if person["sex"] == "L" else "Perempuan",
             address, phone, stamp),
        )
        for visit in person["visits"]:
            day = visit["at"] + timedelta(hours=2)
            items = [("Pendaftaran", 25000)]
            items.append(("Konsultasi dokter spesialis", 150000) if visit["poli"] not in ("Umum", "IGD")
                         else ("Konsultasi dokter umum", 75000))
            if visit["labs"]:
                items.append((f"Pemeriksaan laboratorium ({len(visit['labs'])} item)", 65000 * len(visit["labs"])))
            if visit["meds"]:
                items.append(("Obat-obatan", rng.randint(4, 30) * 5000))
            if visit["type"] == "RI":
                items.append(("Kamar rawat inap kelas 2 (3 malam)", 1050000))
            for item, amount in items:
                bill += 1
                conn.execute(
                    "INSERT INTO tagihan VALUES (?, ?, ?, ?, ?, ?)",
                    (bill, bid, day.isoformat(), item, amount, stamp),
                )
    conn.commit()
    conn.close()


def build_simulator(seed: int = 42) -> None:
    rng = random.Random(seed)
    today = date.today()
    stamp = datetime.now().replace(microsecond=0).isoformat()
    if SIM_DIR.exists():
        shutil.rmtree(SIM_DIR)
    SIM_DIR.mkdir(parents=True)

    people = build_people(rng, today)
    build_visits(rng, today, people)
    write_simrs(rng, people, stamp)
    lis_patients = write_lis(rng, people)
    farmasi_patients = write_farmasi(rng, people, today)
    write_billing(rng, people, stamp)

    state = {
        "lis_patients": lis_patients,
        "farmasi_patients": farmasi_patients,
        "next_lab_msg": 900000,
        "next_resep": 80000,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run(seed: int = 42) -> dict:
    with write_lock:
        connectors.OUTAGES.clear()
        reset_db()
        build_simulator(seed)
        register_sources()
        return {code: sync_source(code) for code in ("simrs", "lis", "farmasi", "billing")}


if __name__ == "__main__":
    for code, result in run().items():
        print(f"{code:8} {result['status']:7} {result['message']}")
