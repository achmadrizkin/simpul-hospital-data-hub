# Struktur Project — Simpul

## 1. Gambaran folder

```
ai-healthcare/
├── README.md
├── PROJECT_STRUCTURE.md
├── PLAYGROUND_RULES.md
├── start-demo.bat                  # Windows: install, build, dan jalankan dengan satu klik
│
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # entry FastAPI, scheduler, menyajikan frontend/dist
│   │   ├── api.py                  # semua endpoint /api/...
│   │   ├── db.py                   # skema SQLite, koneksi, kunci tulis
│   │   ├── connectors.py           # konektor hanya-baca: SIMRS (DB), Kasir (DB), Lab (HL7), Farmasi (CSV)
│   │   ├── hl7.py                  # pembaca pesan HL7 v2 ORU^R01
│   │   ├── pipeline.py             # sinkron: ambil → staging → normalisasi → MPI → mapping kode
│   │   ├── normalize.py            # rapikan nama, NIK, tanggal, HP, alamat; penyamaran NIK/HP
│   │   ├── mpi.py                  # pencocokan pasien, gabung, tolak, batalkan
│   │   ├── terminology.py          # saran kode standar untuk kode lokal
│   │   ├── reference.py            # katalog ICD-10 / LOINC / ATC (subset) + kamus awal RS
│   │   ├── quality.py              # aturan kualitas data dan perhitungan nilai
│   │   ├── alerts.py               # aturan peringatan klinis lintas sistem + evaluasi ke database
│   │   ├── live.py                 # penjadwal sinkron + alat lab tiruan + contoh file farmasi
│   │   └── seed.py                 # membuat 4 sistem RS tiruan berisi data kotor sintetis
│   ├── data/                       # (dibuat otomatis) simpul.db
│   └── simulator/                  # (dibuat otomatis) sistem RS tiruan
│       ├── simrs.db                # tabel m_pasien, t_kunjungan ala SIMRS lokal
│       ├── billing.db              # tabel pasien, tagihan ala aplikasi kasir
│       ├── lis_inbox/*.hl7         # pesan HL7 dari alat lab (diproses → processed/)
│       ├── farmasi_drop/*.csv      # ekspor resep harian (diproses → processed/)
│       └── state.json              # penghitung untuk simulator
│
└── frontend/
    ├── package.json
    ├── vite.config.ts              # dev server :5173, /api diteruskan ke :8000
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx                 # kerangka: menu samping, bar atas, routing
        ├── styles.css              # seluruh tampilan (token warna, komponen, responsif)
        ├── lib/
        │   ├── api.ts              # tipe data + pemanggil API
        │   ├── format.ts           # tanggal Indonesia, Rupiah, "5 menit lalu"
        │   ├── hooks.ts            # useData (muat + refresh), useStoredFlag
        │   └── router.ts           # routing berbasis #hash
        ├── components/ui.tsx       # tombol, status, badge sistem, modal, notifikasi, "Cara pakai"
        └── pages/
            ├── Beranda.tsx         # Ringkasan
            ├── PasienList.tsx      # Cari Pasien
            ├── PasienDetail.tsx    # Pasien 360 (riwayat lengkap)
            ├── Peringatan.tsx      # Peringatan klinis lintas sistem
            ├── CekGanda.tsx        # Antrian MPI
            ├── SamakanKode.tsx     # Mapping kode
            ├── Kualitas.tsx        # Kualitas data
            └── SumberData.tsx      # Konektor + panel demo
```

## 2. Alur data

```
[Sistem RS] ──konektor (hanya-baca)──▶ staging_records ──normalize──▶ source_patients ──MPI──▶ patients
                                              │
                                              ├──▶ events (kunjungan, diagnosis, lab, obat, tagihan)
                                              │        └──terminology──▶ code_mappings
                                              │
                                              └── quality (dihitung saat dibuka) ──▶ daftar masalah
```

