"""Data quality rules. Every finding says what is wrong, why it matters, and how to fix it."""

import sqlite3
from collections import defaultdict

from .normalize import birth_date_problem, mask_nik

RULES = {
    "TGL_LAHIR_BERMASALAH": {
        "label": "Tanggal lahir bermasalah",
        "severity": "tinggi",
        "why": "Tanggal lahir dipakai untuk mencocokkan pasien dan menghitung dosis obat anak.",
        "fix": "Cocokkan dengan KTP/KK pasien, lalu perbaiki di sistem asal.",
    },
    "KUNJUNGAN_TANPA_DIAGNOSIS": {
        "label": "Kunjungan tanpa diagnosis",
        "severity": "tinggi",
        "why": "Kunjungan tanpa diagnosis tidak bisa diklaim dan tidak masuk laporan penyakit.",
        "fix": "Minta dokter penanggung jawab melengkapi diagnosis di SIMRS.",
    },
    "NIK_KOSONG": {
        "label": "NIK pasien kosong",
        "severity": "sedang",
        "why": "Tanpa NIK, pasien sulit dicocokkan antar sistem dan tidak bisa dilaporkan ke SATUSEHAT.",
        "fix": "Minta petugas pendaftaran melengkapi NIK saat pasien datang berikutnya.",
    },
    "NIK_TIDAK_VALID": {
        "label": "NIK tidak 16 digit",
        "severity": "sedang",
        "why": "NIK yang salah membuat pasien tercatat sebagai orang lain.",
        "fix": "Periksa ulang NIK dari KTP/KK pasien.",
    },
    "PASIEN_GANDA_BELUM_DICEK": {
        "label": "Kemungkinan pasien ganda belum dicek",
        "severity": "sedang",
        "why": "Riwayat pasien terpecah di beberapa catatan sehingga dokter tidak melihat gambaran lengkap.",
        "fix": "Buka menu Cek Pasien Ganda dan putuskan satu per satu.",
    },
    "KODE_BELUM_STANDAR": {
        "label": "Kode belum disamakan ke standar",
        "severity": "sedang",
        "why": "Kode lokal tidak bisa dibandingkan antar sistem atau dilaporkan ke luar RS.",
        "fix": "Buka menu Samakan Kode dan setujui saran yang sesuai.",
    },
    "SATUAN_LAB_KOSONG": {
        "label": "Hasil lab tanpa satuan",
        "severity": "rendah",
        "why": "Angka tanpa satuan bisa disalahartikan (mg/dL atau mmol/L).",
        "fix": "Periksa pengaturan satuan di alat lab atau LIS.",
    },
}

SEVERITY_ORDER = {"tinggi": 0, "sedang": 1, "rendah": 2}


