"""
CONSOLIDATED final stress test -- combines every data quality check run so far
plus new checks (self-flagged contradiction phrases, cross-institution accession
overlap, medium field gaps). This is the definitive pre-ingest.py quality report.

Usage: python final_stress_test.py data/base.jsonl
"""
import json
import re
import sys
from collections import Counter


KNOWN_FIELDS = {
    "id", "title", "artist", "year", "medium", "dimensions", "classification",
    "institution", "accession_number", "description", "image_path", "format",
    "raw_text"
}

YEAR_4DIGIT = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")

SELF_CONTRADICTION_PHRASES = [
    "at odds with", "some years after the date carried here",
    "discrepancy", "contradicts", "differs from the record",
    "at variance with", "conflicting", "disputed",
]


def load_records(filepath):
    records, errors = [], []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                errors.append((line_num, str(e)))
    return records, errors


def normalize_year(year_str):
    if not year_str or not year_str.strip():
        return []
    return [int(y) for y in YEAR_4DIGIT.findall(year_str)]


def is_mangled_artist(artist_str):
    if not artist_str:
        return False
    if artist_str.count("(") != artist_str.count(")"):
        return True
    if ")" in artist_str and "(" in artist_str:
        if artist_str.index(")") < artist_str.index("("):
            return True
    return False


def main(filepath):
    records, parse_errors = load_records(filepath)
    total = len(records)
    structured = [r for r in records if r.get("format") == "structured"]

    print(f"TOTAL RECORDS: {total}  |  parse errors: {len(parse_errors)}\n")

    print("=" * 70); print("1. DUPLICATE IDs"); print("=" * 70)
    id_counter = Counter(r.get("id") for r in records)
    id_dupes = {k: v for k, v in id_counter.items() if v > 1}
    print(f"Duplicate ids: {len(id_dupes)}\n")

    print("=" * 70); print(f"2. FIELD COMPLETENESS -- structured only (n={len(structured)})"); print("=" * 70)
    for field in ["title", "artist", "year", "medium", "dimensions", "classification", "description"]:
        empty = sum(1 for r in structured if not (r.get(field) or "").strip())
        print(f"  {field:<16} empty/missing: {empty}")
    print()

    print("=" * 70); print("3. WHITESPACE ANOMALIES"); print("=" * 70)
    ws_count = 0
    for r in records:
        for f in ["title", "artist", "description", "raw_text"]:
            val = r.get(f)
            if isinstance(val, str) and val != val.strip():
                ws_count += 1
    print(f"Fields with leading/trailing whitespace: {ws_count}\n")

    print("=" * 70); print("4. ARTIST NAME MANGLING"); print("=" * 70)
    mangled = [(r["id"], r["artist"]) for r in records if is_mangled_artist(r.get("artist"))]
    print(f"Mangled artist fields: {len(mangled)}")
    for rid, a in mangled:
        print(f"  {rid}: {a!r}")
    print()

    print("=" * 70); print("5. YEAR NORMALIZATION COVERAGE"); print("=" * 70)
    all_years = set(r.get("year") for r in records if r.get("year"))
    fails = [y for y in all_years if not normalize_year(y)]
    print(f"Distinct year strings: {len(all_years)}  |  extraction failures: {len(fails)}\n")

    print("=" * 70); print("6. ACCESSION DUPLICATES -- within same institution"); print("=" * 70)
    acc_within = Counter((r.get("institution"), r.get("accession_number")) for r in records
                         if r.get("accession_number"))
    within_dupes = {k: v for k, v in acc_within.items() if v > 1}
    print(f"Duplicate pairs within same institution: {len(within_dupes)}")
    for k in within_dupes:
        print(f"  {k}")
    print()

    print("6b. Accession numbers appearing in BOTH institutions (sanity check)")
    acc_across = {}
    for r in records:
        acc = r.get("accession_number")
        if acc:
            acc_across.setdefault(acc, set()).add(r.get("institution"))
    cross_inst = {k: v for k, v in acc_across.items() if len(v) > 1}
    print(f"Accession numbers shared across institutions: {len(cross_inst)}\n")

    print("=" * 70); print("7. IMAGE PATH DUPLICATES"); print("=" * 70)
    img_counter = Counter(r.get("image_path") for r in records if r.get("image_path"))
    img_dupes = {k: v for k, v in img_counter.items() if v > 1}
    print(f"Shared image paths: {len(img_dupes)}\n")

    print("=" * 70); print("8. INSTITUTION / FORMAT VALUE DRIFT"); print("=" * 70)
    print(f"Institution values: {dict(Counter(r.get('institution') for r in records))}")
    print(f"Format values: {dict(Counter(r.get('format') for r in records))}\n")

    print("=" * 70); print("9. UNEXPECTED SCHEMA KEYS"); print("=" * 70)
    all_keys = set()
    for r in records:
        all_keys.update(r.keys())
    print(f"Unexpected keys: {all_keys - KNOWN_FIELDS or 'none'}\n")

    print("=" * 70); print("10. NEAR-EMPTY RECORDS (<4 non-empty fields)"); print("=" * 70)
    junk = [r["id"] for r in records
            if sum(1 for v in r.values() if v not in (None, "", [])) < 4]
    print(f"Junk records: {len(junk)}\n")

    print("=" * 70); print("11. SELF-FLAGGED CONTRADICTION PHRASES (systematic scan)"); print("=" * 70)
    contradiction_hits = []
    for r in records:
        text = (r.get("description") or "") + " " + (r.get("raw_text") or "")
        text_lower = text.lower()
        for phrase in SELF_CONTRADICTION_PHRASES:
            if phrase in text_lower:
                contradiction_hits.append((r["id"], phrase))
                break
    print(f"Records containing a self-flagged contradiction phrase: {len(contradiction_hits)}")
    for rid, phrase in contradiction_hits[:15]:
        print(f"  {rid}: matched {phrase!r}")
    print()

    print("=" * 70); print("12. MEDIUM FIELD GAPS (structured records)"); print("=" * 70)
    empty_medium = [r for r in structured if not (r.get("medium") or "").strip()]
    print(f"Structured records with empty medium: {len(empty_medium)}")
    for r in empty_medium[:5]:
        print(f"  {r['id']}: title={r.get('title')!r}, classification={r.get('classification')!r}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)