"""
Stress-test pass: surfaces remaining data quality issues before writing ingest.py.
Checks: duplicate IDs, structured-only field completeness, whitespace/encoding
anomalies, artist-name mangling, and a real year-normalization function tested
against every distinct year string in the corpus.

Usage: python stress_test_quality.py data/base.jsonl
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict


def load_records(filepath):
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# ---------- Year normalization ----------

YEAR_4DIGIT = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")  # any plausible 1000-2099 year


def normalize_year(year_str):
    """Extract ALL plausible 4-digit years found in a messy year string.
    Returns a list (possibly empty) rather than forcing a single value,
    since many records genuinely have multiple relevant dates
    (e.g. 'designed 2005, made 2017', 'printed c. 1936-39').
    """
    if not year_str or not year_str.strip():
        return []
    return [int(y) for y in YEAR_4DIGIT.findall(year_str)]


# ---------- Artist mangling detection ----------

def is_mangled_artist(artist_str):
    if not artist_str:
        return False
    open_count = artist_str.count("(")
    close_count = artist_str.count(")")
    if open_count != close_count:
        return True
    if ")" in artist_str and "(" in artist_str:
        if artist_str.index(")") < artist_str.index("("):
            return True
    return False


def main(filepath):
    records = load_records(filepath)
    total = len(records)
    print(f"Total records loaded: {total}\n")

    # ---------- 1. Duplicate ID check ----------
    id_counter = Counter(r.get("id") for r in records)
    dupes = {rid: count for rid, count in id_counter.items() if count > 1}
    print("=" * 70)
    print("1. DUPLICATE ID CHECK")
    print("=" * 70)
    print(f"Unique ids: {len(id_counter)} / {total} records")
    print(f"Duplicate ids found: {len(dupes)}")
    if dupes:
        print(f"  Examples: {list(dupes.items())[:5]}")
    print()

    # ---------- 2. Structured-only field completeness ----------
    structured = [r for r in records if r.get("format") == "structured"]
    print("=" * 70)
    print(f"2. FIELD COMPLETENESS -- STRUCTURED RECORDS ONLY (n={len(structured)})")
    print("=" * 70)
    fields_to_check = ["title", "artist", "year", "medium", "dimensions",
                        "classification", "description", "image_path"]
    for field in fields_to_check:
        missing = sum(1 for r in structured if field not in r)
        null_count = sum(1 for r in structured if field in r and r[field] is None)
        empty = sum(1 for r in structured if field in r and isinstance(r[field], str) and r[field].strip() == "")
        present = len(structured) - missing - null_count - empty
        print(f"  {field:<16} present={present:>5}  missing_key={missing:>4}  "
              f"null={null_count:>4}  empty_str={empty:>4}")
    print()

    # ---------- 3. Whitespace / encoding anomaly scan ----------
    print("=" * 70)
    print("3. WHITESPACE / ENCODING ANOMALY SCAN")
    print("=" * 70)
    leading_trailing_ws = 0
    double_spaces = 0
    control_chars = 0
    mojibake_suspects = 0
    examples = defaultdict(list)

    for r in records:
        for field in ["title", "artist", "description", "raw_text"]:
            val = r.get(field)
            if not isinstance(val, str) or not val:
                continue
            if val != val.strip():
                leading_trailing_ws += 1
                if len(examples["leading_trailing_ws"]) < 3:
                    examples["leading_trailing_ws"].append((r["id"], field, repr(val[:60])))
            if "  " in val:
                double_spaces += 1
            if any(unicodedata.category(c) == "Cc" and c not in ("\n", "\t", "\r") for c in val):
                control_chars += 1
                if len(examples["control_chars"]) < 3:
                    examples["control_chars"].append((r["id"], field, repr(val[:60])))
            if re.search(r"Ã.|â€.", val):
                mojibake_suspects += 1
                if len(examples["mojibake"]) < 3:
                    examples["mojibake"].append((r["id"], field, repr(val[:60])))

    print(f"Fields with leading/trailing whitespace: {leading_trailing_ws}")
    for ex in examples["leading_trailing_ws"]:
        print(f"  {ex}")
    print(f"Fields with double-spaces: {double_spaces}")
    print(f"Fields with non-standard control characters: {control_chars}")
    for ex in examples["control_chars"]:
        print(f"  {ex}")
    print(f"Fields with likely mojibake (double-encoding artifacts): {mojibake_suspects}")
    for ex in examples["mojibake"]:
        print(f"  {ex}")
    print()

    # ---------- 4. Artist name mangling detection ----------
    print("=" * 70)
    print("4. ARTIST NAME MANGLING DETECTION")
    print("=" * 70)
    mangled = []
    for r in records:
        artist = r.get("artist")
        if artist and is_mangled_artist(artist):
            mangled.append((r["id"], artist))
    print(f"Records with likely mangled artist field: {len(mangled)}")
    for rid, artist in mangled[:10]:
        print(f"  {rid}: {artist!r}")
    print()

    # ---------- 5. Year normalization test against EVERY distinct year string ----------
    print("=" * 70)
    print("5. YEAR NORMALIZATION -- tested against every distinct year value")
    print("=" * 70)
    all_year_strings = set(r.get("year") for r in records if r.get("year"))
    print(f"Distinct non-empty year strings in corpus: {len(all_year_strings)}")

    fail_to_extract_any = []
    multi_year_examples = []
    for y in all_year_strings:
        extracted = normalize_year(y)
        if not extracted:
            fail_to_extract_any.append(y)
        elif len(extracted) > 1 and len(multi_year_examples) < 5:
            multi_year_examples.append((y, extracted))

    print(f"Year strings where normalize_year() extracts ZERO years: {len(fail_to_extract_any)}")
    for y in fail_to_extract_any[:10]:
        print(f"  {y!r}")
    print()
    print(f"Sample of multi-year extractions (expected/correct for disputed dates):")
    for y, extracted in multi_year_examples:
        print(f"  {y!r} -> {extracted}")
    print()

    # ---------- 6. Classification field missing specifically within structured records ----------
    print("=" * 70)
    print("6. CLASSIFICATION FIELD -- missing specifically WITHIN structured records")
    print("=" * 70)
    structured_missing_class = [r for r in structured
                                  if not r.get("classification") or not r.get("classification", "").strip()]
    print(f"Structured records with missing/empty classification: {len(structured_missing_class)}")
    for r in structured_missing_class[:5]:
        print(f"  {r['id']}: title={r.get('title')!r}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)