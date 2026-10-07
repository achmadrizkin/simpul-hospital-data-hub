import {
  Activity,
  Database,
  Gauge,
  Home,
  Languages,
  Search,
  Siren,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Overview } from "./lib/api";
import { formatDateLong, formatTime } from "./lib/format";
import { useData } from "./lib/hooks";
import { useRoute, type Route } from "./lib/router";
import { Beranda } from "./pages/Beranda";
import { CekGanda } from "./pages/CekGanda";
import { Kualitas } from "./pages/Kualitas";
import { PasienDetail } from "./pages/PasienDetail";
import { PasienList } from "./pages/PasienList";
import { Peringatan } from "./pages/Peringatan";
import { SamakanKode } from "./pages/SamakanKode";
import { SumberData } from "./pages/SumberData";

interface NavItem {
  page: Route["page"];
  href: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  badge?: (o: Overview) => number;
}

const NAV: NavItem[] = [
  { page: "beranda", href: "#/", label: "Beranda", hint: "Ringkasan hari ini", icon: Home },
  { page: "pasien", href: "#/pasien", label: "Cari Pasien", hint: "Riwayat lengkap satu pasien", icon: Search },
  {
    page: "peringatan",
    href: "#/peringatan",
    label: "Peringatan Klinis",
    hint: "Temuan dari data gabungan",
    icon: Siren,
    badge: (o) => o.totals.open_alerts,
  },
  {
    page: "ganda",
    href: "#/ganda",
    label: "Cek Pasien Ganda",
    hint: "Satu orang, banyak catatan",
    icon: UserRoundCheck,
    badge: (o) => o.totals.pending_duplicates,
  },
  {
    page: "kode",
    href: "#/kode",
    label: "Samakan Kode",
    hint: "Singkatan RS ke kode standar",
    icon: Languages,
    badge: (o) => o.totals.unmapped_codes,
  },
  { page: "kualitas", href: "#/kualitas", label: "Kualitas Data", hint: "Apa yang perlu diperbaiki", icon: Gauge },
  { page: "sumber", href: "#/sumber", label: "Sumber Data", hint: "Sistem yang terhubung", icon: Database },
];

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 15000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <div className="topbar-clock">
      <strong>{formatTime(now.toISOString())}</strong>
      <span>{formatDateLong(now)}</span>
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const { data: overview, reload } = useData(api.overview, [], 10000);
  const activePage = route.page === "pasien-detail" ? "pasien" : route.page;

  // Refresh the badges whenever the page changes.
  useEffect(() => {
    reload();
  }, [route, reload]);

  const sourceProblems = overview?.sources.filter((s) => s.status !== "lancar") ?? [];

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Langsung ke isi halaman
      </a>
      <aside className="sidebar">
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden>
            <svg viewBox="0 0 32 32" width="32" height="32">
              <circle cx="7" cy="9" r="3.2" />
              <circle cx="7" cy="23" r="3.2" />
              <circle cx="25" cy="16" r="4.2" />
              <path d="M9.5 10.5 L21 15 M9.5 21.5 L21 17" />
            </svg>
          </span>
          <span>
            <strong>Simpul</strong>
            <small>Satu data pasien</small>
          </span>
        </a>
        <nav aria-label="Menu utama">
          {NAV.map((item) => {
            const Icon = item.icon;
            const count = overview && item.badge ? item.badge(overview) : 0;
            const active = activePage === item.page;
            return (
              <a key={item.page} href={item.href} className={`nav-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
                <Icon size={20} aria-hidden />
                <span className="nav-text">
                  <span className="nav-label">{item.label}</span>
                  <span className="nav-hint">{item.hint}</span>
                </span>
                {count > 0 && (
                  <span className="nav-badge" aria-label={`${count} perlu dicek`}>
                    {count}
                  </span>
                )}
              </a>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <span className="avatar small">RM</span>
            <span>
              <strong>Petugas Rekam Medis</strong>
              <small>{overview?.hospital.name ?? "RS Sehat Sentosa"}</small>
            </span>
          </div>
          <p className="demo-note">Semua data pasien di aplikasi ini adalah data contoh (fiktif).</p>
        </div>
      </aside>

      <div className="main-col">
        <header className="topbar">
          <div className="topbar-hospital">
            <strong>{overview?.hospital.name ?? "RS Sehat Sentosa"}</strong>
            <span>{overview?.hospital.city ?? ""}</span>
          </div>
          <div className="topbar-right">
            {overview && (
              <a href="#/sumber" className={`live-chip ${sourceProblems.length ? "has-problem" : ""}`}>
                <Activity size={16} aria-hidden />
                {sourceProblems.length
                  ? `${sourceProblems.length} sistem bermasalah`
                  : "Semua sistem terhubung"}
              </a>
            )}
            <Clock />
          </div>
        </header>

        <main id="main" className="content">
          {route.page === "beranda" && <Beranda />}
          {route.page === "sumber" && <SumberData onChanged={reload} />}
          {route.page === "pasien" && <PasienList />}
          {route.page === "pasien-detail" && <PasienDetail id={route.id} />}
          {route.page === "peringatan" && <Peringatan onChanged={reload} />}
          {route.page === "ganda" && <CekGanda onChanged={reload} />}
          {route.page === "kode" && <SamakanKode onChanged={reload} />}
          {route.page === "kualitas" && <Kualitas rule={route.rule} />}
        </main>
      </div>
    </div>
  );
}
