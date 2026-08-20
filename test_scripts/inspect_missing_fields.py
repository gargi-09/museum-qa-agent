"""
Prints full raw records for the actual gap cases we've been reasoning about,
so we look at real data instead of assumptions.

Usage: python inspect_missing_fields.py data/base.jsonl
"""
import json
import sys


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


def print_full(r):
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print("-" * 80)


def main(filepath):
    records = load_records(filepath)
    structured = [r for r in records if r.get("format") == "structured"]

    print("=" * 80)
    print("SAMPLE: structured records with EMPTY artist field (n=5)")
    print("=" * 80)
    empty_artist = [r for r in structured if not (r.get("artist") or "").strip()]
    print(f"Total: {len(empty_artist)}")
    for r in empty_artist[:5]:
        print_full(r)

    print("=" * 80)
    print("SAMPLE: structured records with EMPTY dimensions field (n=5)")
    print("=" * 80)
    empty_dims = [r for r in structured if not (r.get("dimensions") or "").strip()]
    print(f"Total: {len(empty_dims)}")
    for r in empty_dims[:5]:
        print_full(r)

    print("=" * 80)
    print("SAMPLE: structured records with EMPTY classification field (n=5)")
    print("=" * 80)
    empty_class = [r for r in structured if not (r.get("classification") or "").strip()]
    print(f"Total: {len(empty_class)}")
    for r in empty_class[:5]:
        print_full(r)


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)