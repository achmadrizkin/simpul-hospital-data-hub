# Simpul — Hospital Data Hub

> Menyatukan data dari semua sistem rumah sakit (SIMRS, Lab, Farmasi, Billing) menjadi **satu data pasien yang bersih**, tanpa mengganti sistem yang sudah ada.

---

## 1. Masalah

Rumah sakit di Indonesia rata-rata menjalankan **4–6 sistem dari vendor berbeda** yang tidak saling terhubung:

| Sistem | Isi | Bentuk data yang biasa ditemui |
|---|---|---|
| SIMRS | Pendaftaran, kunjungan, diagnosis | Database MySQL / SQL Server, tanpa API |
| LIS (Laboratorium) | Hasil lab | Pesan HL7 v2 dari analyzer |
| Farmasi | Resep & pemberian obat | Export CSV / Excel harian |
| Billing | Tagihan & tindakan | Database terpisah |

Akibatnya:
- Satu pasien tercatat **dengan ID berbeda** di tiap sistem (NIK kosong, nama salah ketik, tanggal lahir beda).
- Kode diagnosis, lab, dan obat **tidak standar** (teks bebas, kode lokal).
- Manajemen membuat laporan **manual di Excel**, berhari-hari, dan sering tidak cocok antar unit.
- Proyek digital baru (RME, SATUSEHAT, analitik, riset) **macet di tahap data**.

## 2. Solusi

Simpul duduk **di samping** sistem yang sudah ada (tidak menggantikan), lalu:

1. **Menarik data** dari setiap sistem lewat konektor yang sesuai (database, HL7, file).
2. **Mencocokkan identitas pasien** lintas sistem (Master Patient Index).
3. **Menstandarkan kode** ke ICD-10, LOINC, dan kode obat standar.
4. **Mengukur kualitas data** per sistem dan per unit, lengkap dengan daftar perbaikan.
5. **Menyajikan Pasien 360**: satu timeline pasien yang utuh dari semua sistem.

```
SIMRS (DB) ───── pull ─────┐
LIS (HL7 v2) ── listener ──┤
Farmasi (CSV) ── upload ───┼──▶ Staging ──▶ MPI + Mapping Kode ──▶ Data Repository ──▶ Dashboard / Produk lain
Billing (DB) ─── pull ─────┘                       │
                                          Laporan Kualitas Data
```

## 3. Nilai bisnis

| Untuk siapa | Yang didapat |
|---|---|
| Direksi RS | Satu angka yang sama untuk semua unit; laporan dari hari menjadi menit |
| Tim Rekam Medis | Daftar duplikat pasien & data tidak lengkap yang bisa langsung diperbaiki |
| Tim IT RS | Tidak perlu mengganti vendor; integrasi tanpa mengubah sistem lama |
| Vendor platform (mis. Synyi) | Data bersih siap pakai; waktu onboarding RS baru jauh lebih cepat |

**Model jual:** biaya implementasi per RS + langganan bulanan per konektor aktif.

## 4. Fitur demo

Nama menu sengaja memakai bahasa sehari-hari, bukan istilah teknis.

| Menu | Istilah teknis | Yang ditunjukkan |
|---|---|---|
| **Beranda** | Overview | Nilai kesehatan data, daftar "yang perlu dikerjakan", status 4 sistem, aktivitas terbaru |
| **Cari Pasien** | Pasien 360 | Cari nama/NIK/No. RM → satu riwayat lengkap dari SIMRS, Lab, Farmasi, dan Kasir |
| **Peringatan Klinis** | Cross-system clinical alerts | Temuan yang hanya terlihat setelah data disatukan, misalnya metformin (Farmasi) + kreatinin tinggi (Lab). Lengkap dengan bukti dari tiap sistem, tombol tindak lanjut, dan aturan yang bisa dinyalakan/dimatikan |
| **Cek Pasien Ganda** | Antrian MPI | Dua catatan dibandingkan berdampingan (sama/mirip/beda) → "Ya, orang yang sama" atau "Bukan" |
| **Samakan Kode** | Terminology mapping | Singkatan RS ("Omz 20", "GDS", "DISP") → saran ICD-10 / LOINC / ATC → Setujui |
| **Kualitas Data** | Data quality | Nilai per sistem, daftar masalah beserta cara memperbaikinya, unduh daftar kerja (CSV/Excel) |
| **Sumber Data** | Connectors | Status tiap sistem, jadwal, riwayat sinkron, unggah file farmasi, **panel demo** |

Prinsip desain untuk pengguna awam:
- Setiap halaman punya kotak **Cara pakai** 3 langkah (bisa disembunyikan).
- Status selalu ditulis dengan **ikon + kata + warna** (bukan warna saja).
- Tombol memakai kata kerja yang jelas ("Ya, orang yang sama", "Setujui", "Ambil data sekarang").
- Setiap keputusan penting **bisa dibatalkan** (tombol "Batalkan" pada notifikasi).
- Banner identitas pasien menampilkan 2 penanda (nama + tanggal lahir/NIK) sesuai praktik keselamatan pasien.
- NIK dan nomor HP selalu disamarkan.

