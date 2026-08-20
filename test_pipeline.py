"""
test_pipeline.py -- TEMPORARY validation script. Wires together retrieval.py, entity_resolution.py, and
contradiction.py into one pipeline, WITHOUT calling the API at all.

PURPOSE: validate that these three modules work correctly TOGETHER before
spending any real tokens on api_client.py / reasoning.py. This prints
exactly what WOULD be sent to Haiku, making it possible to eyeball whether
the assembled context looks sensible before committing to the paid step.

Usage:
    python test_pipeline.py data/normalized.jsonl "your question here"

NOTE ON NAMING: this is deliberately NOT called main.py. The eventual
real main.py will be the top-level entry point that calls
reasoning.answer_question() (once reasoning.py exists), which will in
turn import retrieval.py, entity_resolution.py, contradiction.py, and
api_client.py directly. This script is a temporary stand-in that skips
reasoning.py and api_client.py entirely, purely to validate the first
three modules work together before spending any real tokens.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from retrieval import HybridRetriever, load_records
from entity_resolution import build_entity_groups, summarize_group_for_prompt
from contradiction import check_internal_contradiction


def build_not_recorded_view(record):
    """Converts internal None values into the explicit '[not recorded]'
    marker for anything that would be shown in a prompt -- this is the
    concrete fix for the "model might fill in a gap from general
    knowledge" risk found during data-quality analysis. Kept as a
    separate function here (not baked into ingest.py) since [not recorded]
    is a PROMPT-TIME concern, not a data-storage concern -- internal code
    should keep using None/checking truthiness, only text shown to Haiku
    should use this marker.
    """
    fields = ["title", "artist", "medium", "dimensions", "classification"]
    return {f: (record.get(f) if record.get(f) else "[not recorded]") for f in fields}


def assemble_context_for_question(question, retriever, top_k=10):
    """Runs retrieval -> entity resolution -> contradiction check, and
    returns the assembled context that WOULD be sent to Haiku, without
    ever calling the API.
    """
    candidates, abstain, best_sim, signals = retriever.retrieve(question, top_k=top_k)

    print(f"\n{'='*70}")
    print(f"QUESTION: {question!r}")
    print(f"{'='*70}")
    print(f"Best similarity: {best_sim:.3f}  |  ABSTAIN: {abstain}")

    if abstain:
        print("\n--> Would abstain here. No entity resolution, no contradiction")
        print("    check, no Haiku call -- budget saved on a question the")
        print("    corpus likely can't answer confidently.")
        return {"abstained": True, "context_blocks": []}

    candidate_records = [c["record"] for c in candidates]
    entity_groups = build_entity_groups(candidate_records)

    grouped_ids = set()
    for g in entity_groups:
        grouped_ids.update(m["id"] for m in g["members"])

    context_blocks = []

    print(f"\n--- Entity groups found among {len(candidates)} candidates ---")
    for g in entity_groups:
        summary = summarize_group_for_prompt(g)
        rep = summary["representative"]
        contradiction_result = check_internal_contradiction(rep)

        print(f"\n  Representative: {rep['id']} -- {rep.get('title')!r}")
        print(f"  Group note: {summary['note']}")
        if contradiction_result["has_contradiction"]:
            print(f"    [{rep['id']}] INTERNAL CONTRADICTION: {contradiction_result['matched_sentence']!r}")
            print(f"    [{rep['id']}] conflicting years: {contradiction_result['conflicting_years']} "
                  f"(structured says: {contradiction_result['structured_years']})")

        context_blocks.append({
            "record": build_not_recorded_view(rep),
            "id": rep["id"],
            "group_note": summary["note"],
            "internal_contradiction": contradiction_result if contradiction_result["has_contradiction"] else None,
        })

    print(f"\n--- Ungrouped candidates (no duplicates found) ---")
    for c in candidates:
        r = c["record"]
        if r["id"] in grouped_ids:
            continue
        contradiction_result = check_internal_contradiction(r)
        print(f"\n  {r['id']} -- {r.get('title')!r} (sim={c['dense_similarity']:.3f})")
        if contradiction_result["has_contradiction"]:
            print(f"    [{r['id']}] INTERNAL CONTRADICTION: {contradiction_result['matched_sentence']!r}")
            print(f"    [{r['id']}] conflicting years: {contradiction_result['conflicting_years']} "
                  f"(structured says: {contradiction_result['structured_years']})")

        context_blocks.append({
            "record": build_not_recorded_view(r),
            "id": r["id"],
            "group_note": None,
            "internal_contradiction": contradiction_result if contradiction_result["has_contradiction"] else None,
        })

    print(f"\n--- Final context block count that would go to Haiku: {len(context_blocks)} ---")
    return {"abstained": False, "context_blocks": context_blocks}


def main():
    if len(sys.argv) < 3:
        print('Usage: python main.py <normalized.jsonl> "<question1>" ["<question2>" ...]')
        return

    filepath = sys.argv[1]
    questions = sys.argv[2:]

    records = load_records(filepath)
    print(f"Loaded {len(records)} records")
    retriever = HybridRetriever(records)

    for question in questions:
        assemble_context_for_question(question, retriever)


if __name__ == "__main__":
    main()