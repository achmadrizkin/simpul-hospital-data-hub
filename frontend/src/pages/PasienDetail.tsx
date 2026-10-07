import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  CalendarClock,
  FlaskConical,
  Hospital,
  Link2,
  Pill,
  Receipt,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type EventKind, type TimelineItem } from "../lib/api";
import { dayKey, formatDate, formatDateLong, formatRupiah, formatTime, sexLabel } from "../lib/format";
import { useData } from "../lib/hooks";
import { go } from "../lib/router";
import { Card, ErrorBox, Loading, Notice, SeverityPill, SourceBadge, Term } from "../components/ui";
import { AlertCard } from "./Peringatan";

const KIND_META: Record<EventKind, { icon: LucideIcon; label: string }> = {
  visit: { icon: Hospital, label: "Kunjungan" },
  diagnosis: { icon: Stethoscope, label: "Diagnosis" },
  lab: { icon: FlaskConical, label: "Hasil lab" },
  medication: { icon: Pill, label: "Obat" },
  charge: { icon: Receipt, label: "Tagihan" },
};

const FILTERS: { key: "all" | EventKind; label: string }[] = [
  { key: "all", label: "Semua" },
  { key: "visit", label: "Kunjungan" },
  { key: "diagnosis", label: "Diagnosis" },
  { key: "lab", label: "Hasil lab" },
  { key: "medication", label: "Obat" },
  { key: "charge", label: "Tagihan" },
];

function LabFlag({ flag }: { flag: string | null }) {
  if (flag === "H")
    return (
      <span className="flag tone-text-bad">
        <ArrowUp size={14} aria-hidden /> Tinggi
      </span>
    );
  if (flag === "L")
    return (
      <span className="flag tone-text-info">
        <ArrowDown size={14} aria-hidden /> Rendah
      </span>
    );
  return <span className="flag tone-text-good">Normal</span>;
}

const LINK_LABEL: Record<string, string> = {
  otomatis: "Dicocokkan otomatis",
  petugas: "Digabung oleh petugas",
  baru: "Catatan pertama",
};

