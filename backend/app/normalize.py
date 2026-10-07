"""Tidy identity fields without throwing away the original values."""

import re
from datetime import date, datetime

HONORIFICS = {
    "tn", "ny", "nn", "nona", "an", "by", "bayi", "h", "hj", "dr", "drs", "ir",
    "sdr", "sdri", "ibu", "bu", "bpk", "bapak", "pak", "mr", "mrs", "ms",
}

CITY_ALIASES = {
    "jaktim": "jakarta timur",
    "jakbar": "jakarta barat",
    "jaksel": "jakarta selatan",
    "jakut": "jakarta utara",
    "jakpus": "jakarta pusat",
    "jkt": "jakarta",
    "tangsel": "tangerang selatan",
}


def clean_name(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw.replace("^", " ").lower()
    text = re.sub(r"[.,'`]", "", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = [t for t in text.split() if t not in HONORIFICS]
    return " ".join(tokens)


def display_name(clean: str) -> str:
    return " ".join(part.capitalize() for part in clean.split())


def hl7_name(raw: str) -> str:
    """HL7 names come as FAMILY^GIVEN; turn them into 'GIVEN FAMILY'."""
    parts = raw.split("^")
    if len(parts) >= 2 and parts[1]:
        return f"{parts[1]} {parts[0]}"
    return parts[0]


def clean_nik(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    return digits or None


def nik_is_valid(nik: str | None) -> bool:
    return bool(nik) and len(nik) == 16 and len(set(nik)) > 1


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d", "%d.%m.%Y", "%Y/%m/%d")


def parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def birth_date_problem(birth_date: str | None) -> str | None:
    if not birth_date:
        return "kosong atau formatnya tidak dikenali"
    d = date.fromisoformat(birth_date)
    today = date.today()
    if d > today:
        return "tanggal di masa depan"
    if today.year - d.year > 120:
        return "umur lebih dari 120 tahun"
    return None


def clean_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    elif digits.startswith("8"):
        digits = "0" + digits
    return digits if 9 <= len(digits) <= 13 else None


def clean_sex(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if value in {"l", "m", "1", "laki-laki", "laki", "pria", "male"}:
        return "L"
    if value in {"p", "f", "2", "perempuan", "wanita", "female"}:
        return "P"
    return None


def clean_address(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw.lower()
    text = re.sub(r"\bjl\b\.?", "jalan", text)
    text = re.sub(r"\bkel\b\.?", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [CITY_ALIASES.get(t, t) for t in text.split()]
    return " ".join(" ".join(tokens).split())


def mask_nik(nik: str | None) -> str | None:
    if not nik:
        return None
    if len(nik) < 8:
        return "*" * len(nik)
    return nik[:4] + "*" * (len(nik) - 8) + nik[-4:]


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return phone[:4] + "****" + phone[-3:]