def collect_issues(conn: sqlite3.Connection) -> list[dict]:
    issues: list[dict] = []
    has_nik = {r["code"]: r["has_nik"] for r in conn.execute("SELECT code, has_nik FROM sources")}

    def add(rule: str, source: str, ref: str, patient: str | None, detail: str, golden_id=None) -> None:
        issues.append({
            "rule": rule,
            "source": source,
            "ref": ref,
            "patient": patient,
            "detail": detail,
            "golden_id": golden_id,
        })

    for sp in conn.execute("SELECT * FROM source_patients"):
        problem = birth_date_problem(sp["birth_date"])
        if problem:
            add("TGL_LAHIR_BERMASALAH", sp["source_code"], sp["local_id"], sp["raw_name"],
                f"Tertulis \"{sp['raw_birth_date'] or '(kosong)'}\": {problem}", sp["golden_id"])
        if has_nik.get(sp["source_code"]):
            if not sp["nik"]:
                add("NIK_KOSONG", sp["source_code"], sp["local_id"], sp["raw_name"],
                    "NIK belum diisi", sp["golden_id"])
            elif len(sp["nik"]) != 16:
                add("NIK_TIDAK_VALID", sp["source_code"], sp["local_id"], sp["raw_name"],
                    f"NIK {mask_nik(sp['nik'])} hanya {len(sp['nik'])} digit", sp["golden_id"])

    name_of = {
        (r["source_code"], r["local_id"]): (r["raw_name"], r["golden_id"])
        for r in conn.execute("SELECT source_code, local_id, raw_name, golden_id FROM source_patients")
    }

    for ev in conn.execute(
        """
        SELECT e.*, m.status AS map_status FROM events e
        LEFT JOIN code_mappings m ON m.system = e.code_system AND m.local_code = e.local_code
        WHERE e.code_system IS NOT NULL AND (m.status IS NULL OR m.status != 'confirmed')
        """
    ):
        name, gid = name_of.get((ev["source_code"], ev["local_patient_id"]), (None, None))
        add("KODE_BELUM_STANDAR", ev["source_code"], ev["source_key"], name,
            f"Kode \"{ev['local_code']}\" belum disamakan", gid)

    for ev in conn.execute(
        """
        SELECT v.* FROM events v
        WHERE v.kind = 'visit' AND NOT EXISTS (
            SELECT 1 FROM events d
            WHERE d.kind = 'diagnosis' AND d.source_code = v.source_code AND d.visit_key = v.visit_key
        )
        """
    ):
        name, gid = name_of.get((ev["source_code"], ev["local_patient_id"]), (None, None))
        add("KUNJUNGAN_TANPA_DIAGNOSIS", ev["source_code"], ev["source_key"], name,
            f"{ev['title']} pada {ev['occurred_at'][:10]}", gid)

    for ev in conn.execute(
        "SELECT * FROM events WHERE kind = 'lab' AND (unit IS NULL OR unit = '')"
    ):
        name, gid = name_of.get((ev["source_code"], ev["local_patient_id"]), (None, None))
        add("SATUAN_LAB_KOSONG", ev["source_code"], ev["source_key"], name,
            f"{ev['title']}: {ev['value']} (tanpa satuan)", gid)

    for cand in conn.execute(
        """
        SELECT c.id, b.source_code, b.local_id, b.raw_name, b.golden_id, c.score
        FROM mpi_candidates c JOIN source_patients b ON b.id = c.sp_b
        WHERE c.status = 'pending'
        """
    ):
        add("PASIEN_GANDA_BELUM_DICEK", cand["source_code"], cand["local_id"], cand["raw_name"],
            f"Kemiripan {round(cand['score'] * 100)}% dengan pasien lain", cand["golden_id"])

    return issues


def report(conn: sqlite3.Connection) -> dict:
    issues = collect_issues(conn)
    sources = conn.execute("SELECT code, name FROM sources ORDER BY rowid").fetchall()

    records = defaultdict(int)
    for r in conn.execute("SELECT source_code, COUNT(*) n FROM source_patients GROUP BY source_code"):
        records[r["source_code"]] += r["n"]
    for r in conn.execute("SELECT source_code, COUNT(*) n FROM events GROUP BY source_code"):
        records[r["source_code"]] += r["n"]

    bad = defaultdict(set)
    by_rule = defaultdict(int)
    by_source_rule = defaultdict(lambda: defaultdict(int))
    for issue in issues:
        bad[issue["source"]].add(issue["ref"])
        by_rule[issue["rule"]] += 1
        by_source_rule[issue["source"]][issue["rule"]] += 1

    def score(total: int, problems: int) -> int:
        return 100 if total == 0 else round(100 * (1 - problems / total))

    total_records = sum(records.values())
    total_bad = sum(len(v) for v in bad.values())

    rules = [
        {"rule": code, **meta, "count": by_rule.get(code, 0)}
        for code, meta in RULES.items()
    ]
    rules.sort(key=lambda r: (r["count"] == 0, SEVERITY_ORDER[r["severity"]], -r["count"]))

    return {
        "score": score(total_records, total_bad),
        "records": total_records,
        "records_with_issues": total_bad,
        "issues": len(issues),
        "sources": [
            {
                "code": s["code"],
                "name": s["name"],
                "records": records[s["code"]],
                "records_with_issues": len(bad[s["code"]]),
                "score": score(records[s["code"]], len(bad[s["code"]])),
                "top_rules": sorted(
                    ({"rule": k, "label": RULES[k]["label"], "count": v}
                     for k, v in by_source_rule[s["code"]].items()),
                    key=lambda x: -x["count"],
                )[:3],
            }
            for s in sources
        ],
        "rules": rules,
    }