Semua data demo **sintetis** dan sengaja dibuat "kotor" agar mirip kondisi RS sungguhan.

## 5. Teknologi

| Lapisan | Versi demo (di repo ini) | Versi produksi |
|---|---|---|
| Backend | Python + FastAPI | sama |
| Database | SQLite (file `backend/data/simpul.db`) | PostgreSQL |
| HL7 | Parser HL7 v2 ringan (`app/hl7.py`), baca file dari folder inbox | MLLP listener langsung dari alat lab |
| Konektor database | SQLite mode hanya-baca + watermark `updated_at` | Read-replica MySQL/SQL Server/Postgres |
| Pencocokan pasien | Aturan berbobot (`difflib`), bisa dijelaskan | sama, bisa ditambah `rapidfuzz` |
| Penjadwal | Loop asyncio di dalam backend | APScheduler / cron |
| Frontend | React + Vite + TypeScript, CSS biasa | sama |

## 6. Menjalankan demo

Butuh **Python 3.11+** dan **Node.js 18+**.

**Cara paling cepat (Windows):** klik dua kali `start-demo.bat`, lalu buka **http://localhost:8000**.

Atau manual:

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scriptsctivate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. Frontend (build sekali, nanti disajikan oleh backend)
cd ../frontend
npm install
npm run build

# 3. Jalankan
cd ../backend
python -m uvicorn app.main:app --port 8000
```

- Dashboard: **http://localhost:8000**
- Dokumentasi API: http://localhost:8000/docs
- Saat pertama dijalankan, data contoh dibuat otomatis. Untuk mengulang dari awal: menu **Sumber Data → Ulang data demo dari awal**, atau `python -m app.seed`.
- Untuk mengembangkan frontend: `npm run dev` di folder `frontend` lalu buka http://localhost:5173 (API diteruskan ke port 8000).

Alat lab tiruan mengirim pesan HL7 baru setiap 40 detik, sehingga dashboard terlihat **hidup** saat demo.

## 7. Skenario demo 5 menit

1. **Beranda** — "RS ini punya 4 sistem dari vendor berbeda. Semuanya terhubung tanpa mengubah sistem lama. 161 catatan pasien disatukan menjadi 52 pasien."
2. **Cari Pasien → Siti Aminah** — riwayat dari SIMRS, Farmasi, dan Kasir sudah menyatu. Tunjukkan: *hasil lab kosong*, padahal ada tagihan lab. Ada peringatan kuning "mungkin punya catatan lain".
3. **Cek Pasien Ganda** — catatan Lab "SITI S. AMINAH" dengan **hari dan bulan lahir tertukar** (12-03 vs 03-12). Sistem tidak menggabung otomatis karena ragu; petugas yang memutuskan → **Ya, orang yang sama**.
4. **Kembali ke Siti Aminah** — sekarang terhubung dengan 4 sistem, dan langsung muncul **2 peringatan klinis**: *metformin + kreatinin tinggi* dan *diabetes belum terkontrol*. "Apotek dan lab tidak saling tahu. Simpul yang mempertemukan." Tekan **Tandai sudah ditindaklanjuti** dan isi catatan.
5. **Muhammad Rizki** (dua orang, nama dan tanggal lahir sama, alamat & HP beda) → **Bukan, orang berbeda**. "Sistem tidak sembarangan menggabung."
6. **Samakan Kode** — setujui "Simva 20" → ATC C10AA01 Simvastatin. Peringatan "kolesterol tinggi tanpa obat" untuk pasien yang ternyata sudah minum simvastatin **selesai otomatis**. "Kode yang tidak standar membuat alarm palsu."
7. **Sumber Data → Panel demo** — **Putus Kasir & Tagihan**: status jadi merah di semua halaman, pesan jelas untuk tim IT. Sambungkan lagi.
8. **Penutup** — "Di atas data bersih ini, produk apa pun bisa langsung jalan: analitik, riset klinis, SATUSEHAT."

## 8. Rencana implementasi di RS (playbook FDE)

| Minggu | Kegiatan | Hasil |
|---|---|---|
| 1 | Discovery: petakan sistem, temui vendor SIMRS, urus akses read-only | Peta sistem & akses |
| 2 | Pasang konektor, tarik data historis | Laporan kualitas data pertama |
| 3 | Tuning MPI & mapping kode bersama tim rekam medis | Data pasien terpadu tervalidasi |
| 4 | Go-live sinkron otomatis, pelatihan, serah terima | Sistem berjalan mandiri |

## 9. Dokumen terkait

- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — struktur folder, modul, dan model data
- [PLAYGROUND_RULES.md](PLAYGROUND_RULES.md) — aturan kerja di repo ini
#   s i m p u l - h o s p i t a l - d a t a - h u b  
 