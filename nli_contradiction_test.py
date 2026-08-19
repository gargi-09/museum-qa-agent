"""
nli_contradiction_test.py -- MINI version of the NLI-based generalization
discussed as a scalability upgrade for contradiction.py's phrase-gate.

WHAT THIS TESTS: the phrase-gate in contradiction.py only catches
contradictions worded using 3 specific, hand-verified phrases ("at odds
with", "discrepancy", "some years after the date carried here"). This
script tests whether that's actually missing real contradictions phrased
differently, by using a small, free, local NLI (Natural Language
Inference) model to judge candidate sentences WITHOUT requiring any exact
phrase match at all.

Uses sentence-transformers' CrossEncoder (same library already installed
for bge-small embeddings -- no new dependency, just a new model download,
~140MB, one-time, cached like everything else).

METHODOLOGY:
1. Find every sentence in a description that mentions a year NOT in the
   record's own structured year field (regardless of phrase-gate match).
2. Build a premise from the structured field ("This work was created in
   {year}.") and treat the candidate sentence as the hypothesis.
3. Ask the NLI model: does this sentence CONTRADICT the premise?
4. Compare against the phrase-gate's existing 35 results:
   - Does NLI independently agree on those 35? (cross-validation)
   - Does NLI find genuinely NEW contradictions the phrase-gate missed?
   - Does NLI correctly REJECT known false positives (e.g. the Bontecou
     record mentioning earlier, unrelated lithograph dates for context)?

Usage:
    pip install sentence-transformers  (already installed if you did the
    embedding model test earlier)
    python nli_contradiction_test.py data/normalized.jsonl
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.ingest import normalize_year
from sentence_transformers import CrossEncoder


NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-small"
CONTRADICTION_THRESHOLD = 0.7  # per the suggested architecture; not yet tuned


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


def build_candidates(record):
    """Finds sentences in the description mentioning a year NOT in the
    structured field -- NO phrase-gate applied here, deliberately, since
    the whole point is testing whether NLI can judge these WITHOUT
    requiring an exact phrase match.
    """
    structured_years = set(normalize_year(record.get("year_raw") or record.get("year")))
    description = record.get("description") or ""
    if not structured_years or not description:
        return [], structured_years

    sentences = re.split(r"(?<=[.!?])\s+", description)
    candidates = []
    for sent in sentences:
        years_in_sentence = set(normalize_year(sent))
        conflicting = years_in_sentence - structured_years
        if conflicting:
            candidates.append((sent.strip(), sorted(conflicting)))
    return candidates, structured_years


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    records = load_records(filepath)
    by_id = {r["id"]: r for r in records}

    print(f"Loading NLI model ({NLI_MODEL_NAME})...")
    model = CrossEncoder(NLI_MODEL_NAME)

    print("\nModel label configuration (VERIFY THIS before trusting results below):")
    try:
        print(f"  {model.config.id2label}")
    except Exception as e:
        print(f"  Could not read id2label automatically: {e}")
        print("  Proceeding with common convention: [contradiction, entailment, neutral]")

    print("\n" + "=" * 70)
    print("STEP 1: Cross-validation against KNOWN cases")
    print("=" * 70)

    known_cases = {
        "TRUE POSITIVE (phrase-gate caught this, Omer Fast)": "cma-168184",
        "KNOWN FALSE POSITIVE if naive (Bontecou -- mentions EARLIER, "
        "unrelated lithograph dates for context, not a real contradiction)": "aic-121177",
    }

    for label, rid in known_cases.items():
        record = by_id.get(rid)
        if not record:
            continue
        candidates, structured_years = build_candidates(record)
        primary_year = sorted(structured_years)[0] if structured_years else None
        premise = f"This work was created in {primary_year}."

        print(f"\n--- {label}: {rid} ---")
        print(f"  Premise: {premise!r}")
        if not candidates:
            print("  No candidate sentences with a conflicting year found.")
            continue
        for sent, conflicting in candidates:
            scores = model.predict([(premise, sent)])
            print(f"  Candidate sentence: {sent[:120]!r}...")
            print(f"  Conflicting year(s) in sentence: {conflicting}")
            print(f"  Raw NLI scores: {scores}")
            print()

    print("=" * 70)
    print("STEP 2: Full corpus -- does NLI find NEW contradictions the")
    print("phrase-gate missed? (This directly tests the scalability concern.)")
    print("=" * 70)
    print("(This may take a few minutes on CPU)\n")

    from src.contradiction import check_internal_contradiction
    phrase_gate_flagged = set(
        r["id"] for r in records if check_internal_contradiction(r)["has_contradiction"]
    )

    new_findings = []
    checked = 0
    for r in records:
        candidates, structured_years = build_candidates(r)
        if not candidates:
            continue
        checked += 1
        primary_year = sorted(structured_years)[0]
        premise = f"This work was created in {primary_year}."
        for sent, conflicting in candidates:
            scores = model.predict([(premise, sent)])
            contradiction_score = float(scores[0][0])
            if contradiction_score > CONTRADICTION_THRESHOLD and r["id"] not in phrase_gate_flagged:
                new_findings.append((r["id"], sent, conflicting, contradiction_score))
                break

    print(f"Records checked (had at least one candidate sentence): {checked}")
    print(f"Records already flagged by phrase-gate: {len(phrase_gate_flagged)}")
    print(f"NEW records flagged by NLI, NOT caught by phrase-gate: {len(new_findings)}")
    print()
    for rid, sent, conflicting, score in new_findings[:15]:
        print(f"  {rid} (score={score:.3f}): {sent[:150]!r}")
        print(f"    conflicting years: {conflicting}")
        print()


if __name__ == "__main__":
    main()