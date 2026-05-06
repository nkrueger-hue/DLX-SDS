"""
sdsocr.py
---------
OCR-scans a folder of SDS PDFs and stores results in sds.db.

Extracts:
  - revision_date  — via multi-pattern date matching (most-specific first)
  - hazard_codes   — via H-statement mapping, direct GHS codes, and
                     section-scoped / full-doc text phrases

Usage:
    python sdsocr.py [--debug]

Pass --debug to print which extraction step fired for hazards (or why blocked).
"""

import re
import os
import sys
import sqlite3

from pdf2image import convert_from_path
import pytesseract

# ── Config ────────────────────────────────────────────────────────────────────

folder_path = "/Users/nate/Documents/SDS DATABASE/SDS Data Sheets"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "sds.db")
DEBUG    = "--debug" in sys.argv

# ── Date extraction ───────────────────────────────────────────────────────────
#
# Patterns tried in order; first valid match wins.
# Priority:
#   1. Explicit "Revision date" labels  (highest confidence)
#   2. "Date of preparation/revision", "Date prepared"
#   3. "Date of issue / Date of revision"
#   4. "Date of issue" / "Issue date"   (fallback)

_MF = r"January|February|March|April|May|June|July|August|September|October|November|December"
_MA = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"

DATE_PATTERNS = [
    # ── Explicit "Revision date" labels ───────────────────────────────────────

    # "Revision Date: November 13, 2024"
    rf"revision\s+date\s*[:\s]+((?:{_MF})\.?\s+\d{{1,2}},?\s*\d{{4}})",

    # "Revision date: 6/9/2022"  or  "Revision date : 06/09/2022"
    r"revision\s+date\s*[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})(?!\d)",

    # "Revision Date 10/20/2020"  (no colon)
    r"revision\s+date\s+(\d{1,2}/\d{1,2}/\d{2,4})(?!\d)",

    # "Revision Date 19.03.2024"  (European dot-separated)
    r"revision\s+date\s*[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})",

    # "Revision Date 14-Jun-2018"  (abbreviated month, no colon)
    rf"revision\s+date\s+(\d{{1,2}}-(?:{_MA})-\d{{2,4}})",

    # "Revision date: 15-April-2025"  (full month with dash)
    rf"revision\s+date\s*[:\s]+(\d{{1,2}}-(?:{_MF})-\d{{4}})",

    # "Revision date: 11-DEC-2017"  (uppercase abbreviated month)
    r"revision\s+date\s*[:\s]+(\d{1,2}-[A-Z]{3}-\d{4})",

    # ISO: "Revision date: 2023-09-19"
    r"revision\s+date\s*[:\s]+(\d{4}-\d{2}-\d{2})",

    # "Revision: 2021-03-03"  (short label, ISO date)
    r"(?<!\w)revision\s*:\s*(\d{4}-\d{2}-\d{2})",

    # ── "SDS Date of Preparation/Revision: October 21, 2019" ─────────────────
    rf"date\s+of\s+preparation(?:/revision)?\s*[:\s]+((?:{_MF})\.?\s+\d{{1,2}},?\s*\d{{4}})",

    # "Date Prepared: 10/21/2019"
    r"date\s+prepared\s*[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",

    # ── "Date of issue/Date of revision : 4/20/2017" ─────────────────────────
    r"date\s+of\s+(?:issue/date\s+of\s+)?revision\s*[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",

    # ── "Date of issue mm/dd/yyyy : 10/15/2014" ──────────────────────────────
    r"date\s+of\s+(?:issue|last\s+issue)\s*(?:mm/dd/yyyy)?\s*[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",

    # "Date of issue: 2022-05-04"  (ISO)
    r"date\s+of\s+issue\s*[:\s]+(\d{4}-\d{2}-\d{2})",

    # ── "Issue date: 10-22-2019"  (dashes instead of slashes) ────────────────
    r"issue\s+date\s*[:\s]+(\d{1,2}-\d{1,2}-\d{2,4})",

    # ── Fallback: Issue date labels ───────────────────────────────────────────

    # "Issue Date: March 12, 2024"
    rf"issue\s+date\s*[:\s]+((?:{_MF})\.?\s+\d{{1,2}},?\s*\d{{4}})",

    # "Issue Date: 15-April-2025"
    rf"issue\s+date\s*[:\s]+(\d{{1,2}}-(?:{_MF})-\d{{4}})",

    # "Issue date: 1/25/2019"
    r"issue\s+date\s*[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
]

