"""
Converts base.jsonl into a single CSV file so you can open it in Excel/Sheets
and visually inspect the corpus directly.

Usage: python jsonl_to_csv.py data/base.jsonl data/base_preview.csv
"""
import json
import csv
import sys


ALL_COLUMNS = [
    "id", "source_format", "extraction_method", "institution", "accession_number",
    "title", "artist", "year_raw", "years", "medium", "dimensions",
    "classification", "description", "image_path", "warnings"
]


def main(in_path, out_path):
    rows = []
    with open(in_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = {}
            for col in ALL_COLUMNS:
                val = r.get(col, "")
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                row[col] = val
            rows.append(row)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    print("Open this file directly in Excel or Google Sheets to browse the corpus visually.")


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "data/base.jsonl"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data/base_preview.csv"
    main(in_path, out_path)