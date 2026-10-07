import { CheckCircle2, ClipboardCheck, Plus, RotateCcw, ShieldCheck, Siren } from "lucide-react";
import { useState } from "react";
import { api, type AlertStatus, type ClinicalAlert } from "../lib/api";
import { formatDate, formatDateTime, sexLabel, timeAgo } from "../lib/format";
import { useData } from "../lib/hooks";
import {
  Button,
  Card,
  EmptyState,
  ErrorBox,
  HowTo,
  Loading,
  Modal,
  Notice,
  PageHeader,
  SourceBadge,
  useToast,
} from "../components/ui";

const QUICK_NOTES = [
  "Sudah dikonfirmasi ke dokter penanggung jawab",
  "Pasien dijadwalkan kontrol ulang",
  "Sudah dicatat di rekam medis",
];

function evidenceValue(e: ClinicalAlert["evidence"][number]) {
  if (e.kind === "lab") {
    const flag = e.flag === "H" ? " ↑ tinggi" : e.flag === "L" ? " ↓ rendah" : "";
    return `${e.value} ${e.unit ?? ""}${flag}`;
  }
  return e.detail ?? "";
}

function HandleModal({ alert, onClose, onDone }: { alert: ClinicalAlert; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const save = async () => {
    setBusy(true);
    try {
      await api.handleAlert(alert.id, note);
      toast({
        tone: "good",
        message: "Peringatan ditandai sudah ditindaklanjuti.",
        action: { label: "Batalkan", onClick: () => api.reopenAlert(alert.id).then(onDone) },
      });
      onClose();
      onDone();
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal menyimpan." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Tandai sudah ditindaklanjuti"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Batal</Button>
          <Button variant="success" icon={ClipboardCheck} busy={busy} onClick={save}>
            Simpan
          </Button>
        </>
      }
    >
      <p>
        <strong>{alert.title}</strong>
      </p>
      <label className="field-label" htmlFor="alert-note">
        Apa yang sudah dilakukan? <span className="muted">(boleh dikosongkan)</span>
      </label>
      <div className="chips quick-notes">
        {QUICK_NOTES.map((q) => (
          <button key={q} className={`chip ${note === q ? "active" : ""}`} onClick={() => setNote(q)}>
            {q}
          </button>
        ))}
      </div>
      <textarea
        id="alert-note"
        className="textarea"
        rows={3}
        maxLength={500}
        placeholder="Tulis catatan singkat…"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
    </Modal>
  );
}

export function AlertCard({ alert, compact, onChanged }: { alert: ClinicalAlert; compact?: boolean; onChanged: () => void }) {
  const [handling, setHandling] = useState(false);
  const toast = useToast();
  const p = alert.patient;

  const reopen = async () => {
    await api.reopenAlert(alert.id);
    toast({ tone: "info", message: "Peringatan dibuka kembali." });
    onChanged();
  };

  return (
    <article className={`alert-card sev-${alert.severity} status-${alert.status}`}>
      <div className="alert-head">
        <span className="alert-icon" aria-hidden>
          {alert.status === "open" ? <Siren size={20} /> : <CheckCircle2 size={20} />}
        </span>
        <div className="alert-title-block">
          <div className="alert-meta">
            <span className={`pill ${alert.severity === "tinggi" ? "tone-bad" : "tone-warn"}`}>
              {alert.severity === "tinggi" ? "Segera dicek" : "Perlu perhatian"}
            </span>
            <span className="muted small">Muncul {timeAgo(alert.created_at)}</span>
          </div>
          <h3 className="alert-title">{alert.title}</h3>
          {!compact && p && (
            <a className="alert-patient" href={`#/pasien/${alert.golden_id}`}>
              {p.name} · {sexLabel(p.sex)}
              {p.age !== null ? `, ${p.age} th` : ""} · <span className="mono">{alert.golden_label}</span>
            </a>
          )}
        </div>
      </div>

      <p className="alert-detail">{alert.detail}</p>

      <div className="alert-evidence">
        <span className="evidence-label">Ditemukan dengan menyatukan data dari:</span>
        <div className="evidence-row">
          {alert.evidence.map((e, i) => (
            <div key={`${e.event_id}-${i}`} className="evidence-item">
              {i > 0 && (
                <span className="evidence-plus" aria-hidden>
                  <Plus size={16} />
                </span>
              )}
              <div className="evidence-box">
                <SourceBadge code={e.source} small />
                <strong>{e.title}</strong>
                <span className={e.flag === "H" || e.flag === "L" ? "tone-text-bad evidence-value" : "evidence-value"}>
                  {evidenceValue(e)}
                </span>
                <span className="muted small">{formatDate(e.occurred_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {alert.status === "open" && (
        <div className="button-row">
          <Button variant="primary" icon={ClipboardCheck} onClick={() => setHandling(true)}>
            Tandai sudah ditindaklanjuti
          </Button>
          {!compact && (
            <a className="btn btn-ghost btn-md" href={`#/pasien/${alert.golden_id}`}>
              <span>Buka riwayat pasien</span>
            </a>
          )}
        </div>
      )}
      {alert.status === "handled" && (
        <div className="alert-handled">
          <ShieldCheck size={18} aria-hidden />
          <span>
            Ditindaklanjuti oleh <strong>{alert.handled_by}</strong>, {formatDateTime(alert.handled_at)}
            {alert.note && <> · "{alert.note}"</>}
          </span>
          <Button variant="ghost" icon={RotateCcw} onClick={reopen}>
            Buka lagi
          </Button>
        </div>
      )}
      {alert.status === "resolved" && (
        <div className="alert-handled">
          <CheckCircle2 size={18} aria-hidden />
          <span>
            Selesai otomatis {formatDateTime(alert.resolved_at)}, karena kondisinya sudah tidak terpenuhi lagi (misalnya
            ada data obat atau lab baru).
          </span>
        </div>
      )}
      {handling && <HandleModal alert={alert} onClose={() => setHandling(false)} onDone={onChanged} />}
    </article>
  );
}

function RulesCard({ onChanged }: { onChanged: () => void }) {
  const { data, reload } = useData(api.alertRules, []);
  const toast = useToast();
  if (!data) return null;

  const toggle = async (code: string, enabled: boolean) => {
    const res = await api.toggleRule(code, enabled);
    toast({
      tone: "info",
      message: enabled
        ? `Aturan diaktifkan. ${res.new_alerts} peringatan baru ditemukan.`
        : `Aturan dimatikan. ${res.resolved_alerts} peringatan ditutup.`,
    });
    reload();
    onChanged();
  };

  return (
    <Card>
      <h2 className="card-title">Aturan yang dipakai</h2>
      <p className="muted small">
        Setiap aturan menggabungkan data dari minimal dua sistem. Rumah sakit bisa menyalakan atau mematikan aturan sesuai
        kebijakan komite medis.
      </p>
      <ul className="rule-rows">
        {data.items.map((r) => (
          <li key={r.code}>
            <div className="rule-row-main">
              <strong>{r.title}</strong>
              <span className="muted small">{r.description}</span>
              <span className="badge-row">
                {r.sources.map((s) => (
                  <SourceBadge key={s} name={s} small />
                ))}
              </span>
            </div>
            <span className="rule-row-count">
              <strong>{r.open_count}</strong>
              <span className="muted small">terbuka</span>
            </span>
            <label className="switch" htmlFor={`rule-${r.code}`}>
              <input id={`rule-${r.code}`} type="checkbox" checked={r.enabled} onChange={(e) => toggle(r.code, e.target.checked)} />
              <span className="switch-track" aria-hidden />
              <span className="sr-only">{r.enabled ? "Matikan" : "Nyalakan"} aturan {r.title}</span>
            </label>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const TABS: { key: AlertStatus; label: string }[] = [
  { key: "open", label: "Perlu ditindaklanjuti" },
  { key: "handled", label: "Sudah ditindaklanjuti" },
  { key: "resolved", label: "Selesai otomatis" },
];

export function Peringatan({ onChanged }: { onChanged: () => void }) {
  const [tab, setTab] = useState<AlertStatus>("open");
  const { data, error, loading, reload } = useData(() => api.alerts(tab), [tab], 10000);

  const refresh = () => {
    reload();
    onChanged();
  };

  return (
    <>
      <PageHeader
        title="Peringatan Klinis"
        subtitle="Hal-hal yang tidak terlihat jika data lab, farmasi, dan SIMRS dilihat terpisah. Simpul menemukannya setelah data pasien disatukan."
      />
      <HowTo
        id="peringatan"
        steps={[
          <>Baca peringatan paling atas dulu. Label <strong>merah</strong> berarti perlu segera dicek.</>,
          <>Lihat kotak bukti: data apa saja dari sistem mana yang memicu peringatan.</>,
          <>Teruskan ke dokter, lalu tekan <strong>Tandai sudah ditindaklanjuti</strong> dan tulis catatan singkat.</>,
        ]}
      />
      <Notice tone="info">
        Ini <strong>contoh aturan</strong> untuk demonstrasi, bukan pengganti penilaian dokter. Di rumah sakit sungguhan,
        aturan ditetapkan bersama komite medis.
      </Notice>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
            {data && <span className={`tab-count ${t.key === "open" ? "" : "muted-count"}`}>{data.counts[t.key]}</span>}
          </button>
        ))}
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && (
        <EmptyState icon={CheckCircle2} title={tab === "open" ? "Tidak ada peringatan terbuka" : "Belum ada data"}>
          {tab === "open" ? "Peringatan baru akan muncul otomatis saat data lab atau obat baru masuk." : undefined}
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <div className="alert-list">
          {data.items.map((a) => (
            <AlertCard key={a.id} alert={a} onChanged={refresh} />
          ))}
        </div>
      )}

      <RulesCard onChanged={refresh} />
    </>
  );
}
