const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const MONTHS_LONG = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];
const DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];

function parse(value: string): Date {
  return new Date(value.length === 10 ? `${value}T00:00:00` : value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = parse(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatDateLong(value: string | Date): string {
  const d = typeof value === "string" ? parse(value) : value;
  return `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS_LONG[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return "";
  const d = parse(value);
  return `${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return `${formatDate(value)}, ${formatTime(value)}`;
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return "belum pernah";
  const seconds = Math.round((Date.now() - parse(value).getTime()) / 1000);
  if (seconds < 10) return "baru saja";
  if (seconds < 60) return `${seconds} detik lalu`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const days = Math.round(hours / 24);
  return `${days} hari lalu`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("id-ID");
}

export function formatRupiah(value: number): string {
  return `Rp ${Math.round(value).toLocaleString("id-ID")}`;
}

export function sexLabel(sex: string | null | undefined): string {
  if (sex === "L") return "Laki-laki";
  if (sex === "P") return "Perempuan";
  return "Tidak diketahui";
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 11) return "Selamat pagi";
  if (h < 15) return "Selamat siang";
  if (h < 18) return "Selamat sore";
  return "Selamat malam";
}

export function dayKey(value: string): string {
  return value.slice(0, 10);
}