# Reject OCR noise
INVALID_DATE_VALUES = {"-", "--", "mm/dd/yyyy", "dd/mm/yyyy", "n/a", "none", ""}

_MONTHS_ONLY = re.compile(
    r"^(?:January|February|March|April|May|June|July|August"
    r"|September|October|November|December)$", re.IGNORECASE
)


def _is_valid_date(value: str) -> bool:
    """Reject month-only strings and impossible numeric dates."""
    if _MONTHS_ONLY.match(value.strip()):
        return False
    m = re.match(r"(\d{1,2})/(\d{1,2})/\d{2,4}", value)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b > 12:
            return False
        if a > 31 or b > 31:
            return False
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.\d{4}", value)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 31 or b > 12:
            return False
    m = re.match(r"(\d{1,2})-(\d{1,2})-\d{2,4}", value)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b > 12:
            return False
        if a > 31 or b > 31:
            return False
    return True


def extract_revision_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = " ".join(match.group(1).split())   # collapse whitespace/newlines
            if value.lower() not in INVALID_DATE_VALUES and _is_valid_date(value):
                return value
    return None


# ── Hazard extraction ─────────────────────────────────────────────────────────
#
# Strategy (tried in order, first match wins):
#   1. Not-required check          — explicit "no pictogram required" text
#   2. Section H-statements        — H225, H319, etc. anchored to label section
#   3. Section direct GHS codes    — GHS02, GHS07, etc. anchored to label section
#   4. Full-doc H-statement scan   — fallback when label section is blank/absent
#   5. Section text phrases        — descriptive text within label section
#   6. Full-doc text phrases       — fallback using tight safe-only patterns

# H-statement number → GHS pictogram code
H_TO_GHS = {
    # GHS01 — Exploding bomb
    200: "GHS01", 201: "GHS01", 202: "GHS01", 203: "GHS01",
    204: "GHS01", 205: "GHS01", 240: "GHS01", 241: "GHS01",
    # GHS02 — Flame
    220: "GHS02", 221: "GHS02", 222: "GHS02", 223: "GHS02",
    224: "GHS02", 225: "GHS02", 226: "GHS02", 228: "GHS02",
    229: "GHS02", 230: "GHS02", 231: "GHS02", 232: "GHS02",
    242: "GHS02", 250: "GHS02", 251: "GHS02", 252: "GHS02",
    260: "GHS02", 261: "GHS02",
    # GHS03 — Flame over circle (oxidising)
    270: "GHS03", 271: "GHS03", 272: "GHS03",
    # GHS04 — Gas cylinder
    280: "GHS04", 281: "GHS04",
    # GHS05 — Corrosion
    290: "GHS05", 314: "GHS05", 318: "GHS05",
    # GHS06 — Skull & crossbones
    300: "GHS06", 301: "GHS06", 310: "GHS06", 311: "GHS06",
    330: "GHS06", 331: "GHS06",
    # GHS07 — Exclamation mark
    302: "GHS07", 303: "GHS07",
    312: "GHS07", 313: "GHS07",
    315: "GHS07", 316: "GHS07", 317: "GHS07",
    319: "GHS07", 320: "GHS07",
    332: "GHS07", 333: "GHS07",
    335: "GHS07", 336: "GHS07",
    # GHS08 — Health hazard
    304: "GHS08", 334: "GHS08",
    340: "GHS08", 341: "GHS08",
    350: "GHS08", 351: "GHS08",
    360: "GHS08", 361: "GHS08", 362: "GHS08",
    370: "GHS08", 371: "GHS08", 372: "GHS08", 373: "GHS08",
    # GHS09 — Environment
    400: "GHS09", 401: "GHS09", 402: "GHS09", 410: "GHS09",
    411: "GHS09", 412: "GHS09", 413: "GHS09", 420: "GHS09",
}

