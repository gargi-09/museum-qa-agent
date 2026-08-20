"""
Spot-checks the self-flagged contradiction matches that used less common phrases
(conflicting, disputed, discrepancy, at odds with) rather than the repeated stock
phrase, to confirm they're genuine self-referential contradictions.

Usage: python verify_contradictions.py data/base.jsonl
"""
import json
import sys


PHRASES_TO_CHECK = ["conflicting", "disputed", "discrepancy", "at odds with", "at variance with"]


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

    for phrase in PHRASES_TO_CHECK:
        print("=" * 80)
        print(f"PHRASE: {phrase!r}")
        print("=" * 80)
        matches = []
        for r in records:
            text = (r.get("description") or "") + " " + (r.get("raw_text") or "")
            if phrase in text.lower():
                matches.append(r)
        print(f"Total matches: {len(matches)}")
        for r in matches[:3]:
            text = r.get("description") or r.get("raw_text") or ""
            idx = text.lower().find(phrase)
            start = max(0, idx - 150)
            end = min(len(text), idx + 150)
            print(f"  id={r['id']}")
            print(f"  ...{text[start:end]}...")
            print()


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)