import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock,
  FlaskConical,
  Hospital,
  Info,
  Loader2,
  Minus,
  Pill,
  Receipt,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import type { SourceStatus } from "../lib/api";
import { useStoredFlag } from "../lib/hooks";

/* ---------- sources ---------- */

export const SOURCE_META: Record<string, { icon: LucideIcon; label: string }> = {
  simrs: { icon: Hospital, label: "SIMRS" },
  lis: { icon: FlaskConical, label: "Laboratorium" },
  farmasi: { icon: Pill, label: "Farmasi" },
  billing: { icon: Receipt, label: "Kasir & Tagihan" },
};

const SOURCE_BY_NAME: Record<string, string> = {
  SIMRS: "simrs",
  Laboratorium: "lis",
  Farmasi: "farmasi",
  "Kasir & Tagihan": "billing",
};

export function SourceBadge({ code, name, small }: { code?: string; name?: string; small?: boolean }) {
  const key = code ?? (name ? SOURCE_BY_NAME[name] : undefined) ?? "simrs";
  const meta = SOURCE_META[key];
  const Icon = meta.icon;
  return (
    <span className={`source-badge src-${key} ${small ? "small" : ""}`}>
      <Icon size={small ? 12 : 14} aria-hidden />
      {name ?? meta.label}
    </span>
  );
}

/* ---------- status ---------- */

const STATUS_META: Record<SourceStatus, { label: string; icon: LucideIcon; tone: string; hint: string }> = {
  lancar: { label: "Lancar", icon: CheckCircle2, tone: "good", hint: "Data masuk sesuai jadwal" },
  terlambat: { label: "Terlambat", icon: Clock, tone: "warn", hint: "Data belum masuk sesuai jadwal" },
  gagal: { label: "Gagal terhubung", icon: XCircle, tone: "bad", hint: "Perlu dicek tim IT" },
  belum: { label: "Belum pernah", icon: Minus, tone: "neutral", hint: "Belum pernah mengambil data" },
};

export function StatusPill({ status, large }: { status: SourceStatus; large?: boolean }) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span className={`pill tone-${meta.tone} ${large ? "large" : ""}`} title={meta.hint}>
      <Icon size={large ? 16 : 14} aria-hidden />
      {meta.label}
    </span>
  );
}

export function statusHint(status: SourceStatus) {
  return STATUS_META[status].hint;
}

const SEVERITY_META = {
  tinggi: { label: "Penting", tone: "bad" },
  sedang: { label: "Sedang", tone: "warn" },
  rendah: { label: "Ringan", tone: "neutral" },
} as const;

export function SeverityPill({ severity }: { severity: keyof typeof SEVERITY_META }) {
  const meta = SEVERITY_META[severity];
  return <span className={`pill tone-${meta.tone}`}>{meta.label}</span>;
}

/* ---------- layout pieces ---------- */

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

/** "How to use this page" box. Dismissible, remembered per page. */
export function HowTo({ id, steps }: { id: string; steps: ReactNode[] }) {
  const [open, setOpen] = useStoredFlag(`simpul.howto.${id}`, true);
  if (!open) {
    return (
      <button className="howto-reopen" onClick={() => setOpen(true)}>
        <CircleHelp size={16} aria-hidden /> Tampilkan cara pakai halaman ini
      </button>
    );
  }
  return (
    <section className="howto" aria-label="Cara pakai halaman ini">
      <div className="howto-head">
        <span className="howto-title">
          <CircleHelp size={18} aria-hidden /> Cara pakai
        </span>
        <button className="icon-button" onClick={() => setOpen(false)} aria-label="Sembunyikan cara pakai">
          <X size={16} />
        </button>
      </div>
      <ol className="howto-steps">
        {steps.map((step, i) => (
          <li key={i}>
            <span className="step-no">{i + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Card({ children, className = "", ...rest }: { children: ReactNode; className?: string } & HTMLAttributes<HTMLElement>) {
  return (
    <section className={`card ${className}`} {...rest}>
      {children}
    </section>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
  icon?: LucideIcon;
  busy?: boolean;
  size?: "md" | "lg";
};

export function Button({ variant = "secondary", icon: Icon, busy, size = "md", children, className = "", disabled, ...rest }: ButtonProps) {
  return (
    <button className={`btn btn-${variant} btn-${size} ${className}`} disabled={disabled || busy} {...rest}>
      {busy ? <Loader2 size={18} className="spin" aria-hidden /> : Icon && <Icon size={18} aria-hidden />}
      <span>{children}</span>
    </button>
  );
}

export function Loading({ label = "Memuat data…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <Loader2 size={22} className="spin" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="notice tone-bad" role="alert">
      <AlertTriangle size={20} aria-hidden />
      <div>
        <strong>Data tidak bisa dimuat.</strong> {message}
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Coba lagi
        </Button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "bad" | "good"; children: ReactNode }) {
  const Icon = tone === "good" ? CheckCircle2 : tone === "info" ? Info : AlertTriangle;
  return (
    <div className={`notice tone-${tone}`}>
      <Icon size={20} aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={28} aria-hidden />
      </div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}

/** Small "?" with a plain-language explanation of a technical term. */
export function Term({ children, explain }: { children: ReactNode; explain: string }) {
  return (
    <span className="term" tabIndex={0} title={explain}>
      {children}
      <CircleHelp size={13} aria-hidden />
      <span className="term-tip" role="tooltip">
        {explain}
      </span>
    </span>
  );
}

/* ---------- score ---------- */

export function scoreVerdict(score: number) {
  if (score >= 90) return { label: "Sangat baik", tone: "good" };
  if (score >= 75) return { label: "Cukup baik", tone: "warn" };
  return { label: "Perlu perhatian", tone: "bad" };
}

export function ScoreRing({ score, size = 132 }: { score: number; size?: number }) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const verdict = scoreVerdict(score);
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-track" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className={`ring-value tone-stroke-${verdict.tone}`}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="score-ring-label">
        <strong>{score}</strong>
        <span>dari 100</span>
      </div>
    </div>
  );
}

export function Meter({ value, tone }: { value: number; tone?: string }) {
  const t = tone ?? scoreVerdict(value).tone;
  return (
    <div className="meter" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className={`meter-fill tone-bg-${t}`} style={{ width: `${Math.max(2, value)}%` }} />
    </div>
  );
}

/* ---------- modal ---------- */

export function Modal({
  title,
  children,
  onClose,
  footer,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.querySelector<HTMLElement>("button, input")?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- toasts ---------- */

interface Toast {
  id: number;
  tone: "good" | "bad" | "info";
  message: ReactNode;
  action?: { label: string; onClick: () => void };
}

const ToastContext = createContext<(t: Omit<Toast, "id">) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((list) => [...list, { ...t, id }]);
    window.setTimeout(() => setToasts((list) => list.filter((x) => x.id !== id)), t.action ? 9000 : 5000);
  }, []);
  const dismiss = (id: number) => setToasts((list) => list.filter((x) => x.id !== id));
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast tone-${t.tone}`}>
            {t.tone === "good" ? <CheckCircle2 size={20} /> : t.tone === "bad" ? <XCircle size={20} /> : <Info size={20} />}
            <div className="toast-msg">{t.message}</div>
            {t.action && (
              <button
                className="toast-action"
                onClick={() => {
                  t.action?.onClick();
                  dismiss(t.id);
                }}
              >
                {t.action.label}
              </button>
            )}
            <button className="icon-button" onClick={() => dismiss(t.id)} aria-label="Tutup pemberitahuan">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