# Section-scoped text patterns (broader — safe within a narrow window)
TEXT_TO_GHS = [
    (r"\bexplosiv\w*\b",                          "GHS01"),
    (r"\bself.react\w*\b",                        "GHS01"),
    (r"\bflammab\w*\b",                           "GHS02"),
    (r"\bflammib\w*\b",                           "GHS02"),
    (r"\bcombustib\w*\b",                         "GHS02"),
    (r"\bpyrophoric\b",                           "GHS02"),
    (r"\boxidiz\w*\b",                            "GHS03"),
    (r"\boxidis\w*\b",                            "GHS03"),
    (r"\bgas under pressure\b",                   "GHS04"),
    (r"\bcontains gas under pressure\b",          "GHS04"),
    (r"\bcompressed gas\b",                       "GHS04"),
    (r"\bliquefied gas\b",                        "GHS04"),
    (r"\bmay explode if heated\b",                "GHS04"),
    (r"\bsuffocation\b",                          "GHS04"),
    (r"\bcorrosiv\w*\b",                          "GHS05"),
    (r"\bskin burns?\b",                          "GHS05"),
    (r"\bserious eye damage\b",                   "GHS05"),
    (r"\beye damage\b",                           "GHS05"),
    (r"\bfatal\b",                                "GHS06"),
    (r"\bacute tox\w*\b",                         "GHS06"),
    (r"\birritant\b",                             "GHS07"),
    (r"\birritation\b",                           "GHS07"),
    (r"\bharmful\b",                              "GHS07"),
    (r"\bdrowsiness\b",                           "GHS07"),
    (r"\bdizziness\b",                            "GHS07"),
    (r"\brespiratory irritat\w*\b",               "GHS07"),
    (r"\bcarcino\w*\b",                           "GHS08"),
    (r"\bmutageni\w*\b",                          "GHS08"),
    (r"\breproductive tox\w*\b",                  "GHS08"),
    (r"\baspiration\b",                           "GHS08"),
    (r"\bhealth hazard\b",                        "GHS08"),
    (r"\bstot\b",                                 "GHS08"),
    (r"\baquatic\b",                              "GHS09"),
    (r"\benvironmental\b",                        "GHS09"),
    (r"\becotox\w*\b",                            "GHS09"),
]

# Full-document safe text patterns (tight phrases only — avoids boilerplate)
TEXT_TO_GHS_SAFE = [
    (r"\bextremely\s+flammab\w*\b",                             "GHS02"),
    (r"\bhighly\s+flammab\w*\b",                                "GHS02"),
    (r"\bflammable\s+aerosol\b",                                "GHS02"),
    (r"\bflammable\s+(?:liquid|gas|solid)\b",                   "GHS02"),
    (r"\bpyrophoric\b",                                         "GHS02"),
    (r"\bliquefied\s+gas\b",                                    "GHS04"),
    (r"\bcompressed\s+gas\b",                                   "GHS04"),
    (r"\bgas\s+under\s+pressure\b",                             "GHS04"),
    (r"\bcontains\s+gas\s+under\s+pressure\b",                  "GHS04"),
    (r"\bmay\s+explode\s+if\s+heated\b",                        "GHS04"),
    (r"\bcauses?\s+severe\s+skin\s+burns?\b",                   "GHS05"),
    (r"\bcauses?\s+serious\s+eye\s+damage\b",                   "GHS05"),
    (r"\bcorrosiv\w*\s+to\s+metals?\b",                         "GHS05"),
    (r"\bfatal\s+if\s+(?:swallowed|inhaled)\b",                 "GHS06"),
    (r"\btoxic\s+if\s+(?:swallowed|inhaled|in\s+contact)\b",    "GHS06"),
    (r"\bcauses?\s+skin\s+irritation\b",                        "GHS07"),
    (r"\bcauses?\s+(?:serious\s+)?eye\s+irritation\b",          "GHS07"),
    (r"\bharmful\s+if\s+(?:swallowed|inhaled)\b",               "GHS07"),
    (r"\bmay\s+cause\s+respiratory\s+irritation\b",             "GHS07"),
    (r"\bmay\s+cause\s+drowsiness\s+or\s+dizziness\b",          "GHS07"),
    (r"\bmay\s+cause\s+(?:cancer|genetic\s+defects?)\b",        "GHS08"),
    (r"\bsuspected\s+of\s+causing\s+cancer\b",                  "GHS08"),
    (r"\bmay\s+be\s+fatal\s+if\s+swallowed\b",                  "GHS08"),
    (r"\baspiration\s+hazard\b",                                "GHS08"),
    (r"\bmay\s+damage\s+(?:fertility|the\s+unborn\s+child)\b",  "GHS08"),
    (r"\bcauses?\s+damage\s+to\s+organs?\b",                    "GHS08"),
    (r"\bstot\b",                                               "GHS08"),
    (r"\bvery\s+toxic\s+to\s+aquatic\b",                        "GHS09"),
    (r"\btoxic\s+to\s+aquatic\b",                               "GHS09"),
    (r"\bharmful\s+to\s+aquatic\b",                             "GHS09"),
]

