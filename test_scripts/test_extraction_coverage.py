"""
Tests regex-based field extraction against all semi_structured records,
to determine what fraction can be parsed for free vs. need an LLM fallback.

This directly informs the cost/scalability tradeoff for ingestion.

Usage: python test_extraction_coverage.py data/base.jsonl
"""
import json
import re
import sys


YEAR_TOKEN = re.compile(
    r'(c\.\s*)?\d{3,4}(/\d{2,4})?([\u2013\-]\d{2,4})?'
    r'(,\s*printed\s*(c\.\s*)?\d{3,4}([\u2013\-]\d{2,4})?)?'
    r'(\s*or\s*\d{3,4})?'
)


def try_labeled_extraction(raw_text):
    """Pattern A: 'LABEL: value' lines (e.g. TITLE: ..., ARTIST: ...)
    Guards against empty-value fields being silently merged with the next label's line.
    """
    pattern = re.compile(r'^([A-Z][A-Z ]+):[ \t]*(.*)$', re.MULTILINE)
    matches = pattern.findall(raw_text)
    if len(matches) < 3:
        return None
    result = {}
    for k, v in matches:
        key = k.strip().lower()
        value = v.strip()
        result[key] = value if value else None  # explicit None, never silently merged
    return result


def try_narrative_extraction(raw_text, accession_number):
    """Pattern B: 'Title, Artist, Year. Medium/dims. Accession NUM. Description...'
    FIXED: locates the year via regex first (robust to titles containing commas),
    then splits title/artist on the LAST comma before the year, rather than assuming
    a fixed comma position. This avoids misattributing part of a comma-containing
    title to the artist field.
    """
    if not accession_number:
        return None
    anchor = None
    for candidate in [f"Accession {accession_number}.", f"Accession {accession_number}"]:
        if candidate in raw_text:
            anchor = candidate
            break
    if not anchor:
        return None

    parts = raw_text.split(anchor, 1)
    if len(parts) != 2:
        return None
    metadata_block, description = parts[0].strip(), parts[1].strip()

    year_match = YEAR_TOKEN.search(metadata_block)
    if not year_match:
        return None

    text_before_year = metadata_block[:year_match.start()].rstrip(", ")
    year = year_match.group().strip()
    medium_and_dims = metadata_block[year_match.end():].lstrip(". ").strip()

    if "," in text_before_year:
        title, artist = text_before_year.rsplit(",", 1)
        title, artist = title.strip(), artist.strip()
    else:
        title, artist = text_before_year.strip(), None

    if not title:
        return None

    return {
        "title": title,
        "artist": artist,
        "year": year,
        "medium_and_dimensions": medium_and_dims,
        "description": description,
    }


def try_newline_extraction(raw_text, accession_number):
    """Pattern C: newline-delimited narrative
    Artist\nTitle (Year info)\nMedium; dims\nInstitution, acc. NUM\n\nDescription
    Anchors on the KNOWN accession number, same reliable trick as Pattern B.
    """
    if not accession_number:
        return None
    anchor_pattern = re.compile(
        rf"^(.*?),\s*acc\.\s*{re.escape(accession_number)}\s*\n\n(.*)$",
        re.DOTALL
    )
    m = anchor_pattern.search(raw_text)
    if not m:
        return None
    metadata_block, description = m.group(1), m.group(2)

    lines = [l for l in metadata_block.split("\n") if l.strip()]
    if len(lines) < 3:
        return None

    artist = lines[0].strip()
    title_year_line = lines[1].strip()

    year_match = re.search(r"\(([^)]+)\)\s*$", title_year_line)
    year = year_match.group(1) if year_match else None
    title = (title_year_line[:year_match.start()].strip().rstrip(",")
             if year_match else title_year_line)

    medium_and_dims = " ".join(l.strip() for l in lines[2:])

    return {
        "artist": artist,
        "title": title,
        "year": year,
        "medium_and_dimensions": medium_and_dims,
        "description": description.strip(),
    }


import random

def main(filepath):
    random.seed(42)  # reproducible sampling across runs
    semi_records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("format") == "semi_structured":
                semi_records.append(r)

    labeled_success = 0
    narrative_success = 0
    newline_success = 0
    failures = []
    labeled_matches = []
    narrative_matches = []
    newline_matches = []
    ambiguous = []  # records that match MORE than one pattern independently

    for r in semi_records:
        raw_text = r.get("raw_text", "")
        acc = r.get("accession_number")

        a = try_labeled_extraction(raw_text)
        b = try_narrative_extraction(raw_text, acc)
        c = try_newline_extraction(raw_text, acc)

        matched_patterns = [name for name, res in [("A", a), ("B", b), ("C", c)] if res]
        if len(matched_patterns) > 1:
            ambiguous.append((r["id"], matched_patterns))

        # Cascade: first non-None wins (same behavior as before)
        if a:
            labeled_success += 1
            labeled_matches.append((r["id"], raw_text, a))
        elif b:
            narrative_success += 1
            narrative_matches.append((r["id"], raw_text, b))
        elif c:
            newline_success += 1
            newline_matches.append((r["id"], raw_text, c))
        else:
            failures.append(r)

    print(f"Records matching MORE THAN ONE pattern independently: {len(ambiguous)}")
    if ambiguous:
        print("  (This means pattern order matters for these records — worth inspecting)")
        for rid, patterns in ambiguous[:10]:
            print(f"    {rid}: matched {patterns}")
    print()

    # Random sample of 5 from ALL matches per pattern, not just the first 5 encountered
    labeled_samples = random.sample(labeled_matches, min(5, len(labeled_matches)))
    narrative_samples = random.sample(narrative_matches, min(5, len(narrative_matches)))
    newline_samples = random.sample(newline_matches, min(5, len(newline_matches)))

    total = len(semi_records)
    print(f"Total semi_structured records: {total}")
    print(f"  Matched labeled pattern (A):   {labeled_success} ({labeled_success/total*100:.1f}%)")
    print(f"  Matched narrative pattern (B): {narrative_success} ({narrative_success/total*100:.1f}%)")
    print(f"  Matched newline pattern (C):   {newline_success} ({newline_success/total*100:.1f}%)")
    print(f"  FAILED all three (need LLM fallback): {len(failures)} ({len(failures)/total*100:.1f}%)")
    print()

    def print_verification_samples(label, samples):
        print("=" * 80)
        print(f"VERIFICATION SAMPLES: {label} (raw_text vs extracted, check correctness by eye)")
        print("=" * 80)
        for rid, raw_text, extracted in samples:
            print(f"--- id={rid} ---")
            print(f"RAW: {raw_text[:400]!r}")
            print(f"EXTRACTED: {json.dumps(extracted, ensure_ascii=False)}")
            print()

    print_verification_samples("Pattern A (labeled)", labeled_samples)
    print_verification_samples("Pattern B (comma narrative)", narrative_samples)
    print_verification_samples("Pattern C (newline narrative)", newline_samples)
    print()

    if failures:
        print("Sample of up to 5 failures (raw_text, truncated to 300 chars):")
        for r in failures[:5]:
            print(f"  id={r['id']}: {r.get('raw_text', '')[:300]!r}")
            print()

    est_tokens_per_call = 400
    est_total = len(failures) * est_tokens_per_call
    print(f"Estimated token cost if only failures need an LLM call: "
          f"~{len(failures)} records x ~{est_tokens_per_call} tokens = ~{est_total} tokens "
          f"({est_total / 200000 * 100:.2f}% of the 200k budget)")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)