import { ArrowRight, CheckCircle2, Languages, Pencil, Search, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Mapping } from "../lib/api";
import { formatDateTime, formatNumber } from "../lib/format";
import { useData } from "../lib/hooks";
import {
  Button,
  Card,
  EmptyState,
  ErrorBox,
  HowTo,
  Loading,
  Modal,
  PageHeader,
  SourceBadge,
  Term,
  useToast,
} from "../components/ui";

const STANDARD_EXPLAIN: Record<string, string> = {
  "ICD-10": "Kode diagnosis standar WHO. Dipakai untuk klaim BPJS, laporan penyakit, dan SATUSEHAT.",
  LOINC: "Kode standar internasional untuk jenis pemeriksaan laboratorium.",
  ATC: "Kode standar WHO untuk jenis obat berdasarkan zat aktifnya.",
};

const SYSTEM_TONE: Record<string, string> = { dx: "dx", lab: "lab", obat: "obat" };

function PickCodeModal({ mapping, onClose, onPicked }: { mapping: Mapping; onClose: () => void; onPicked: (code: string) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<{ code: string; text: string }[]>([]);
  useEffect(() => {
    const t = window.setTimeout(() => {
      api.catalog(mapping.system, q).then((r) => setItems(r.items)).catch(() => setItems([]));
    }, 200);
    return () => window.clearTimeout(t);
  }, [q, mapping.system]);

  return (
    <Modal title={`Pilih kode ${mapping.standard} untuk "${mapping.local_code}"`} onClose={onClose}>
      <div className="search-box small">
        <Search size={18} aria-hidden />
        <input
          id="catalog-search"
          type="search"
          placeholder="Cari nama atau kode…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Cari kode standar"
        />
      </div>
      <ul className="pick-list">
        {items.map((item) => (
          <li key={item.code}>
            <button onClick={() => onPicked(item.code)}>
              <span className="code-chip std">{item.code}</span>
              <span>{item.text}</span>
              <ArrowRight size={16} aria-hidden />
            </button>
          </li>
        ))}
        {items.length === 0 && <li className="muted">Tidak ada kode yang cocok.</li>}
      </ul>
    </Modal>
  );
}

export function SamakanKode({ onChanged }: { onChanged: () => void }) {
  const [tab, setTab] = useState<"todo" | "done">("todo");
  const { data, error, loading, reload } = useData(() => api.mappings(tab), [tab]);
  const [picking, setPicking] = useState<Mapping | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const toast = useToast();

  const refresh = () => {
    reload();
    onChanged();
  };

  const confirm = async (m: Mapping, code: string) => {
    setBusy(m.id);
    try {
      const res = await api.confirmMapping(m.id, code);
      toast({
        tone: "good",
        message: (
          <>
            "<strong>{m.local_code}</strong>" sekarang tercatat sebagai {m.standard} {code}. Berlaku untuk{" "}
            {formatNumber(m.usage)} data.
            {res.resolved_alerts > 0 && <> {res.resolved_alerts} peringatan klinis selesai otomatis.</>}
            {res.new_alerts > 0 && <> {res.new_alerts} peringatan klinis baru muncul.</>}
          </>
        ),
        action: { label: "Batalkan", onClick: () => api.resetMapping(m.id).then(refresh) },
      });
    } catch (err) {
      toast({ tone: "bad", message: err instanceof Error ? err.message : "Gagal menyimpan." });
    } finally {
      setBusy(null);
      setPicking(null);
      refresh();
    }
  };

  return (
    <>
      <PageHeader
        title="Samakan Kode"
        subtitle="Setiap bagian rumah sakit punya singkatan sendiri. Di sini singkatan itu disamakan dengan kode standar, cukup sekali, lalu berlaku untuk semua data."
      />
      <HowTo
        id="kode"
        steps={[
          <>Lihat kolom <strong>Tertulis di RS</strong>, misalnya "Omz 20" dari Farmasi.</>,
          <>Simpul sudah menyiapkan <strong>saran kode standar</strong>. Jika benar, tekan <strong>Setujui</strong>.</>,
          <>Jika saran salah atau kosong, tekan <strong>Pilih kode lain</strong> dan cari kode yang tepat.</>,
        ]}
      />

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "todo"} className={`tab ${tab === "todo" ? "active" : ""}`} onClick={() => setTab("todo")}>
          Perlu dicek {data && <span className="tab-count">{data.counts.todo}</span>}
        </button>
        <button role="tab" aria-selected={tab === "done"} className={`tab ${tab === "done" ? "active" : ""}`} onClick={() => setTab("done")}>
          Sudah disamakan {data && <span className="tab-count muted-count">{data.counts.done}</span>}
        </button>
      </div>

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && (
        tab === "todo" ? (
          <EmptyState icon={CheckCircle2} title="Semua kode sudah disamakan">
            Jika ada singkatan baru dari sistem mana pun, akan muncul di sini.
          </EmptyState>
        ) : (
          <EmptyState icon={Languages} title="Belum ada kode yang disamakan" />
        )
      )}
      {data && data.items.length > 0 && (
        <Card className="flush">
          <div className="table-wrap">
            <table className="table mapping-table">
              <thead>
                <tr>
                  <th>Jenis</th>
                  <th>Tertulis di RS</th>
                  <th className="num">Dipakai</th>
                  <th>{tab === "todo" ? "Saran kode standar" : "Kode standar"}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <span className={`kind-tag kind-${SYSTEM_TONE[m.system]}`}>{m.system_label}</span>
                    </td>
                    <td>
                      <strong className="mono local-code">{m.local_code}</strong>
                      {m.local_text && m.local_text !== m.local_code && <div className="muted small">"{m.local_text}"</div>}
                      <div className="badge-row">
                        {m.source_names.map((s) => (
                          <SourceBadge key={s} name={s} small />
                        ))}
                      </div>
                    </td>
                    <td className="num">
                      <strong>{formatNumber(m.usage)}</strong> data
                      <div className="muted small">{formatNumber(m.patients)} pasien</div>
                    </td>
                    <td>
                      {m.std_code ? (
                        <>
                          <div>
                            <Term explain={STANDARD_EXPLAIN[m.standard]}>
                              <span className="code-chip std">
                                {m.standard} {m.std_code}
                              </span>
                            </Term>
                          </div>
                          <div>{m.std_text}</div>
                          <div className="muted small">
                            {tab === "todo"
                              ? `Saran dari: ${m.suggested_by}`
                              : `Disetujui ${m.confirmed_by}${m.confirmed_at ? `, ${formatDateTime(m.confirmed_at)}` : ""}`}
                          </div>
                        </>
                      ) : (
                        <span className="muted">Belum ada saran. Pilih kode secara manual.</span>
                      )}
                    </td>
                    <td className="row-actions">
                      {tab === "todo" ? (
                        <>
                          {m.std_code && (
                            <Button variant="success" icon={CheckCircle2} busy={busy === m.id} onClick={() => confirm(m, m.std_code!)}>
                              Setujui
                            </Button>
                          )}
                          <Button variant={m.std_code ? "ghost" : "primary"} icon={Pencil} onClick={() => setPicking(m)}>
                            {m.std_code ? "Pilih kode lain" : "Pilih kode"}
                          </Button>
                        </>
                      ) : (
                        m.confirmed_by !== "Sistem" && (
                          <Button variant="ghost" icon={Undo2} onClick={() => api.resetMapping(m.id).then(refresh)}>
                            Ubah
                          </Button>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {picking && <PickCodeModal mapping={picking} onClose={() => setPicking(null)} onPicked={(code) => confirm(picking, code)} />}
    </>
  );
}