function TimelineEntry({ item }: { item: TimelineItem }) {
  const meta = KIND_META[item.kind];
  const Icon = meta.icon;
  return (
    <li className={`tl-item kind-${item.kind}`}>
      <span className="tl-icon">
        <Icon size={16} aria-hidden />
      </span>
      <div className="tl-body">
        <div className="tl-head">
          <span className="tl-kind">{meta.label}</span>
          <span className="tl-time">{formatTime(item.occurred_at)}</span>
          <SourceBadge code={item.source} small />
        </div>
        <div className="tl-title">
          {item.kind === "lab" ? (
            <>
              {item.title}:{" "}
              <strong className="lab-value">
                {item.value} {item.unit || <em className="tone-text-warn">(satuan kosong)</em>}
              </strong>{" "}
              <LabFlag flag={item.flag} />
              {item.ref_range && <span className="muted small"> · normal {item.ref_range}</span>}
            </>
          ) : item.kind === "charge" ? (
            <>
              {item.title} <strong className="num">{formatRupiah(item.amount ?? 0)}</strong>
            </>
          ) : (
            <>
              {item.std_text ?? item.title}
              {item.detail && <span className="muted"> · {item.detail}</span>}
            </>
          )}
        </div>
        {item.local_code && (
          <div className="tl-codes">
            <span className="code-chip local" title="Kode yang tertulis di sistem asal">
              {item.local_code}
            </span>
            {item.std_code ? (
              <span className="code-chip std" title={`Kode standar ${item.std_system}`}>
                {item.std_system} {item.std_code}
              </span>
            ) : (
              <a className="code-chip missing" href="#/kode">
                Belum disamakan
              </a>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

export function PasienDetail({ id }: { id: number }) {
  const { data, error, loading, reload } = useData(() => api.patient(id), [id]);
  const [filter, setFilter] = useState<"all" | EventKind>("all");

  useEffect(() => {
    if (data?.redirect_to) go(`/pasien/${data.redirect_to}`);
  }, [data]);

  const groups = useMemo(() => {
    if (!data?.timeline) return [];
    const items = data.timeline.filter((t) => filter === "all" || t.kind === filter);
    const map = new Map<string, TimelineItem[]>();
    for (const item of items) {
      const key = dayKey(item.occurred_at);
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return [...map.entries()];
  }, [data, filter]);

  if (loading && !data) return <Loading label="Membuka riwayat pasien…" />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;
  if (!data || data.redirect_to) return null;

  const p = data.identity;
  const s = data.summary;

  return (
    <>
      <a className="back-link" href="#/pasien">
        <ArrowLeft size={16} aria-hidden /> Kembali ke pencarian
      </a>

      <section className="patient-banner" aria-label="Identitas pasien">
        <span className={`avatar large sex-${p.sex ?? "x"}`} aria-hidden>
          {p.name.split(" ").slice(0, 2).map((n) => n[0]).join("")}
        </span>
        <div className="patient-banner-main">
          <h1>{p.name}</h1>
          <div className="identity-row">
            <span>
              <small>Jenis kelamin</small>
              {sexLabel(p.sex)}
            </span>
            <span>
              <small>Tanggal lahir</small>
              {formatDate(p.birth_date)} {p.age !== null && <em>({p.age} th)</em>}
            </span>
            <span>
              <small>NIK</small>
              {p.nik ?? <em className="tone-text-warn">Belum ada</em>}
            </span>
            <span>
              <small>
                <Term explain="Nomor pasien di Simpul. Satu nomor untuk satu orang, apa pun nomornya di tiap sistem.">ID Simpul</Term>
              </small>
              <span className="mono">{data.label}</span>
            </span>
          </div>
          {p.address && <div className="muted small">{p.address}</div>}
        </div>
        <div className="patient-banner-side">
          <span className="linked-count">
            <Link2 size={16} aria-hidden /> Terhubung dengan {new Set(data.records.map((r) => r.source)).size} sistem
          </span>
          <span className="badge-row">
            {[...new Set(data.records.map((r) => r.source))].map((code) => (
              <SourceBadge key={code} code={code} small />
            ))}
          </span>
        </div>
      </section>

      {data.alerts.length > 0 && (
        <section className="patient-alerts" aria-label="Peringatan klinis">
          {data.alerts.map((a) => (
            <AlertCard key={a.id} alert={a} compact onChanged={reload} />
          ))}
        </section>
      )}

      {data.pending_duplicates.length > 0 && (
        <Notice tone="warn">
          <strong>Pasien ini mungkin punya catatan lain yang belum digabung.</strong> Riwayat di bawah bisa jadi belum
          lengkap. <a href="#/ganda">Cek pasien ganda</a>
        </Notice>
      )}

      <div className="patient-layout">
        <div className="patient-side">
          <Card>
            <h2 className="card-title">Ringkasan</h2>
            <dl className="facts single">
              <div>
                <dt>Jumlah kunjungan</dt>
                <dd>
                  {s.visits} kali{s.last_visit && <span className="muted">, terakhir {formatDate(s.last_visit)}</span>}
                </dd>
              </div>
              <div>
                <dt>Total tagihan</dt>
                <dd>{formatRupiah(s.total_charges)}</dd>
              </div>
            </dl>
          </Card>

          <Card>
            <h2 className="card-title">
              <Stethoscope size={18} aria-hidden /> Diagnosis
            </h2>
            {s.diagnoses.length === 0 ? (
              <p className="muted">Belum ada diagnosis.</p>
            ) : (
              <ul className="summary-list">
                {s.diagnoses.map((d) => (
                  <li key={d.local_code}>
                    <span>{d.text}</span>
                    {d.code ? (
                      <span className="code-chip std">ICD-10 {d.code}</span>
                    ) : (
                      <span className="code-chip missing">{d.local_code}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <h2 className="card-title">
              <FlaskConical size={18} aria-hidden /> Hasil lab terakhir
            </h2>
            {s.latest_labs.length === 0 ? (
              <p className="muted">Belum ada hasil lab.</p>
            ) : (
              <table className="table compact">
                <tbody>
                  {s.latest_labs.map((l) => (
                    <tr key={l.id}>
                      <td>
                        {l.title}
                        <div className="muted small">{formatDate(l.occurred_at)}</div>
                      </td>
                      <td className="num">
                        <strong>{l.value}</strong> <span className="muted small">{l.unit}</span>
                      </td>
                      <td>
                        <LabFlag flag={l.flag} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card>
            <h2 className="card-title">
              <Pill size={18} aria-hidden /> Obat 3 bulan terakhir
            </h2>
            {s.medications.length === 0 ? (
              <p className="muted">Tidak ada obat dalam 3 bulan terakhir.</p>
            ) : (
              <ul className="summary-list">
                {s.medications.map((m) => (
                  <li key={m.id}>
                    <span>
                      {m.std_text ?? m.title}
                      <div className="muted small">{m.detail}</div>
                    </span>
                    <span className="muted small">{formatDate(m.occurred_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="patient-main">
          <Card>
            <div className="timeline-head">
              <h2 className="card-title">
                <CalendarClock size={18} aria-hidden /> Riwayat lengkap
              </h2>
              <div className="chips" role="tablist" aria-label="Saring riwayat">
                {FILTERS.map((f) => (
                  <button
                    key={f.key}
                    role="tab"
                    aria-selected={filter === f.key}
                    className={`chip ${filter === f.key ? "active" : ""}`}
                    onClick={() => setFilter(f.key)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            <p className="muted small">
              Data dari {data.records.length} catatan di sistem berbeda, disusun berdasarkan waktu. Terbaru di atas.
            </p>
            {groups.length === 0 ? (
              <p className="muted">Tidak ada data untuk pilihan ini.</p>
            ) : (
              groups.map(([day, items]) => (
                <div key={day} className="tl-day">
                  <h3 className="tl-date">{formatDateLong(day)}</h3>
                  <ul className="timeline">
                    {items.map((item) => (
                      <TimelineEntry key={item.id} item={item} />
                    ))}
                  </ul>
                </div>
              ))
            )}
          </Card>

          <Card>
            <h2 className="card-title">
              <Link2 size={18} aria-hidden /> Catatan pasien ini di tiap sistem
            </h2>
            <p className="muted small">
              Setiap sistem mencatat pasien dengan nomor dan penulisan yang berbeda. Simpul menyatukannya.
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Sistem</th>
                    <th>Nomor di sistem</th>
                    <th>Nama tertulis</th>
                    <th>Tgl lahir tertulis</th>
                    <th>NIK</th>
                    <th>Cara terhubung</th>
                  </tr>
                </thead>
                <tbody>
                  {data.records.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <SourceBadge code={r.source} small />
                      </td>
                      <td className="mono">{r.local_id}</td>
                      <td>{r.name}</td>
                      <td className="mono">{r.birth_date_raw || "—"}</td>
                      <td className="mono">{r.nik ?? <span className="muted">—</span>}</td>
                      <td>{r.linked_by ? LINK_LABEL[r.linked_by] : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {data.issues.length > 0 && (
            <Card>
              <h2 className="card-title">
                <AlertTriangle size={18} aria-hidden /> Data pasien ini yang perlu dirapikan
              </h2>
              <ul className="issue-list">
                {data.issues.map((i, idx) => (
                  <li key={idx}>
                    <SeverityPill severity={i.severity} />
                    <span>
                      <strong>{i.label}</strong> <span className="muted">di {i.source_name}</span>
                      <div className="muted small">{i.detail}</div>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