# Explicit "no pictogram required" declarations
NOT_REQUIRED_PATTERNS = [
    r"pictograms?\s+(not\s+required|none\s+required|:\s*none)",
    r"no\s+pictogram\s+required",
    r"pictogram[:\s]+none",
    r"pictogram\(s\)\s*\n\s*none",
    r"hazard\s+symbol[^.]{0,20}none\s+required",
    r"no\s+hazards?\s+identified\.?(?:\s|$)",
    r"signal\s+word[:\s]+(?:none|not\s+required)",
]

# Hazard label section anchor
SECTION_PATTERN = re.compile(
    r"(?:"
        r"label\s+elements?"
        r"|ghs\s+label"
        r"|hazard\s+statements?"
        r"|signal\s+word"
        r"|(?:^|\n)\s*(?:Danger|Warning)\s*(?:\n|$)"
    r")"
    r"(.{0,3000}?)"
    r"(?:"
        r"precautionary\s+statements?"
        r"|section\s+3"
        r"|composition"
        r"|first.?aid"
        r"|fire.fighting"
        r"|accidental\s+release"
        r"|handling\s+and\s+storage"
        r"|exposure\s+controls?"
        r"|physical"
        r"|stability"
        r"|toxicological"
        r"|ecological"
        r"|disposal"
        r"|transport"
        r"|\Z"
    r")",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

GLOSSARY_PATTERN = re.compile(
    r"(?:definitions?|glossary|key\s+to\s+abbreviations?|explanation\s+of)"
    r".{0,100}GHS0[1-9]",
    re.IGNORECASE | re.DOTALL,
)


def dbg(file_name: str, msg: str) -> None:
    if DEBUG:
        print(f"      [{file_name}] {msg}")


def strip_glossary(text: str) -> str:
    match = GLOSSARY_PATTERN.search(text)
    return text[:match.start()] if match else text


def extract_hazard_section(text: str) -> str:
    match = SECTION_PATTERN.search(text)
    return match.group(1) if match else ""


def is_not_required(text: str, file_name: str = "") -> bool:
    for pat in NOT_REQUIRED_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            dbg(file_name, f"not-required blocked by pattern {pat!r} → {m.group()!r}")
            return True
    return False


def extract_direct_ghs_codes(text: str) -> list[str]:
    codes = set(re.findall(r"\bGHS0[1-9]\b", text, re.IGNORECASE))
    return sorted(c.upper() for c in codes)


def extract_from_h_statements(text: str) -> list[str]:
    numbers = re.findall(r"\bH(\d{3})\b", text, re.IGNORECASE)
    codes = set()
    for num_str in numbers:
        num = int(num_str)
        if num in H_TO_GHS:
            codes.add(H_TO_GHS[num])
    return sorted(codes)


def extract_from_hazard_text(text: str, safe_only: bool = False) -> list[str]:
    table = TEXT_TO_GHS_SAFE if safe_only else TEXT_TO_GHS
    codes = set()
    for pattern, code in table:
        if re.search(pattern, text, re.IGNORECASE):
            codes.add(code)
    return sorted(codes)


def extract_hazard_codes(text: str, file_name: str = "") -> str | None:
    """
    Returns comma-separated GHS codes or None.

    Priority:
      1. Not-required check (full doc)
      2. H-statements in label section
      3. Direct GHS codes in label section
      4. H-statements in full document
      5. Text phrases in label section
      6. Safe text phrases in full document
    """
    if not text:
        return None

    if is_not_required(text, file_name):
        dbg(file_name, "→ blocked by not-required")
        return None

    section = extract_hazard_section(text)
    dbg(file_name, f"section found: {bool(section)} ({len(section)} chars)")

    if section:
        h = extract_from_h_statements(section)
        if h:
            dbg(file_name, f"step 2 (section H-codes): {h}")
            return ",".join(h)

        d = extract_direct_ghs_codes(section)
        if d:
            dbg(file_name, f"step 3 (section GHS strings): {d}")
            return ",".join(d)

    h_full = extract_from_h_statements(text)
    if h_full:
        dbg(file_name, f"step 4 (full-doc H-codes): {h_full}")
        return ",".join(h_full)

    if section:
        t = extract_from_hazard_text(section, safe_only=False)
        if t:
            dbg(file_name, f"step 5 (section text): {t}")
            return ",".join(t)

    t_full = extract_from_hazard_text(text, safe_only=True)
    if t_full:
        dbg(file_name, f"step 6 (full-doc safe text): {t_full}")
        return ",".join(t_full)

    dbg(file_name, "→ no hazards found")
    return None


# ── OCR ───────────────────────────────────────────────────────────────────────

def ocr_pdf(pdf_path: str) -> str:
    pages     = convert_from_path(pdf_path, 300)
    full_text = ""
    for page in pages:
        full_text += pytesseract.image_to_string(page) + "\n"
    return full_text


# ── Database setup ────────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sds (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name     TEXT,
            content       TEXT,
            revision_date TEXT,
            hazard_codes  TEXT
        )
    """)
    conn.commit()


def already_processed(cursor: sqlite3.Cursor, file_name: str) -> bool:
    cursor.execute("SELECT id FROM sds WHERE file_name = ?", (file_name,))
    return cursor.fetchone() is not None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    total     = len(pdf_files)

    print(f"Found {total} PDFs.\n")

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    init_db(conn)

    success = 0
    failed  = []

    for i, file in enumerate(sorted(pdf_files), start=1):
        pdf_path = os.path.join(folder_path, file)
        prefix   = f"[{i}/{total}]"

        if already_processed(cursor, file):
            print(f"{prefix} Skipped (already saved): {file}")
            success += 1
            continue

        print(f"{prefix} Processing: {file} ...", end=" ", flush=True)

        try:
            text          = ocr_pdf(pdf_path)
            revision_date = extract_revision_date(text)
            hazard_codes  = extract_hazard_codes(text, file_name=file)

            cursor.execute(
                "INSERT INTO sds (file_name, content, revision_date, hazard_codes) "
                "VALUES (?, ?, ?, ?)",
                (file, text, revision_date, hazard_codes)
            )
            conn.commit()

            date_str   = revision_date or "no date found"
            hazard_str = hazard_codes  or "no hazards found"
            print(f"OK  |  date: {date_str}  |  hazards: {hazard_str}")
            success += 1

        except Exception as e:
            print(f"FAILED — {e}")
            failed.append((file, str(e)))

    conn.close()

    print(f"\n── Done ──────────────────────────────────────────")
    print(f"Processed: {success}/{total}")
    if failed:
        print(f"Failed ({len(failed)}):")
        for name, err in failed:
            print(f"  • {name}: {err}")


if __name__ == "__main__":
    main()