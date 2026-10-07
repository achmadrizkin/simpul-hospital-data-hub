import { Download, FlaskConical, PlugZap, RefreshCw, RotateCcw, Unplug, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { api, type SourceDetail } from "../lib/api";
import { formatDateTime, formatNumber, formatTime, timeAgo } from "../lib/format";
import { useData } from "../lib/hooks";
import {
  Button,
  Card,
  ErrorBox,
  HowTo,
  Loading,
  Modal,
  PageHeader,
  SOURCE_META,
  StatusPill,
  statusHint,
  useToast,
} from "../components/ui";

function scheduleLabel(minutes: number) {
  if (minutes < 1) return `setiap ${Math.round(minutes * 60)} detik`;
  if (minutes === 1) return "setiap menit";
  return `setiap ${minutes} menit`;
}

function SourcePanel({ src, onDone }: { src: SourceDetail; onDone: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const Icon = SOURCE_META[src.code].icon;

  const run = async (key: string, fn: () => Promise<{ status: string; message: string }>, okText: string) => {
    setBusy(key);
    try {
      const result = await fn();
      if (result.status === "gagal") toast({ tone: "bad", message: result.message });
      else toast({ tone: "good", message: `${okText} ${result.message}.` });
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal." });
    } finally {
      setBusy(null);
      onDone();
    }
  };

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) run("upload", () => api.uploadFarmasi(file), `File "${file.name}" diterima:`);
  };

  return (
    <Card className={`source-panel status-${src.status}`}>
      <div className="source-panel-head">
        <span className={`source-icon large src-${src.code}`}>
          <Icon size={26} aria-hidden />
        </span>
        <div className="source-panel-title">
          <h2>{src.name}</h2>
          <p className="muted">{src.description}</p>
        </div>
        <StatusPill status={src.status} large />
      </div>

      {src.status === "gagal" && (
        <div className="notice tone-bad compact">
          <strong>Apa yang terjadi:</strong> {src.last_message} Data lama tetap aman dan bisa dilihat.
        </div>
      )}

      <dl className="facts">
        <div>
          <dt>Cara mengambil data</dt>
          <dd>{src.method_label}</dd>
        </div>
        <div>
          <dt>Jadwal</dt>
          <dd>Otomatis {scheduleLabel(src.interval_min)}</dd>
        </div>
        <div>
          <dt>Terakhir diambil</dt>
          <dd title={formatDateTime(src.last_sync_at)}>{timeAgo(src.last_sync_at)}</dd>
        </div>
        <div>
          <dt>Isi data</dt>
          <dd>
            {formatNumber(src.patients)} pasien · {formatNumber(src.events)} catatan
          </dd>
        </div>
      </dl>

      <div className="button-row">
        <Button icon={RefreshCw} busy={busy === "sync"} onClick={() => run("sync", () => api.syncNow(src.code), "Selesai.")}>
          Ambil data sekarang
        </Button>
        {src.code === "farmasi" && (
          <>
            <Button variant="primary" icon={Upload} busy={busy === "upload"} onClick={() => fileRef.current?.click()}>
              Unggah file CSV
            </Button>
            <a className="btn btn-ghost btn-md" href={api.sampleFarmasiUrl}>
              <Download size={18} aria-hidden /> <span>Unduh contoh file</span>
            </a>
            <input ref={fileRef} type="file" accept=".csv" hidden onChange={onFile} />
          </>
        )}
      </div>

      <details className="runs">
        <summary>Riwayat pengambilan data ({src.runs.length} terakhir)</summary>
        <table className="table compact">
          <thead>
            <tr>
              <th>Waktu</th>
              <th>Hasil</th>
              <th className="num">Data baru</th>
            </tr>
          </thead>
          <tbody>
            {src.runs.map((r) => (
              <tr key={r.id}>
                <td>{formatTime(r.finished_at ?? r.started_at)}</td>
                <td className={r.status === "gagal" ? "tone-text-bad" : ""}>{r.status === "gagal" ? r.message : "Berhasil"}</td>
                <td className="num">{formatNumber(r.records_new)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="muted small status-hint">{statusHint(src.status)}.</p>
    </Card>
  );
}

function DemoPanel({ sources, live, onDone }: { sources: SourceDetail[]; live: boolean; onDone: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  const act = async (key: string, fn: () => Promise<unknown>, message: string) => {
    setBusy(key);
    try {
      await fn();
      toast({ tone: "info", message });
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal." });
    } finally {
      setBusy(null);
      onDone();
    }
  };

  return (
    <Card className="demo-panel">
      <h2 className="card-title">
        <PlugZap size={18} aria-hidden /> Panel demo
      </h2>
      <p className="muted">
        Tombol di bawah ini meniru kejadian di rumah sakit sungguhan, supaya bisa diperagakan saat presentasi.
      </p>
      <div className="demo-actions">
        <label className="switch">
          <input
            id="live-toggle"
            type="checkbox"
            checked={live}
            onChange={(e) =>
              act("live", () => api.setLive(e.target.checked), e.target.checked ? "Alat lab mulai mengirim hasil otomatis." : "Pengiriman otomatis dihentikan.")
            }
          />
          <span className="switch-track" aria-hidden />
          <span>Alat lab mengirim hasil otomatis tiap 40 detik</span>
        </label>
        <Button
          icon={FlaskConical}
          busy={busy === "lab"}
          onClick={() =>
            act("lab", async () => {
              const r = await api.sendLab();
              toast({ tone: "good", message: `Hasil lab baru untuk ${r.patient.replace("^", ", ")} masuk: ${r.tests.join(", ")}.` });
            }, "Pesan HL7 dari alat lab diterima.")
          }
        >
          Kirim 1 hasil lab baru
        </Button>
      </div>
      <div className="demo-outages">
        <span className="muted small">Simulasikan koneksi putus:</span>
        {sources.map((s) => (
          <Button
            key={s.code}
            variant={s.outage ? "danger" : "ghost"}
            icon={s.outage ? PlugZap : Unplug}
            busy={busy === `out-${s.code}`}
            onClick={() =>
              act(`out-${s.code}`, () => api.setOutage(s.code, !s.outage), s.outage ? `${s.name} tersambung lagi.` : `Koneksi ${s.name} diputus (simulasi).`)
            }
          >
            {s.outage ? `Sambungkan ${s.name}` : `Putus ${s.name}`}
          </Button>
        ))}
      </div>
      <div className="button-row">
        <Button variant="ghost" icon={RotateCcw} onClick={() => setConfirmReset(true)}>
          Ulang data demo dari awal
        </Button>
      </div>
      {confirmReset && (
        <Modal
          title="Ulang data demo dari awal?"
          onClose={() => setConfirmReset(false)}
          footer={
            <>
              <Button onClick={() => setConfirmReset(false)}>Batal</Button>
              <Button
                variant="danger"
                busy={busy === "reset"}
                onClick={() =>
                  act("reset", api.resetDemo, "Data demo sudah dikembalikan ke awal.").then(() => setConfirmReset(false))
                }
              >
                Ya, ulang dari awal
              </Button>
            </>
          }
        >
          <p>Semua keputusan (pasien yang digabung, kode yang disetujui) akan dihapus dan data contoh dibuat ulang.</p>
        </Modal>
      )}
    </Card>
  );
}

export function SumberData({ onChanged }: { onChanged: () => void }) {
  const { data, error, loading, reload } = useData(api.sources, [], 5000);
  const refresh = () => {
    reload();
    onChanged();
  };

  return (
    <>
      <PageHeader
        title="Sumber Data"
        subtitle="Sistem-sistem rumah sakit yang datanya dikumpulkan Simpul. Simpul hanya membaca data, tidak pernah mengubah isi sistem asli."
      />
      <HowTo
        id="sumber"
        steps={[
          <>Lihat warna status: <strong>hijau</strong> berarti lancar, <strong>merah</strong> berarti perlu dicek tim IT.</>,
          <>Data diambil otomatis sesuai jadwal. Tekan <strong>Ambil data sekarang</strong> bila ingin lebih cepat.</>,
          <>Untuk Farmasi, unggah file CSV hasil ekspor harian dengan tombol <strong>Unggah file CSV</strong>.</>,
        ]}
      />
      {loading && !data && <Loading />}
      {error && !data && <ErrorBox message={error} onRetry={reload} />}
      {data && (
        <>
          <div className="source-panels">
            {data.sources.map((s) => (
              <SourcePanel key={s.code} src={s} onDone={refresh} />
            ))}
          </div>
          <DemoPanel sources={data.sources} live={data.live.enabled} onDone={refresh} />
        </>
      )}
    </>
  );
}
