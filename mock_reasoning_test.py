"""
mock_reasoning_test.py -- Tests the FULL reasoning.py pipeline end-to-end
WITHOUT any real API credentials or network calls, by replacing
call_haiku() with a fake function that returns hand-crafted responses.

WHAT STAYS REAL: retrieval (BM25 + embeddings), entity resolution,
contradiction detection, prompt assembly, response parsing, the
verification suite, provenance tracking, confidence scoring -- all of
this is the actual pipeline code, running for real.

WHAT'S FAKED: only the network call itself. This crafts the exact JSON
string Haiku would have returned, for several deliberate scenarios
(a clean answer, a fabricated citation, a not-recorded violation, a
wrong year, a missing exclusion reason) -- so the verification suite
can be seen catching each one, on purpose, before spending a real token.

Usage: python mock_reasoning_test.py data/normalized.jsonl
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import reasoning
from retrieval import HybridRetriever, load_records


def make_fake_haiku_result(content_dict):
    """Builds a fake call_haiku() return value, matching the exact shape
    the real function returns, with content pre-serialized to JSON like
    a real response would be.
    """
    return {
        "content": json.dumps(content_dict),
        "usage": {"input_tokens": 850, "output_tokens": 120},
        "is_truncated": False,
        "truncation_reasons": [],
        "error_type": None,
        "should_retry": False,
        "call_seq": 42,
        "budget_remaining": 199000,
    }


def run_scenario(label, question, retriever, fake_content):
    """Patches reasoning.call_haiku to return the given fake content for
    this one call, runs the real answer_question(), then restores the
    real function.
    """
    original_call_haiku = reasoning.call_haiku

    def fake_call_haiku(messages, max_tokens=600, dev_mode=False,
                         stage="unspecified", expect_json=False, **kwargs):
        return make_fake_haiku_result(fake_content)

    reasoning.call_haiku = fake_call_haiku
    try:
        result = reasoning.answer_question(question, retriever, dev_mode=True)
    finally:
        reasoning.call_haiku = original_call_haiku  # always restore, even on error

    print("=" * 70)
    print(f"SCENARIO: {label}")
    print("=" * 70)
    print(f"Question: {question}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    records = load_records(filepath)
    print(f"Loaded {len(records)} records")
    retriever = HybridRetriever(records)

    question = "What woodblock print depicts an old man from a mountain hut?"

    # First, run retrieval ONCE to find real candidate IDs to use in our
    # fake scenarios below (so the fabricated-citation test uses a REAL
    # record ID that just wasn't retrieved, not a nonsense string).
    candidates, abstain, best_sim, signals = retriever.retrieve(question, top_k=10)
    real_candidate_ids = [c["id"] for c in candidates]
    print(f"Real candidates retrieved for this question: {real_candidate_ids}\n")

    # SCENARIO 1: Clean, correct response -- everything should pass
    run_scenario(
        "1. Clean correct answer -- all verification checks should PASS",
        question, retriever,
        {
            "answer": f"This print, '{records[0].get('title', 'Old Man from the Mountain Hut')}', "
                      f"depicts an old man from a mountain hut.",
            "answerable": True,
            "record_ids_used": [real_candidate_ids[0]],
            "record_ids_excluded": [{"id": real_candidate_ids[1], "reason": "different subject matter"}],
            "limitations": "",
        }
    )

    # SCENARIO 2: Fabricated citation -- citation_membership check should FAIL
    run_scenario(
        "2. FABRICATED CITATION -- citation_membership check should FAIL",
        question, retriever,
        {
            "answer": "This print depicts an old man from a mountain hut.",
            "answerable": True,
            "record_ids_used": [real_candidate_ids[0], "FAKE-ID-DOES-NOT-EXIST-999"],
            "record_ids_excluded": [],
            "limitations": "",
        }
    )

    # SCENARIO 3: Missing exclusion reason -- provenance should flag "NO REASON GIVEN"
    run_scenario(
        "3. NO EXCLUSION REASON GIVEN -- provenance should flag this explicitly",
        question, retriever,
        {
            "answer": "This print depicts an old man from a mountain hut.",
            "answerable": True,
            "record_ids_used": [real_candidate_ids[0]],
            "record_ids_excluded": [],  # deliberately empty, even though other candidates exist
            "limitations": "",
        }
    )

    # SCENARIO 4: Wrong year stated -- factual_match check should FAIL
    real_year = records[0].get("years") if records else None
    run_scenario(
        "4. WRONG YEAR STATED -- factual_match check should FAIL",
        question, retriever,
        {
            "answer": "This print was created in 1850, depicting an old man from a mountain hut.",
            "answerable": True,
            "record_ids_used": [real_candidate_ids[0]],
            "record_ids_excluded": [],
            "limitations": "",
        }
    )

    # SCENARIO 5: Not-answerable case -- the Picasso-style limitation, tested directly
    run_scenario(
        "5. ANSWERABLE=FALSE case -- model correctly declines despite relevant records",
        question, retriever,
        {
            "answer": "The retrieved records describe this print but do not state "
                      "additional biographical opinions requested.",
            "answerable": False,
            "record_ids_used": [real_candidate_ids[0]],
            "record_ids_excluded": [],
            "limitations": "Records are topically related but do not state the specific "
                           "fact requested.",
        }
    )


if __name__ == "__main__":
    main()