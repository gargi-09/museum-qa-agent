import json

ids_to_check = [
      "cma-117571",
      "aic-244616",
      "cma-306684",
      "cma-112094",
      "aic-122230",
      "aic-238522",
      "aic-244077"
]

with open('data/base.jsonl', 'r', encoding='utf-8') as f:
    records = [json.loads(l) for l in f if l.strip()]
by_id = {r['id']: r for r in records}

for rid in ids_to_check:
    r = by_id.get(rid)
    print(f"=== {rid} (RAW, from base.jsonl) ===")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print()