1. **Konektor** hanya membaca. Database dibuka dengan mode `ro`, jadi secara teknis tidak bisa menulis.
2. **Staging** menyimpan data apa adanya beserta hash. Data yang tidak berubah tidak diproses ulang.
3. **Normalize** menyimpan nilai asli (`raw_name`, `raw_birth_date`, `raw_nik`) di samping nilai yang dirapikan.
4. **MPI** memberi setiap orang satu ID Simpul (`SPL-000001`).
5. **Kode standar** tidak ditulis ke `events`. Kode dicari lewat `code_mappings` saat ditampilkan, jadi satu persetujuan langsung berlaku untuk semua data lama dan baru.
6. **Kualitas** dihitung ulang setiap kali dibuka, sehingga perbaikan langsung terlihat.

## 3. Model data inti

| Tabel | Isi | Kolom penting |
|---|---|---|
| `sources` | Sistem RS yang terhubung | `code`, `method`, `interval_min`, `watermark`, `last_sync_at`, `last_status` |
| `sync_runs` | Log tiap sinkron | `source_code`, `records_in`, `records_new`, `status`, `message` |
| `staging_records` | Data mentah | `source_code`, `record_type`, `source_key`, `payload` (JSON), `hash`, `processed` |
| `source_patients` | Pasien versi tiap sistem | `local_id`, `raw_*` + nilai rapi, `golden_id`, `linked_by` (otomatis/petugas/baru) |
| `patients` | Pasien terpadu | `id`, `merged_into` (untuk pembatalan) |
| `mpi_candidates` | Pasangan yang perlu dicek manusia | `sp_a`, `sp_b`, `score`, `reasons` (JSON), `status`, `undo_info` |
| `events` | Kunjungan, diagnosis, lab, obat, tagihan | `local_patient_id`, `kind`, `occurred_at`, `code_system`, `local_code`, `value`, `flag`, `amount` |
| `code_mappings` | Kamus kode lokal → standar | `system` (dx/lab/obat), `local_code`, `std_code`, `status` (confirmed/suggested/unmapped) |
| `alert_rules` | Aturan peringatan klinis | `code`, `title`, `severity`, `sources`, `enabled` |
| `clinical_alerts` | Peringatan per pasien | `golden_id`, `rule_code`, `detail`, `evidence` (JSON: event + sistem asal), `status` (open/handled/resolved), `handled_by`, `note` |

## 4. Logika pencocokan pasien

1. **NIK valid sama** → pasti orang yang sama. **NIK valid beda** → pasti orang berbeda.
2. Selain itu, skor berbobot dari data yang tersedia di kedua sisi:

| Sinyal | Bobot | Catatan |
|---|---|---|
| Tanggal lahir | 0.35 | Hari & bulan tertukar diberi nilai 0.6; tanggal tidak masuk akal diabaikan |
| Nama | 0.30 | Gelar/sapaan (Tn., Ny., Hj., dr.) dibuang; urutan kata tidak berpengaruh |
| Nomor HP | 0.15 | Format +62 / 62 / 08 disamakan |
| Jenis kelamin | 0.10 | L/P, M/F, Laki-laki/Perempuan disamakan |
| Alamat | 0.10 | Singkatan kota (Jaktim, Jaksel, ...) dikembangkan |

Skor dibagi total bobot data yang tersedia.

| Skor | Tindakan |
|---|---|
| ≥ 0.90 | Digabung otomatis, **hanya jika** tanggal lahir sama persis dan nama ≥ 85% mirip |
| 0.70 – 0.89 | Masuk **Cek Pasien Ganda** untuk diputuskan petugas |
| < 0.70 | Dianggap orang berbeda |

Setiap keputusan menyimpan alasan per kolom (sama / mirip / beda / tidak ada data), dan bisa dibatalkan.

## 5. Aturan kualitas data

| Kode aturan | Cek | Tingkat |
|---|---|---|
| `TGL_LAHIR_BERMASALAH` | Kosong, format tidak dikenal, di masa depan, atau umur > 120 tahun | Penting |
| `KUNJUNGAN_TANPA_DIAGNOSIS` | Kunjungan tanpa diagnosis | Penting |
| `NIK_KOSONG` | NIK kosong (hanya untuk sistem yang punya kolom NIK) | Sedang |
| `NIK_TIDAK_VALID` | NIK bukan 16 digit | Sedang |
| `PASIEN_GANDA_BELUM_DICEK` | Kandidat pasien ganda belum diputuskan | Sedang |
| `KODE_BELUM_STANDAR` | Kode lokal belum disetujui padanannya | Sedang |
| `SATUAN_LAB_KOSONG` | Hasil lab tanpa satuan | Ringan |

