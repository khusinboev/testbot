"""
Excel parser for DTM directions.
Reads from:
  - Fanlar_majmuasi_2025-2026.xlsx
  - Ta'lim yo'nalishlari va test fanlari jadvali.xlsx

Avval ikkinchi faylni sinab ko'radi (sifatliroq), agar bo'lmasa birinchisini.
"""

import os
import re
from typing import List, Dict, Optional

try:
    import openpyxl
except ImportError:
    raise ImportError("openpyxl o'rnatilmagan. `pip install openpyxl` qiling.")


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCEL_FILES = [
    os.path.join(BASE_DIR, "Ta'lim yo'nalishlari va test fanlari jadvali.xlsx"),
    os.path.join(BASE_DIR, "Fanlar_majmuasi_2025-2026.xlsx"),
]

# Subject name → subject_id mapping (database/db.py dagi seed_subjects bilan mos)
SUBJECT_MAP = {
    "matematika":                      1,
    "fizika":                          2,
    "kimyo":                           3,
    "biologiya":                       4,
    "tarix":                           5,
    "ona tili":                        6,
    "ona tili va adabiyoti":           6,
    "o'zbek tili va adabiyoti":        6,
    "oʻzbek tili va adabiyoti":        6,
    "adabiyot":                        7,
    "geografiya":                      8,
    "ingliz tili":                     9,
    "chet tili":                       9,
    "nemis tili":                      9,
    "fransuz tili":                    9,
    "rus tili":                        10,
    "rus tili va adabiyoti":           10,
    # Boshqa xorijiy tillar → chet tili
    "qirgʻiz tili va adabiyoti":       9,
    "qozoq tili va adabiyoti":         9,
    "tojik tili va adabiyoti":         9,
    "turkman tili va adabiyoti":       9,
    "qoraqalpoq tili va adabiyoti":    9,
    # Ijodiy imtihon → adabiyot
    "kasbiy (ijodiy imtihon)":         7,
    "kasbiy (ijodiy) imtihon":         7,
    "kasbiy":                          7,
    "huquqshunoslik fanlari":          5,
    "huquqshunoslik":                  5,
}


def get_subject_id(name: str) -> int:
    """Subject nomidan ID qaytaradi. Topilmasa 1 (Matematika) qaytaradi."""
    if not name:
        return 1
    clean = name.lower().strip()
    # To'liq mos
    if clean in SUBJECT_MAP:
        return SUBJECT_MAP[clean]
    # Qisman mos
    for key, sid in SUBJECT_MAP.items():
        if key in clean:
            return sid
    print(f"  [WARN] Noma'lum fan: '{name}' — Matematika (1) deb qabul qilindi")
    return 1


def _clean(val) -> str:
    """Hujayra qiymatini tozalangan stringga o'tkazadi."""
    if val is None:
        return ""
    return str(val).strip()


def _detect_columns(headers: List[str]) -> Dict[str, int]:
    """
    Kolonka nomlaridan kerakli indekslarni aniqlaydi.
    Qaytaradi: {'code': i, 'name': j, 'subject1': k, 'subject2': l}
    """
    mapping = {}
    for i, h in enumerate(headers):
        h_low = h.lower().strip()
        if not h_low:
            continue
        # Kod kolonkasi
        if any(k in h_low for k in ["kod", "code", "raqam", "shifr"]) and "code" not in mapping:
            mapping["code"] = i
        # Nom kolonkasi
        elif any(k in h_low for k in ["nom", "name", "yo'nalish", "yonalish", "mutaxassis"]) and "name" not in mapping:
            mapping["name"] = i
        # 1-fan
        elif any(k in h_low for k in ["1-fan", "fan 1", "subject1", "birinchi fan", "1 fan"]) and "subject1" not in mapping:
            mapping["subject1"] = i
        # 2-fan
        elif any(k in h_low for k in ["2-fan", "fan 2", "subject2", "ikkinchi fan", "2 fan"]) and "subject2" not in mapping:
            mapping["subject2"] = i

    return mapping


