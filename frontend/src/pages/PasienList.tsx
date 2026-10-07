import { AlertTriangle, ChevronRight, Search, SearchX } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate, sexLabel, timeAgo } from "../lib/format";
import { useData } from "../lib/hooks";
import { EmptyState, ErrorBox, HowTo, Loading, PageHeader, SourceBadge } from "../components/ui";

export function PasienList() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const t = window.setTimeout(() => setQuery(input.trim()), 300);
    return () => window.clearTimeout(t);
  }, [input]);

  const { data, error, loading, reload } = useData(() => api.patients(query), [query]);

  return (
    <>
      <PageHeader
        title="Cari Pasien"
        subtitle="Lihat riwayat lengkap satu pasien dari semua sistem dalam satu layar."
      />
      <HowTo
        id="pasien"
        steps={[
          <>Ketik <strong>nama</strong>, <strong>NIK</strong>, atau <strong>nomor rekam medis</strong> pasien.</>,
          <>Klik nama pasien untuk membuka riwayatnya.</>,
          <>Tanda <AlertTriangle size={14} className="inline-icon tone-text-warn" /> berarti pasien ini mungkin punya catatan ganda yang perlu dicek.</>,
        ]}
      />

      <div className="search-box">
        <Search size={22} aria-hidden />
        <input
          id="patient-search"
          type="search"
          autoFocus
          placeholder="Ketik nama, NIK, atau nomor rekam medis…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          aria-label="Cari pasien"
        />
      </div>
      <p className="muted small search-hint">
        Contoh: <button className="link" onClick={() => setInput("Siti Aminah")}>Siti Aminah</button>,{" "}
        <button className="link" onClick={() => setInput("RM-00004")}>RM-00004</button>,{" "}
        <button className="link" onClick={() => setInput("Rizki")}>Rizki</button>
      </p>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && (
        <>
          <h2 className="section-title">
            {data.query ? `Hasil pencarian "${data.query}" (${data.results.length})` : "Pasien dengan aktivitas terbaru"}
          </h2>
          {data.results.length === 0 ? (
            <EmptyState icon={SearchX} title="Pasien tidak ditemukan">
              Periksa ejaan nama, atau coba cari dengan NIK atau nomor rekam medis.
            </EmptyState>
          ) : (
            <div className="patient-list" role="list">
              {data.results.map((p) => (
                <a key={p.id} className="patient-row" href={`#/pasien/${p.id}`} role="listitem">
                  <span className={`avatar sex-${p.sex ?? "x"}`} aria-hidden>
                    {p.name.split(" ").slice(0, 2).map((n) => n[0]).join("")}
                  </span>
                  <span className="patient-row-main">
                    <strong className="patient-name">
                      {p.name}
                      {p.pending_duplicates > 0 && (
                        <span className="pill tone-warn" title="Mungkin punya catatan ganda">
                          <AlertTriangle size={13} aria-hidden /> Cek ganda
                        </span>
                      )}
                    </strong>
                    <span className="muted">
                      {sexLabel(p.sex)} · {p.age !== null ? `${p.age} tahun` : "umur tidak diketahui"} · Lahir{" "}
                      {formatDate(p.birth_date)} · NIK {p.nik ?? <em>belum ada</em>}
                    </span>
                    <span className="badge-row">
                      {p.sources.map((s) => (
                        <SourceBadge key={s} name={s} small />
                      ))}
                    </span>
                  </span>
                  <span className="patient-row-side">
                    <span className="mono small">{p.label}</span>
                    <span className="muted small">Aktivitas {timeAgo(p.last_activity)}</span>
                  </span>
                  <ChevronRight size={20} className="row-chevron" aria-hidden />
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
