"""
Follow-up inspection: semi_structured records, unclassified year formats,
and whether these overlap with missing description/classification.

Usage: python inspect_edge_cases.py data/base.jsonl
"""
import json
import re
import sys


YEAR_PATTERNS = {
    "plain_4digit": re.compile(r"^\d{4}$"),
    "range_dash": re.compile(r"^\d{4}[\u2013\-]\d{2,4}$"),
    "circa": re.compile(r"^c\.\s*\d{4}"),
    "parenthetical": re.compile(r"\(.*\)"),
}


def classify_year(y):
    if not y or not y.strip():
        return "missing_or_empty"
    for name, pat in YEAR_PATTERNS.items():
        if pat.search(y):
            return name
    return "other_unclassified"


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


def main(filepath):
    records = load_records(filepath)

    # --- 1. Semi-structured records ---
    semi = [r for r in records if r.get("format") == "semi_structured"]
    print(f"Total semi_structured records: {len(semi)}")
    print("=" * 80)
    print("First 3 semi_structured records, raw:")
    for r in semi[:3]:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        print("-" * 80)
    print()

    # --- 2. Cross-check: do semi_structured records overlap with missing description/classification? ---
    semi_missing_desc = sum(1 for r in semi if not (r.get("description") or "").strip())
    semi_missing_class = sum(1 for r in semi if not r.get("classification") or r.get("classification") == "MISSING")
    structured = [r for r in records if r.get("format") == "structured"]
    structured_missing_desc = sum(1 for r in structured if not (r.get("description") or "").strip())
    structured_missing_class = sum(1 for r in structured if not r.get("classification") or r.get("classification") == "MISSING")

    print("Cross-check: format vs missing description/classification")
    print(f"  semi_structured ({len(semi)} total): missing description = {semi_missing_desc}, missing classification = {semi_missing_class}")
    print(f"  structured ({len(structured)} total): missing description = {structured_missing_desc}, missing classification = {structured_missing_class}")
    print()

    # --- 3. What fields do semi_structured records actually have, vs structured? ---
    semi_field_sets = set()
    for r in semi:
        present_fields = tuple(sorted(k for k, v in r.items() if v not in (None, "")))
        semi_field_sets.add(present_fields)
    print(f"Distinct 'present field' signatures among semi_structured records: {len(semi_field_sets)}")
    for sig in list(semi_field_sets)[:5]:
        print(f"  {sig}")
    print()

    structured_field_sets = set()
    for r in structured:
        present_fields = tuple(sorted(k for k, v in r.items() if v not in (None, "")))
        structured_field_sets.add(present_fields)
    print(f"Distinct 'present field' signatures among structured records: {len(structured_field_sets)}")
    for sig in list(structured_field_sets)[:5]:
        print(f"  {sig}")
    print()

    # --- 4. Unclassified year samples ---
    unclassified_years = [r.get("year") for r in records if classify_year(r.get("year")) == "other_unclassified"]
    print(f"Total 'other_unclassified' year values: {len(unclassified_years)}")
    print("Sample of 20 unclassified year values:")
    for y in unclassified_years[:20]:
        print(f"  {y!r}")
    print()

    # --- 5. Do unclassified years correlate with semi_structured format? ---
    semi_unclassified_year = sum(1 for r in semi if classify_year(r.get("year")) == "other_unclassified")
    structured_unclassified_year = sum(1 for r in structured if classify_year(r.get("year")) == "other_unclassified")
    print(f"'other_unclassified' year within semi_structured: {semi_unclassified_year} / {len(semi)}")
    print(f"'other_unclassified' year within structured: {structured_unclassified_year} / {len(structured)}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)