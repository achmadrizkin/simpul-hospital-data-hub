import { Check, CheckCircle2, Equal, HelpCircle, Merge, Minus, Undo2, UserRoundCheck, X } from "lucide-react";
import { useState } from "react";
import { api, type Candidate, type LocalRecord, type Reason } from "../lib/api";
import { formatDate, formatDateTime, sexLabel } from "../lib/format";
import { useData } from "../lib/hooks";
import {
  Button,
  Card,
  EmptyState,
  ErrorBox,
  HowTo,
  Loading,
  Meter,
  Modal,
  PageHeader,
  SourceBadge,
  useToast,
} from "../components/ui";

const RESULT_META: Record<string, { label: string; tone: string; icon: typeof Check }> = {
  sama: { label: "Sama", tone: "good", icon: Check },
  mirip: { label: "Mirip", tone: "warn", icon: Equal },
  "mirip (hari dan bulan tertukar)": { label: "Hari & bulan tertukar", tone: "warn", icon: Equal },
  beda: { label: "Beda", tone: "bad", icon: X },
  "tidak ada": { label: "Tidak ada data", tone: "neutral", icon: Minus },
  "tidak bisa dibandingkan": { label: "Tidak bisa dibandingkan", tone: "neutral", icon: HelpCircle },
};

function fieldValue(r: LocalRecord, field: string) {
  switch (field) {
    case "nik":
      return r.nik ?? "—";
    case "dob":
      return r.birth_date_raw ? `${r.birth_date_raw}${r.birth_date ? ` (${formatDate(r.birth_date)})` : ""}` : "—";
    case "name":
      return r.name;
    case "phone":
      return r.phone ?? "—";
    case "sex":
      return r.sex ? sexLabel(r.sex) : "—";
    case "address":
      return r.address ?? "—";
    default:
      return "—";
  }
}

function eventSummary(r: LocalRecord) {
  const parts: string[] = [];
  if (r.events.visit) parts.push(`${r.events.visit} kunjungan`);
  if (r.events.lab) parts.push(`${r.events.lab} hasil lab`);
  if (r.events.medication) parts.push(`${r.events.medication} obat`);
  if (r.events.charge) parts.push(`${r.events.charge} tagihan`);
  return parts.join(" · ") || "Belum ada riwayat";
}

function confidenceText(score: number) {
  if (score >= 0.85) return "Sangat mungkin orang yang sama";
  if (score >= 0.78) return "Kemungkinan orang yang sama";
  return "Ragu-ragu, perlu dicek teliti";
}

function ComparisonTable({ c }: { c: Candidate }) {
  const fields = ["name", "dob", "sex", "nik", "phone", "address"];
  const byField = new Map<string, Reason>(c.reasons.map((r) => [r.field, r]));
  return (
    <div className="table-wrap">
      <table className="compare">
        <thead>
          <tr>
            <th scope="col">Data</th>
            <th scope="col">
              <SourceBadge code={c.a.source} small /> <span className="mono small">{c.a.local_id}</span>
            </th>
            <th scope="col">
              <SourceBadge code={c.b.source} small /> <span className="mono small">{c.b.local_id}</span>
            </th>
            <th scope="col">Hasil</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const reason = byField.get(field);
            const meta = RESULT_META[reason?.result ?? "tidak ada"] ?? RESULT_META["tidak ada"];
            const Icon = meta.icon;
            const label = { name: "Nama", dob: "Tanggal lahir", sex: "Jenis kelamin", nik: "NIK", phone: "Nomor HP", address: "Alamat" }[field];
            return (
              <tr key={field} className={`row-${meta.tone}`}>
                <th scope="row">{label}</th>
                <td>{fieldValue(c.a, field)}</td>
                <td>{fieldValue(c.b, field)}</td>
                <td>
                  <span className={`result tone-text-${meta.tone}`}>
                    <Icon size={15} aria-hidden /> {reason ? meta.label : "Tidak ada data"}
                  </span>
                </td>
              </tr>
            );
          })}
          <tr className="row-history">
            <th scope="row">Riwayat</th>
            <td>{eventSummary(c.a)}</td>
            <td>{eventSummary(c.b)}</td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function CandidateCard({ c, onMerge, onReject, busy }: { c: Candidate; onMerge: () => void; onReject: () => void; busy: boolean }) {
  const pct = Math.round(c.score * 100);
  return (
    <Card className="candidate">
      <div className="candidate-head">
        <div>
          <div className="candidate-title">
            <strong>{c.a.name}</strong> <span className="muted">dan</span> <strong>{c.b.name}</strong>
          </div>
          <div className="muted small">{confidenceText(c.score)}</div>
        </div>
        <div className="candidate-score">
          <span className="score-num">{pct}%</span>
          <span className="muted small">mirip</span>
          <Meter value={pct} tone={pct >= 85 ? "good" : "warn"} />
        </div>
      </div>
      <ComparisonTable c={c} />
      <div className="candidate-actions">
        <Button variant="success" size="lg" icon={Merge} onClick={onMerge} disabled={busy}>
          Ya, orang yang sama
        </Button>
        <Button size="lg" icon={X} onClick={onReject} busy={busy}>
          Bukan, orang berbeda
        </Button>
      </div>
    </Card>
  );
}

