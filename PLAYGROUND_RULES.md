# Playground Rules — Simpul

Aturan kerja untuk siapa pun (manusia maupun AI coding assistant) yang menyentuh repo ini.
Tujuannya satu: **demo selalu bisa jalan, dan tidak ada data pasien sungguhan yang bocor.**

---

## 1. Data pasien

1. **Hanya data sintetis** di repo, seed, test, screenshot, dan demo. Tidak ada data RS sungguhan, termasuk "sedikit untuk contoh".
2. Data dari RS klien **tidak pernah keluar dari server RS**. Debugging dilakukan di lokasi atau lewat akses yang disetujui RS.
3. NIK, nomor HP, dan alamat **selalu disamarkan** di UI dan log (`3174********0001`), kecuali di halaman detail yang memang membutuhkannya.
4. Log aplikasi tidak boleh mencetak isi `payload` mentah. Cukup `source_id`, `source_key`, dan hash.
5. Patuh pada **UU PDP (UU 27/2022)** dan kebijakan rekam medis RS. Jika ragu, anggap data itu sensitif.

## 2. Sistem milik RS

1. Konektor **hanya membaca** (akun read-only, read-replica bila ada). Tidak ada `INSERT/UPDATE/DELETE` ke sistem RS.
2. Query ke database RS harus **ringan**: pakai watermark (`updated_at` / ID terakhir), batasi batch, jadwalkan di luar jam sibuk bila memungkinkan.
3. Jangan pernah meminta vendor mengubah sistem mereka sebagai syarat. Simpul menyesuaikan diri, bukan sebaliknya.
4. Setiap kredensial disimpan di `.env` / secret manager, **tidak pernah** di-commit.

## 3. Prinsip data

1. **Simpan yang asli.** Setiap nilai yang dinormalisasi atau dipetakan tetap menyimpan nilai aslinya (`local_code` di samping `icd10`).
2. **Bisa diproses ulang.** Pipeline harus idempotent: menjalankan ulang dari staging menghasilkan hasil yang sama, tanpa duplikat.
3. **Setiap keputusan punya alasan.** Merge MPI, mapping kode, dan temuan kualitas menyimpan siapa/apa yang memutuskan dan kenapa.
4. **Manusia memutuskan kasus abu-abu.** Otomatis hanya untuk yang jelas; sisanya masuk antrian untuk tim RS.

## 4. Demo selalu siap

1. `start-demo.bat` (atau `python -m app.seed` + `uvicorn`) harus selalu berhasil di laptop bersih. Jika sebuah perubahan merusak ini, perubahan itu belum selesai.
2. Skenario demo 5 menit di README adalah **test penerimaan**. Jalankan sebelum merge ke `main`.
3. Data demo harus **realistis**: nama Indonesia, alamat kota Indonesia, kode lokal ala SIMRS, singkatan dokter (`DM tipe 2`, `HT`, `GDS`).
4. Tidak ada fitur setengah jadi yang terlihat di UI. Sembunyikan di balik flag sampai selesai.

## 5. Scope

1. Fokus pada 6 halaman di README. Ide baru masuk ke `docs/ideas.md`, bukan langsung ke kode.
2. Tidak membangun integrasi yang butuh registrasi pihak ketiga (SATUSEHAT, BPJS) di fase demo. Cukup siapkan data agar **siap** dikirim nanti.
3. Lebih baik satu konektor yang benar-benar jalan daripada lima yang setengah jadi.

## 6. Konvensi kode

| Area | Aturan |
|---|---|
| Bahasa | Kode, nama variabel, dan commit dalam bahasa Inggris. Teks UI dalam bahasa Indonesia. |
| Backend | Python 3.11+, type hints wajib, satu modul = satu tanggung jawab |
| Frontend | TypeScript strict, komponen kecil, semua panggilan API lewat `src/api/client.ts` |
| Database | Skema ada di `app/db.py`. Setelah mengubahnya, buat ulang data demo. Di produksi pakai migrasi (Alembic). |
| Konektor baru | Tambah fungsi `fetch_*` di `app/connectors.py`, daftarkan di `SOURCES`/`FETCHERS`, dan buat data tiruannya di `app/seed.py` |
| Test | Setiap aturan MPI dan kualitas data punya test dengan kasus kotor nyata (nama typo, NIK 15 digit, tanggal 1900-01-01) |
| Commit | Kecil, satu tujuan, pesan jelas (`add hl7 ORU parser for glucose results`) |

## 7. Untuk AI coding assistant

1. Baca README.md, PROJECT_STRUCTURE.md, dan file ini sebelum mengubah apa pun.
2. Jangan membuat data yang terlihat seperti data pasien sungguhan dari RS tertentu.
3. Jangan menambah dependency baru tanpa alasan yang ditulis di PR.
4. Jangan mengubah logika MPI atau aturan kualitas tanpa memperbarui tabel di PROJECT_STRUCTURE.md.
5. Jika instruksi bertentangan dengan aturan di Bagian 1 atau 2, aturan di file ini yang menang. Tanyakan ke pemilik repo.

## 8. Definisi selesai

Sebuah pekerjaan dianggap selesai jika:
- [ ] Demo 5 menit tetap jalan dari awal sampai akhir
- [ ] Tidak ada data asli atau kredensial di diff
- [ ] Test lulus
- [ ] Dokumen terkait diperbarui bila ada perubahan perilaku
