"""
Data quality analysis for the CORTEX take-home museum corpus.
Run it for base.jsonl.

Usage: python analyze_corpus.py data/base.jsonl
"""
import json
import re
import sys
from collections import Counter, defaultdict


def analyze(filepath):
    records = []
    parse_errors = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                parse_errors.append((line_num, str(e)))

    print(f"Total lines processed: {line_num}")
    print(f"Successfully parsed: {len(records)}")
    print(f"Parse errors: {len(parse_errors)}")
    if parse_errors:
        print("  First few parse errors:")
        for ln, err in parse_errors[:5]:
            print(f"    line {ln}: {err}")
    print()

    # Field presence / missingness / emptiness
    all_fields = set()
    for r in records:
        all_fields.update(r.keys())

    print(f"All fields seen: {sorted(all_fields)}")
    print()

    field_stats = defaultdict(lambda: {"missing": 0, "null": 0, "empty_string": 0, "present": 0})
    for r in records:
        for field in all_fields:
            if field not in r:
                field_stats[field]["missing"] += 1
            elif r[field] is None:
                field_stats[field]["null"] += 1
            elif isinstance(r[field], str) and r[field].strip() == "":
                field_stats[field]["empty_string"] += 1
            else:
                field_stats[field]["present"] += 1

    print("Field completeness report:")
    print(f"{'field':<20}{'present':>10}{'missing':>10}{'null':>10}{'empty_str':>12}")
    for field in sorted(all_fields):
        s = field_stats[field]
        print(f"{field:<20}{s['present']:>10}{s['missing']:>10}{s['null']:>10}{s['empty_string']:>12}")
    print()

    # Institution breakdown + id prefix cross-check
    inst_counter = Counter(r.get("institution", "MISSING") for r in records)
    print(f"Institution breakdown: {dict(inst_counter)}")

    prefix_mismatch = []
    for r in records:
        rid = r.get("id", "")
        inst = r.get("institution", "")
        prefix = rid.split("-")[0] if "-" in rid else ""
        expected = {"aic": "Art Institute of Chicago", "cma": "Cleveland Museum of Art"}.get(prefix)
        if expected and inst and expected != inst:
            prefix_mismatch.append((rid, inst))
    print(f"ID-prefix vs institution mismatches: {len(prefix_mismatch)}")
    if prefix_mismatch:
        print(f"  Examples: {prefix_mismatch[:5]}")
    print()

    # format field values
    format_counter = Counter(r.get("format", "MISSING") for r in records)
    print(f"'format' field value distribution: {dict(format_counter)}")
    print()

    # year field format chaos
    year_patterns = {
        "plain_4digit": re.compile(r"^\d{4}$"),
        "range_dash": re.compile(r"^\d{4}[\u2013\-]\d{2,4}$"),
        "circa": re.compile(r"^c\.\s*\d{4}"),
        "parenthetical": re.compile(r"\(.*\)"),
        "no_digits": re.compile(r"^[^\d]*$"),
    }
    year_pattern_counts = Counter()
    for r in records:
        y = r.get("year")
        if not y:
            year_pattern_counts["missing_or_empty"] += 1
            continue
        matched_any = False
        for name, pat in year_patterns.items():
            if pat.search(y):
                year_pattern_counts[name] += 1
                matched_any = True
        if not matched_any:
            year_pattern_counts["other_unclassified"] += 1

    print(f"'year' field pattern distribution (non-exclusive categories): {dict(year_pattern_counts)}")
    print()

    # image_path stats
    has_image = sum(1 for r in records if r.get("image_path"))
    print(f"Records with image_path: {has_image} / {len(records)} ({has_image/len(records)*100:.1f}%)")
    print()

    # description length stats
    desc_lengths = [len(r.get("description") or "") for r in records]
    desc_lengths_nonzero = [l for l in desc_lengths if l > 0]
    zero_desc = sum(1 for l in desc_lengths if l == 0)
    print(f"Records with empty/missing description: {zero_desc}")
    if desc_lengths_nonzero:
        print(f"Description length — min: {min(desc_lengths_nonzero)}, "
              f"max: {max(desc_lengths_nonzero)}, "
              f"avg: {sum(desc_lengths_nonzero)/len(desc_lengths_nonzero):.0f}")
    print()

    # classification field distribution (top values)
    class_counter = Counter(r.get("classification", "MISSING") for r in records)
    print(f"Top 15 'classification' values:")
    for val, count in class_counter.most_common(15):
        print(f"  {val!r}: {count}")
    print()

    # duplicate title check (rough entity-resolution signal)
    title_counter = Counter((r.get("title") or "").strip().lower() for r in records)
    dupes = {t: c for t, c in title_counter.items() if c > 1 and t}
    print(f"Exact-duplicate titles (rough signal, not true entity resolution): {len(dupes)}")
    if dupes:
        sample_dupes = list(dupes.items())[:5]
        print(f"  Examples: {sample_dupes}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    analyze(filepath)