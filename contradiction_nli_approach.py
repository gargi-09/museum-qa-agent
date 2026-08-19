"""
contradiction_nli_approach.py -- Single-record contradiction detection
using a local NLI (Natural Language Inference) model, full description
text as premise.

Premise: the full description text.
Hypothesis: "This work was created in {structured_year}."
Model judges: does the premise CONTRADICT, ENTAIL, or stay NEUTRAL toward
the hypothesis?

Usage:
    python contradiction_nli_approach.py data/normalized.jsonl
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.ingest import normalize_year
from sentence_transformers import CrossEncoder
import numpy as np


NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-small"
CONTRADICTION_PROB_THRESHOLD = 0.7


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


def softmax(logits):
    exp = np.exp(logits - np.max(logits))
    return exp / exp.sum()


def check_contradiction_nli(record, model, id2label):
    """Returns dict: has_contradiction, contradiction_prob, predicted_label,
    structured_year, hypothesis.
    """
    structured_years = normalize_year(record.get("year_raw") or record.get("year"))
    description = record.get("description") or ""

    if not structured_years or not description:
        return {
            "has_contradiction": False,
            "contradiction_prob": None,
            "predicted_label": None,
            "structured_year": None,
            "hypothesis": None,
        }

    primary_year = structured_years[0]
    hypothesis = f"This work was created in {primary_year}."

    scores = model.predict([(description, hypothesis)])
    probs = softmax(scores[0])
    contradiction_prob = float(probs[0])
    predicted_label = id2label[int(np.argmax(probs))]

    return {
        "has_contradiction": contradiction_prob > CONTRADICTION_PROB_THRESHOLD,
        "contradiction_prob": contradiction_prob,
        "predicted_label": predicted_label,
        "structured_year": primary_year,
        "hypothesis": hypothesis,
    }


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    records = load_records(filepath)
    by_id = {r["id"]: r for r in records}

    print(f"Loading NLI model ({NLI_MODEL_NAME})...")
    model = CrossEncoder(NLI_MODEL_NAME)
    id2label = model.config.id2label
    print(f"Label mapping: {id2label}\n")

    print("=" * 70)
    print("KNOWN TEST CASES")
    print("=" * 70)
    test_ids = {
        "Omer Fast 'The Casting' (real, verified contradiction)": "cma-168184",
        "Bontecou etching (earlier, unrelated lithograph dates in text)": "aic-121177",
        "Witkiewicz photo (photographer's career-period dates in text)": "cma-135997",
        "Red Cloud spoon (depicted historical figure's lifespan in text)": "aic-269668",
        "Baumann painting (site's planting date in text)": "cma-160681",
    }
    for label, rid in test_ids.items():
        r = by_id.get(rid)
        if not r:
            continue
        result = check_contradiction_nli(r, model, id2label)
        print(f"\n{label} [{rid}]")
        print(f"  hypothesis: {result['hypothesis']!r}")
        print(f"  contradiction_prob: {result['contradiction_prob']:.3f}")
        print(f"  predicted label: {result['predicted_label']}")
        print(f"  FLAGGED: {result['has_contradiction']}")

    print("\n" + "=" * 70)
    print("FULL CORPUS SWEEP")
    print("=" * 70)
    print("(may take several minutes on CPU)\n")

    flagged = []
    checked = 0
    for r in records:
        result = check_contradiction_nli(r, model, id2label)
        if result["structured_year"] is None:
            continue
        checked += 1
        if result["has_contradiction"]:
            flagged.append((r["id"], result))

    print(f"Records checked: {checked}")
    print(f"Records flagged as contradictions: {len(flagged)}\n")

    for rid, result in sorted(flagged, key=lambda x: -x[1]["contradiction_prob"])[:30]:
        r = by_id[rid]
        print(f"  {rid} (prob={result['contradiction_prob']:.3f}): {r.get('title')!r}")
        print(f"    structured year: {result['structured_year']}")
        print(f"    description: {r.get('description', '')[:180]!r}")
        print()


if __name__ == "__main__":
    main()