import { ArrowRight, ClipboardList, Languages, Siren, Stethoscope, UserRoundCheck, Users } from "lucide-react";
import { api } from "../lib/api";
import { formatNumber, formatTime, greeting, timeAgo } from "../lib/format";
import { useData } from "../lib/hooks";
import {
  Card,
  ErrorBox,
  Loading,
  Notice,
  PageHeader,
  ScoreRing,
  SeverityPill,
  SourceBadge,
  SOURCE_META,
  StatusPill,
  scoreVerdict,
} from "../components/ui";

export function Beranda() {
  const { data, error, loading, reload } = useData(api.overview, [], 8000);

  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const t = data.totals;
  const verdict = scoreVerdict(t.quality_score);
  const visitsNoDx = data.top_problems.find((p) => p.rule === "KUNJUNGAN_TANPA_DIAGNOSIS")?.count ?? 0;
  const broken = data.sources.filter((s) => s.status === "gagal");

  const tasks = [
    {
      show: t.open_alerts > 0,
      icon: Siren,
      count: t.open_alerts,
      title: "peringatan klinis perlu ditindaklanjuti",
      hint: "Temuan yang hanya terlihat setelah data lab, farmasi, dan SIMRS disatukan.",
      href: "#/peringatan",
      action: "Lihat peringatan",
      tone: "bad",
    },
    {
      show: t.pending_duplicates > 0,
      icon: UserRoundCheck,
      count: t.pending_duplicates,
      title: "pasangan catatan mungkin milik orang yang sama",
      hint: "Pastikan apakah benar satu orang, lalu gabungkan.",
      href: "#/ganda",
      action: "Cek sekarang",
    },
    {
      show: t.unmapped_codes > 0,
      icon: Languages,
      count: t.unmapped_codes,
      title: "singkatan belum disamakan ke kode standar",
      hint: "Cukup setujui saran yang sudah disiapkan.",
      href: "#/kode",
      action: "Samakan kode",
    },
    {
      show: visitsNoDx > 0,
      icon: Stethoscope,
      count: visitsNoDx,
      title: "kunjungan belum ada diagnosisnya",
      hint: "Perlu dilengkapi dokter agar bisa diklaim.",
      href: "#/kualitas?masalah=KUNJUNGAN_TANPA_DIAGNOSIS",
      action: "Lihat daftar",
    },
  ].filter((task) => task.show);

  return (
    <>
      <PageHeader
        title={`${greeting()}, Petugas Rekam Medis`}
        subtitle="Ini ringkasan data rumah sakit hari ini. Halaman ini diperbarui otomatis."
      />

      {broken.length > 0 && (
        <Notice tone="bad">
          <strong>{broken.map((s) => s.name).join(", ")} tidak bisa diambil datanya.</strong>{" "}
          {broken[0].last_message} Hubungi tim IT atau buka <a href="#/sumber">Sumber Data</a>.
        </Notice>
      )}

      <div className="home-grid">
        <Card className="score-card">
          <div className="card-eyebrow">Kesehatan data rumah sakit</div>
          <div className="score-card-body">
            <ScoreRing score={t.quality_score} />
            <div>
              <div className={`verdict tone-text-${verdict.tone}`}>{verdict.label}</div>
              <p className="muted">
                Ada {formatNumber(t.issues)} hal yang perlu dirapikan, misalnya NIK kosong atau kode yang belum
                standar.
              </p>
              <a className="link-arrow" href="#/kualitas">
                Lihat apa saja yang perlu diperbaiki <ArrowRight size={16} aria-hidden />
              </a>
            </div>
          </div>
        </Card>

        <Card className="stat-card">
          <div className="card-eyebrow">Pasien terdata</div>
          <div className="big-number">
            <Users size={26} aria-hidden />
            {formatNumber(t.patients)}
          </div>
          <p className="muted">
            Disatukan dari <strong>{formatNumber(t.local_records)}</strong> catatan pasien yang tersebar di{" "}
            {data.sources.length} sistem. <strong>{formatNumber(t.auto_linked)}</strong> catatan berhasil dicocokkan
            otomatis.
          </p>
          <a className="link-arrow" href="#/pasien">
            Cari pasien <ArrowRight size={16} aria-hidden />
          </a>
        </Card>
      </div>

      <h2 className="section-title">Yang perlu dikerjakan</h2>
      {tasks.length === 0 ? (
        <Notice tone="good">Tidak ada pekerjaan tertunda. Semua data sudah rapi.</Notice>
      ) : (
        <div className="task-list">
          {tasks.map((task) => {
            const Icon = task.icon;
            return (
              <a key={task.href} className={`task ${"tone" in task ? "task-bad" : ""}`} href={task.href}>
                <span className="task-icon">
                  <Icon size={22} aria-hidden />
                </span>
                <span className="task-text">
                  <strong>
                    <span className="task-count">{formatNumber(task.count)}</span> {task.title}
                  </strong>
                  <span className="muted">{task.hint}</span>
                </span>
                <span className="btn btn-primary btn-md task-action">
                  {task.action} <ArrowRight size={16} aria-hidden />
                </span>
              </a>
            );
          })}
        </div>
      )}

      <h2 className="section-title">Sistem yang terhubung</h2>
      <div className="source-grid">
        {data.sources.map((s) => {
          const Icon = SOURCE_META[s.code].icon;
          return (
            <a key={s.code} className={`source-tile status-${s.status}`} href="#/sumber">
              <div className="source-tile-head">
                <span className={`source-icon src-${s.code}`}>
                  <Icon size={20} aria-hidden />
                </span>
                <StatusPill status={s.status} />
              </div>
              <strong className="source-tile-name">{s.name}</strong>
              <span className="muted small">{s.description}</span>
              <div className="source-tile-foot">
                <span>
                  <strong>{formatNumber(s.records_today)}</strong> data hari ini
                </span>
                <span className="muted small">Terakhir {timeAgo(s.last_sync_at)}</span>
              </div>
            </a>
          );
        })}
      </div>

      <div className="two-col">
        <Card>
          <h2 className="card-title">Masalah data terbanyak</h2>
          <ul className="problem-list">
            {data.top_problems.map((p) => (
              <li key={p.rule}>
                <a href={`#/kualitas?masalah=${p.rule}`}>
                  <SeverityPill severity={p.severity} />
                  <span className="problem-label">{p.label}</span>
                  <strong className="num">{formatNumber(p.count)}</strong>
                </a>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h2 className="card-title">
            <ClipboardList size={18} aria-hidden /> Aktivitas terbaru
          </h2>
          <ul className="activity">
            {data.activity.map((run) => (
              <li key={run.id}>
                <span className="activity-time">{formatTime(run.finished_at ?? run.started_at)}</span>
                <SourceBadge code={run.source_code} small />
                <span className={`activity-msg ${run.status === "gagal" ? "tone-text-bad" : ""}`}>
                  {run.status === "gagal"
                    ? "Gagal mengambil data"
                    : run.records_new > 0
                      ? `${formatNumber(run.records_new)} data baru masuk`
                      : "Dicek, tidak ada data baru"}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
