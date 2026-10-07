import { ArrowRight, CheckCircle2, Download, X } from "lucide-react";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";
import { useData } from "../lib/hooks";
import { go } from "../lib/router";
import {
  Card,
  EmptyState,
  ErrorBox,
  HowTo,
  Loading,
  Meter,
  PageHeader,
  ScoreRing,
  SeverityPill,
  SourceBadge,
  scoreVerdict,
} from "../components/ui";

const FIX_LINKS: Record<string, { href: string; label: string }> = {
  PASIEN_GANDA_BELUM_DICEK: { href: "#/ganda", label: "Buka Cek Pasien Ganda" },
  KODE_BELUM_STANDAR: { href: "#/kode", label: "Buka Samakan Kode" },
};

function IssueTable({ rule }: { rule: string }) {
  const { data, error, loading, reload } = useData(() => api.issues(rule), [rule]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;
  return (
    <>
      <p className="muted small">
        Menampilkan {formatNumber(data.items.length)} dari {formatNumber(data.total)} data.
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Pasien</th>
              <th>Sistem</th>
              <th>Nomor di sistem</th>
              <th>Keterangan</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((i, idx) => (
              <tr key={idx}>
                <td>
                  {i.golden_id ? <a href={`#/pasien/${i.golden_id}`}>{i.patient ?? "Tanpa nama"}</a> : i.patient ?? "—"}
                </td>
                <td>
                  <SourceBadge code={i.source} small />
                </td>
                <td className="mono">{i.ref}</td>
                <td>{i.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function Kualitas({ rule }: { rule?: string }) {
  const { data, error, loading, reload } = useData(api.quality, []);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const verdict = scoreVerdict(data.score);
  const selected = data.rules.find((r) => r.rule === rule);

  return (
    <>
      <PageHeader
        title="Kualitas Data"
        subtitle="Seberapa rapi data rumah sakit, dan apa saja yang perlu diperbaiki."
        actions={
          <a className="btn btn-primary btn-md" href={api.issuesCsvUrl()}>
            <Download size={18} aria-hidden /> <span>Unduh semua daftar perbaikan (Excel)</span>
          </a>
        }
      />
      <HowTo
        id="kualitas"
        steps={[
          <>Nilai 100 berarti semua data rapi. Di atas <strong>90</strong> sudah sangat baik.</>,
          <>Klik salah satu masalah untuk melihat daftar pasiennya.</>,
          <>Unduh daftar perbaikan dan bagikan ke bagian terkait (pendaftaran, dokter, lab).</>,
        ]}
      />

      <div className="quality-top">
        <Card className="score-card">
          <div className="card-eyebrow">Nilai keseluruhan</div>
          <div className="score-card-body">
            <ScoreRing score={data.score} />
            <div>
              <div className={`verdict tone-text-${verdict.tone}`}>{verdict.label}</div>
              <p className="muted">
                {formatNumber(data.records_with_issues)} dari {formatNumber(data.records)} data punya setidaknya satu
                masalah.
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <h2 className="card-title">Nilai per sistem</h2>
          <ul className="source-scores">
            {data.sources.map((s) => (
              <li key={s.code}>
                <div className="source-score-head">
                  <SourceBadge code={s.code} />
                  <strong className="num">{s.score}</strong>
                </div>
                <Meter value={s.score} />
                <span className="muted small">
                  {s.top_rules.length ? `Terbanyak: ${s.top_rules.map((r) => `${r.label.toLowerCase()} (${r.count})`).join(", ")}` : "Tidak ada masalah"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <h2 className="section-title">Daftar masalah</h2>
      <div className="rule-list">
        {data.rules.map((r) => {
          const active = r.rule === rule;
          return (
            <button
              key={r.rule}
              className={`rule-card ${active ? "active" : ""} ${r.count === 0 ? "done" : ""}`}
              onClick={() => go(active ? "/kualitas" : `/kualitas?masalah=${r.rule}`)}
              aria-expanded={active}
            >
              <div className="rule-card-head">
                {r.count === 0 ? (
                  <span className="pill tone-good">
                    <CheckCircle2 size={13} aria-hidden /> Beres
                  </span>
                ) : (
                  <SeverityPill severity={r.severity} />
                )}
                <strong className="rule-count num">{formatNumber(r.count)}</strong>
              </div>
              <strong className="rule-label">{r.label}</strong>
              <span className="muted small">{r.why}</span>
            </button>
          );
        })}
      </div>

      {selected && (
        <Card className="issue-panel">
          <div className="issue-panel-head">
            <div>
              <h2 className="card-title">{selected.label}</h2>
              <p>
                <strong>Cara memperbaiki:</strong> {selected.fix}
              </p>
            </div>
            <div className="button-row">
              {FIX_LINKS[selected.rule] && (
                <a className="btn btn-primary btn-md" href={FIX_LINKS[selected.rule].href}>
                  <span>{FIX_LINKS[selected.rule].label}</span> <ArrowRight size={16} aria-hidden />
                </a>
              )}
              <a className="btn btn-secondary btn-md" href={api.issuesCsvUrl(selected.rule)}>
                <Download size={18} aria-hidden /> <span>Unduh daftar ini</span>
              </a>
              <button className="icon-button" onClick={() => go("/kualitas")} aria-label="Tutup daftar">
                <X size={18} />
              </button>
            </div>
          </div>
          {selected.count === 0 ? (
            <EmptyState icon={CheckCircle2} title="Tidak ada masalah jenis ini" />
          ) : (
            <IssueTable rule={selected.rule} />
          )}
        </Card>
      )}
    </>
  );
}