Nilai kualitas = persentase data yang tidak punya masalah apa pun.

## 6. Peringatan klinis lintas sistem

Setiap aturan butuh data dari **minimal dua sistem**, sehingga hanya bisa muncul setelah pasien disatukan.
Aturan membaca kode standar (ATC, LOINC, ICD-10) lewat `code_mappings` yang sudah disetujui.

| Aturan | Sistem | Kondisi |
|---|---|---|
| `METFORMIN_GINJAL` | Farmasi + Lab | Metformin dalam 180 hari + kreatinin terakhir > 1,3 mg/dL |
| `TROMBOSIT_RENDAH_TANPA_TINDAK_LANJUT` | Lab + SIMRS | Trombosit < 100 tanpa kunjungan IGD/rawat inap sesudahnya |
| `DIABETES_TIDAK_TERKONTROL` | SIMRS + Lab | Diagnosis E11 + HbA1c ≥ 7% atau GDS ≥ 200 |
| `KOLESTEROL_TANPA_OBAT` | Lab + Farmasi | Kolesterol ≥ 240 tanpa statin dalam 120 hari |

Evaluasi ulang (`alerts.evaluate`) berjalan otomatis setelah: sinkron data baru, gabung/batal gabung pasien,
persetujuan atau perubahan kode, dan menyalakan/mematikan aturan.
- Kondisi baru terpenuhi → baris baru `open`.
- Kondisi tidak terpenuhi lagi → `resolved` (selesai otomatis).
- Petugas menindaklanjuti → `handled`, beserta nama dan catatan.

Ini contoh aturan untuk demo, bukan alat bantu keputusan klinis.

## 7. Endpoint API

| Method | Path | Fungsi |
|---|---|---|
| GET | `/api/overview` | Ringkasan beranda |
| GET | `/api/sources` | Status konektor + riwayat sinkron |
| POST | `/api/sources/{code}/sync` | Ambil data sekarang |
| POST | `/api/sources/farmasi/upload` | Unggah CSV farmasi (kolom divalidasi) |
| GET | `/api/patients?q=` | Cari pasien (nama, NIK, No. RM, ID Simpul) |
| GET | `/api/patients/{id}` | Pasien 360: identitas, ringkasan, riwayat, catatan per sistem, masalah |
| GET | `/api/mpi/candidates?status=pending\|decided` | Antrian pasien ganda |
| POST | `/api/mpi/candidates/{id}/merge` · `/reject` · `/undo` | Putuskan / batalkan |
| GET | `/api/mappings?status=todo\|done` | Kode lokal + saran |
| GET | `/api/mappings/catalog?system=&q=` | Cari kode standar |
| POST | `/api/mappings/{id}/confirm` · `/reset` | Setujui / ubah |
| GET | `/api/quality` | Nilai per sistem & per aturan |
| GET | `/api/quality/issues?rule=` · `/issues.csv` | Daftar masalah / unduh |
| GET | `/api/alerts?status=open\|handled\|resolved` | Daftar peringatan klinis |
| POST | `/api/alerts/{id}/handle` · `/reopen` | Tindak lanjuti (dengan catatan) / buka lagi |
| GET | `/api/alerts/rules` · POST `/api/alerts/rules/{code}` | Daftar aturan / nyalakan-matikan |
| POST | `/api/demo/lab-message` | Alat lab tiruan mengirim 1 hasil |
| POST | `/api/demo/live` | Hidupkan/matikan pengiriman otomatis |
| POST | `/api/sources/{code}/outage` | Simulasi koneksi putus |
| POST | `/api/demo/reset` | Buat ulang data contoh |

## 8. Dari demo ke produksi

| Bagian | Demo | Produksi |
|---|---|---|
| Database Simpul | SQLite | PostgreSQL |
| Konektor SIMRS/Kasir | File SQLite tiruan | Read-replica database vendor, akun hanya-baca |
| Lab | File `.hl7` di folder | MLLP listener (port 2575) |
| Farmasi | Folder CSV + unggah | Folder bersama / SFTP |
| Login | Satu pengguna tetap | SSO RS + peran (rekam medis, IT, direksi) + log audit |
| Deploy | `start-demo.bat` | Docker di server RS (on-premise) |
