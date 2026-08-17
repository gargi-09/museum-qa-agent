"""
Prints full records for the accession-number duplicate pairs and image-path
duplicate clusters found in the final stress test, so we can see what's
actually going on rather than guessing.

Usage: python inspect_duplicates.py data/base.jsonl
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


def main(filepath):
    records = load_records(filepath)

    print("=" * 80)
    print("ACCESSION NUMBER DUPLICATE PAIRS -- full records")
    print("=" * 80)
    acc_groups = {}
    for r in records:
        key = (r.get("institution"), r.get("accession_number"))
        if r.get("accession_number"):
            acc_groups.setdefault(key, []).append(r)

    dupe_groups = {k: v for k, v in acc_groups.items() if len(v) > 1}
    for key, group in dupe_groups.items():
        print(f"--- {key} ---")
        for r in group:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        print()

    print("=" * 80)
    print("IMAGE PATH DUPLICATE CLUSTERS -- full records")
    print("=" * 80)
    img_groups = {}
    for r in records:
        if r.get("image_path"):
            img_groups.setdefault(r["image_path"], []).append(r)

    img_dupe_groups = {k: v for k, v in img_groups.items() if len(v) > 1}
    for path, group in img_dupe_groups.items():
        print(f"--- image_path={path} ---")
        for r in group:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    main(filepath)