export function CekGanda({ onChanged }: { onChanged: () => void }) {
  const [tab, setTab] = useState<"pending" | "decided">("pending");
  const { data, error, loading, reload } = useData(() => api.candidates(tab), [tab]);
  const [confirm, setConfirm] = useState<Candidate | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const toast = useToast();

  const refresh = () => {
    reload();
    onChanged();
  };

  const undo = async (id: number) => {
    await api.undo(id);
    toast({ tone: "info", message: "Keputusan dibatalkan. Pasangan ini kembali ke daftar perlu dicek." });
    refresh();
  };

  const doMerge = async (c: Candidate) => {
    setBusyId(c.id);
    try {
      const res = await api.merge(c.id);
      toast({
        tone: "good",
        message: (
          <>
            Digabung. Riwayat <strong>{c.a.name}</strong> sekarang lengkap.{" "}
            {res.new_alerts.length > 0 && (
              <>
                Data yang disatukan memunculkan <strong>{res.new_alerts.length} peringatan klinis baru</strong>.{" "}
              </>
            )}
            <a href={`#/pasien/${res.golden_id}`}>Lihat pasien</a>
          </>
        ),
        action: { label: "Batalkan", onClick: () => undo(c.id) },
      });
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal menggabungkan." });
    } finally {
      setBusyId(null);
      setConfirm(null);
      refresh();
    }
  };

  const doReject = async (c: Candidate) => {
    setBusyId(c.id);
    try {
      await api.reject(c.id);
      toast({
        tone: "info",
        message: "Dicatat sebagai dua orang berbeda.",
        action: { label: "Batalkan", onClick: () => undo(c.id) },
      });
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal menyimpan." });
    } finally {
      setBusyId(null);
      refresh();
    }
  };

  return (
    <>
      <PageHeader
        title="Cek Pasien Ganda"
        subtitle="Satu orang bisa tercatat beberapa kali dengan penulisan berbeda. Pastikan apakah dua catatan ini milik orang yang sama."
      />
      <HowTo
        id="ganda"
        steps={[
          <>Bandingkan kolom kiri dan kanan. Perhatikan kolom <strong>Hasil</strong>: hijau sama, kuning mirip, merah beda.</>,
          <>Yang paling penting: <strong>tanggal lahir</strong> dan <strong>nama</strong>. NIK yang sama berarti pasti orang yang sama.</>,
          <>Jika yakin sama, tekan <strong>Ya, orang yang sama</strong>. Jika ragu, biarkan dulu dan tanyakan pasien saat datang. Semua keputusan bisa dibatalkan.</>,
        ]}
      />

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "pending"} className={`tab ${tab === "pending" ? "active" : ""}`} onClick={() => setTab("pending")}>
          Perlu dicek {data && <span className="tab-count">{data.counts.pending}</span>}
        </button>
        <button role="tab" aria-selected={tab === "decided"} className={`tab ${tab === "decided" ? "active" : ""}`} onClick={() => setTab("decided")}>
          Sudah diputuskan {data && <span className="tab-count muted-count">{data.counts.decided}</span>}
        </button>
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <Loading />}

      {data && tab === "pending" && (
        data.items.length === 0 ? (
          <EmptyState icon={CheckCircle2} title="Semua sudah dicek">
            Tidak ada catatan yang perlu dibandingkan saat ini. Simpul akan memberi tahu jika ada yang baru.
          </EmptyState>
        ) : (
          <div className="candidate-list">
            {data.items.map((c) => (
              <CandidateCard
                key={c.id}
                c={c}
                busy={busyId === c.id}
                onMerge={() => setConfirm(c)}
                onReject={() => doReject(c)}
              />
            ))}
          </div>
        )
      )}

      {data && tab === "decided" && (
        data.items.length === 0 ? (
          <EmptyState icon={UserRoundCheck} title="Belum ada keputusan">
            Keputusan yang Anda buat akan tampil di sini dan bisa dibatalkan.
          </EmptyState>
        ) : (
          <Card>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Catatan</th>
                    <th>Keputusan</th>
                    <th>Oleh</th>
                    <th>Waktu</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <div>
                          <SourceBadge code={c.a.source} small /> {c.a.name}
                        </div>
                        <div>
                          <SourceBadge code={c.b.source} small /> {c.b.name}
                        </div>
                      </td>
                      <td>
                        {c.status === "merged" ? (
                          <span className="pill tone-good">
                            <Merge size={13} aria-hidden /> Digabung
                          </span>
                        ) : (
                          <span className="pill tone-neutral">
                            <X size={13} aria-hidden /> Orang berbeda
                          </span>
                        )}
                      </td>
                      <td>{c.decided_by}</td>
                      <td>{formatDateTime(c.decided_at)}</td>
                      <td>
                        {c.decided_by !== "otomatis (ikut tergabung)" && (
                          <Button variant="ghost" icon={Undo2} onClick={() => undo(c.id)}>
                            Batalkan
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      )}

      {confirm && (
        <Modal
          title="Gabungkan dua catatan ini?"
          onClose={() => setConfirm(null)}
          footer={
            <>
              <Button onClick={() => setConfirm(null)}>Batal</Button>
              <Button variant="success" icon={Merge} busy={busyId === confirm.id} onClick={() => doMerge(confirm)}>
                Ya, gabungkan
              </Button>
            </>
          }
        >
          <p>
            Catatan <strong>{confirm.a.name}</strong> ({confirm.a.source_name}) dan <strong>{confirm.b.name}</strong> (
            {confirm.b.source_name}) akan dianggap <strong>satu orang</strong>.
          </p>
          <ul className="plain-list">
            <li>Riwayat kunjungan, hasil lab, obat, dan tagihan akan tampil bersama.</li>
            <li>Data di sistem asli (SIMRS, Lab, dll.) <strong>tidak diubah</strong>.</li>
            <li>Keputusan ini bisa dibatalkan kapan saja.</li>
          </ul>
        </Modal>
      )}
    </>
  );
}
