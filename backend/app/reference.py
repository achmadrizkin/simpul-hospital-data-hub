"""Reference code sets (small subsets for the demo) and the starter dictionary.

dx  -> ICD-10 (WHO)
lab -> LOINC
obat -> ATC (WHO)
"""

ICD10 = {
    "E11.9": "Diabetes melitus tipe 2 tanpa komplikasi",
    "E11.6": "Diabetes melitus tipe 2 dengan komplikasi lain",
    "I10": "Hipertensi esensial (primer)",
    "J06.9": "Infeksi saluran napas atas akut (ISPA)",
    "A09": "Diare dan gastroenteritis infeksi",
    "A91": "Demam berdarah dengue",
    "I50.0": "Gagal jantung kongestif",
    "A15.0": "Tuberkulosis paru",
    "I63.9": "Infark serebral (stroke)",
    "K30": "Dispepsia fungsional",
    "J45.9": "Asma",
    "N39.0": "Infeksi saluran kemih",
    "E78.5": "Hiperlipidemia",
    "R50.9": "Demam, tidak spesifik",
    "K29.7": "Gastritis",
    "M54.5": "Nyeri punggung bawah",
    "R42": "Pusing dan vertigo",
    "R51": "Sakit kepala",
}

LOINC = {
    "2339-0": ("Glukosa darah sewaktu", "mg/dL"),
    "1558-6": ("Glukosa darah puasa", "mg/dL"),
    "4548-4": ("HbA1c", "%"),
    "718-7": ("Hemoglobin", "g/dL"),
    "6690-2": ("Leukosit", "10^3/uL"),
    "777-3": ("Trombosit", "10^3/uL"),
    "2093-3": ("Kolesterol total", "mg/dL"),
    "2571-8": ("Trigliserida", "mg/dL"),
    "3094-0": ("Ureum (BUN)", "mg/dL"),
    "2160-0": ("Kreatinin", "mg/dL"),
    "1920-8": ("SGOT (AST)", "U/L"),
    "1742-6": ("SGPT (ALT)", "U/L"),
}

ATC = {
    "A10BA02": "Metformin",
    "C08CA01": "Amlodipin",
    "N02BE01": "Parasetamol",
    "J01CA04": "Amoksisilin",
    "C03CA01": "Furosemid",
    "A02BC01": "Omeprazol",
    "A10AE04": "Insulin glargine",
    "C09AA01": "Kaptopril",
    "C10AA01": "Simvastatin",
    "J01DD04": "Seftriakson",
    "R03AC02": "Salbutamol",
    "A07CA": "Oralit",
    "R06AE07": "Setirizin",
    "A02BA02": "Ranitidin",
}

SYSTEM_LABELS = {
    "dx": ("Diagnosis", "ICD-10"),
    "lab": ("Pemeriksaan lab", "LOINC"),
    "obat": ("Obat", "ATC"),
}


def std_text(system: str, code: str | None) -> str | None:
    if not code:
        return None
    if system == "dx":
        return ICD10.get(code)
    if system == "lab":
        item = LOINC.get(code)
        return item[0] if item else None
    if system == "obat":
        return ATC.get(code)
    return None


def catalog(system: str) -> list[tuple[str, str]]:
    if system == "dx":
        return list(ICD10.items())
    if system == "lab":
        return [(code, name) for code, (name, _unit) in LOINC.items()]
    if system == "obat":
        return list(ATC.items())
    return []


# Local codes the hospital already agreed on in an earlier project: applied automatically.
STARTER_DICTIONARY = {
    "dx": {
        "DM2": "E11.9",
        "HT": "I10",
        "ISPA": "J06.9",
        "GEA": "A09",
        "DHF": "A91",
        "CHF": "I50.0",
        "TB": "A15.0",
        "ASMA": "J45.9",
    },
    "lab": {
        "GDS": "2339-0",
        "GDP": "1558-6",
        "HB": "718-7",
        "LEU": "6690-2",
        "TROMBO": "777-3",
        "KOL": "2093-3",
        "UREUM": "3094-0",
        "KREA": "2160-0",
        "HBA1C": "4548-4",
    },
    "obat": {
        "Mtf 500": "A10BA02",
        "Amlo 10": "C08CA01",
        "PCT 500": "N02BE01",
        "Amox 500": "J01CA04",
        "Captopril 25": "C09AA01",
        "Oralit": "A07CA",
    },
}

# Abbreviations Simpul recognises but a person still has to confirm.
KNOWN_ABBREVIATIONS = {
    "dx": {
        "DISP": "K30",
        "OBS FEBRIS": "R50.9",
        "DISLIP": "E78.5",
        "GASTRITIS": "K29.7",
        "LBP": "M54.5",
        "ISK": "N39.0",
        "DM2 KOMPL": "E11.6",
    },
    "lab": {
        "TG": "2571-8",
        "SGOT": "1920-8",
        "SGPT": "1742-6",
    },
    "obat": {
        "Furo inj": "C03CA01",
        "Omz 20": "A02BC01",
        "Lantus": "A10AE04",
        "Simva 20": "C10AA01",
        "Cefx 1g": "J01DD04",
        "Salbu 2": "R03AC02",
        "Cetirizine 10": "R06AE07",
    },
}