def _parse_sheet(ws) -> List[Dict]:
    """
    Bitta sheet dan yo'nalishlarni o'qiydi.
    Kolonkalar avtomatik aniqlanadi.
    """
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # Birinchi 5 qatordan sarlavhani topamiz
    header_row_idx = None
    col_map = {}
    for idx, row in enumerate(rows[:5]):
        headers = [_clean(c) for c in row]
        col_map = _detect_columns(headers)
        if len(col_map) >= 3:  # kamida kod, nom, 1-fan
            header_row_idx = idx
            print(f"  Sarlavha qatori: {idx + 1} | Kolonkalar: {col_map}")
            print(f"  Sarlavhalar: {headers}")
            break

    if header_row_idx is None:
        # Fallback: birinchi qatorni sarlavha deb olamiz, strukturani taxmin qilamiz
        print("  [WARN] Sarlavha aniqlanmadi — manual mapping ishlatiladi")
        col_map = _guess_columns(rows)
        header_row_idx = 0
        if not col_map:
            return []

    directions = []
    seen_codes = set()

    for row in rows[header_row_idx + 1:]:
        if all(c is None or str(c).strip() == "" for c in row):
            continue  # Bo'sh qator

        code    = _clean(row[col_map.get("code", 1)] if col_map.get("code") is not None else "")
        name    = _clean(row[col_map.get("name", 2)] if col_map.get("name") is not None else "")
        subj1   = _clean(row[col_map.get("subject1", 3)] if col_map.get("subject1") is not None else "")
        subj2   = _clean(row[col_map.get("subject2", 4)] if col_map.get("subject2") is not None else "")

        # Kod tekshiruvi — raqamli 8 belgili bo'lishi kerak
        code = re.sub(r'\s+', '', code)
        if not re.match(r'^\d{6,9}$', code):
            continue
        if not name:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)

        directions.append({
            "code":     code,
            "name":     name,
            "subject1": subj1,
            "subject2": subj2,
            "subject1_id": get_subject_id(subj1),
            "subject2_id": get_subject_id(subj2),
        })

    return directions


def _guess_columns(rows: List) -> Dict[str, int]:
    """
    Sarlavha aniqlanmasa, ma'lumot qatorlarini analiz qilib kolonkalarni taxmin qiladi.
    8 xonali raqam → code, qolganlar → name, subject1, subject2.
    """
    for row in rows[:10]:
        for i, cell in enumerate(row):
            val = _clean(cell)
            if re.match(r'^\d{6,9}$', val):
                # i = code, i+1 = name, i+2 = subj1, i+3 = subj2
                return {"code": i, "name": i + 1, "subject1": i + 2, "subject2": i + 3}
    return {}


def parse_directions_from_excel() -> List[Dict]:
    """
    Mavjud Excel fayllardan yo'nalishlarni o'qiydi.
    Ikkinchi fayl (sifatliroq) birinchi bo'lib sinab ko'riladi.
    """
    for filepath in EXCEL_FILES:
        if not os.path.exists(filepath):
            print(f"  [SKIP] Fayl topilmadi: {os.path.basename(filepath)}")
            continue

        print(f"\n📂 O'qilmoqda: {os.path.basename(filepath)}")
        try:
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            all_directions = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                print(f"  Sheet: '{sheet_name}'")
                directions = _parse_sheet(ws)
                print(f"  → {len(directions)} ta yo'nalish topildi")
                all_directions.extend(directions)

            wb.close()

            if all_directions:
                # Kodlar bo'yicha deduplikatsiya
                seen = set()
                unique = []
                for d in all_directions:
                    if d["code"] not in seen:
                        seen.add(d["code"])
                        unique.append(d)
                print(f"  ✅ Jami unikal yo'nalish: {len(unique)}")
                return unique

        except Exception as e:
            print(f"  [ERROR] {os.path.basename(filepath)}: {e}")
            continue

    print("[ERROR] Hech qaysi Excel fayl o'qilmadi.")
    return _fallback_directions()


def _fallback_directions() -> List[Dict]:
    """
    Excel fayllar topilmasa yoki o'qilmasa — minimal test ma'lumotlari.
    Production da bu ishlatilmasligi kerak.
    """
    print("[WARN] Fallback yo'nalishlar ishlatilmoqda — Excel fayllarni tekshiring!")
    return [
        {"code": "60610400", "name": "Dasturiy injiniring",
         "subject1": "Matematika", "subject2": "Fizika",
         "subject1_id": 1, "subject2_id": 2},
        {"code": "60610500", "name": "Sun'iy intellekt",
         "subject1": "Matematika", "subject2": "Fizika",
         "subject1_id": 1, "subject2_id": 2},
        {"code": "60540100", "name": "Matematika",
         "subject1": "Matematika", "subject2": "Fizika",
         "subject1_id": 1, "subject2_id": 2},
        {"code": "60110100", "name": "Pedagogika",
         "subject1": "Tarix", "subject2": "Ona tili va adabiyoti",
         "subject1_id": 5, "subject2_id": 6},
        {"code": "60420100", "name": "Yurisprudensiya",
         "subject1": "Huquqshunoslik fanlari", "subject2": "Chet tili",
         "subject1_id": 5, "subject2_id": 9},
    ]