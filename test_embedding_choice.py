"""
Empirically tests whether bge-small-en-v1.5's recommended query prefix
("Represent this sentence for searching relevant passages: ") actually
improves retrieval quality on THIS corpus, rather than assuming it does
based on general reputation.

Also compares bge-small against all-MiniLM-L6-v2 directly on the same
test questions, so the model choice is backed by evidence specific to
this task, not just general benchmark reputation.

Setup (run once):
    pip install sentence-transformers numpy

Usage:
    python test_embedding_choice.py data/normalized.jsonl
"""
import json
import sys
import numpy as np
from sentence_transformers import SentenceTransformer


# A small, hand-picked set of (question, expected_record_id) pairs.
# Pick a few real records from your normalized.jsonl, write a natural
# question about each, and fill in the correct id. This gives you real
# ground truth to test against, even though the assignment overall has none.
TEST_CASES = [
    ("What woodblock print depicts an old man from a mountain hut?", "aic-136265"),
    ("Tell me about a Willem de Kooning oil painting called Excavation", "aic-76244"),
    ("What sculpture did Eva Hesse make using fiberglass?", "aic-73423"),
    ("What video installation by Omer Fast is called The Casting?", "cma-168184"),
    ("What lithograph by Helen Frankenthaler is titled I Need Yellow?", "aic-97633"),
    ("What series of etchings did Louise Bourgeois make about her mother?", "cma-160793"),
]


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


def build_passage_text(record):
    """Combines the fields most relevant for semantic matching into one
    passage string per record."""
    parts = [
        record.get("title") or "",
        record.get("artist") or "",
        record.get("medium") or "",
        record.get("description") or "",
    ]
    return " ".join(p for p in parts if p)


def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)


def rank_of_correct(query_embedding, passage_embeddings, ids, correct_id):
    sims = [cosine_sim(query_embedding, pe) for pe in passage_embeddings]
    ranked_ids = [ids[i] for i in np.argsort(sims)[::-1]]
    return ranked_ids.index(correct_id) + 1 if correct_id in ranked_ids else None


def main(filepath):
    if not TEST_CASES:
        print("No test cases defined yet.")
        print("Open this script and fill in TEST_CASES with a handful of")
        print("real (question, expected_record_id) pairs from your own")
        print("corpus before running this test.")
        return

    print("Loading corpus...")
    records = load_records(filepath)
    passages = [build_passage_text(r) for r in records]
    ids = [r["id"] for r in records]
    print(f"Loaded {len(records)} records\n")

    print("Loading bge-small-en-v1.5...")
    bge = SentenceTransformer("BAAI/bge-small-en-v1.5")
    print("Loading all-MiniLM-L6-v2...")
    minilm = SentenceTransformer("all-MiniLM-L6-v2")

    print("\nEncoding all passages with both models (this may take a minute)...")
    bge_passage_emb = bge.encode(passages, show_progress_bar=True, batch_size=64)
    minilm_passage_emb = minilm.encode(passages, show_progress_bar=True, batch_size=64)

    BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    print("\n" + "=" * 70)
    print("RESULTS: rank of the correct record for each test question")
    print("(lower is better; 1 = perfect retrieval)")
    print("=" * 70)

    for question, correct_id in TEST_CASES:
        print(f"\nQuestion: {question!r}")
        print(f"Expected: {correct_id}")

        q_emb_prefixed = bge.encode(BGE_QUERY_PREFIX + question)
        rank_prefixed = rank_of_correct(q_emb_prefixed, bge_passage_emb, ids, correct_id)

        q_emb_noprefix = bge.encode(question)
        rank_noprefix = rank_of_correct(q_emb_noprefix, bge_passage_emb, ids, correct_id)

        q_emb_minilm = minilm.encode(question)
        rank_minilm = rank_of_correct(q_emb_minilm, minilm_passage_emb, ids, correct_id)

        print(f"  bge-small WITH prefix:    rank {rank_prefixed}")
        print(f"  bge-small WITHOUT prefix: rank {rank_noprefix}")
        print(f"  all-MiniLM-L6-v2:         rank {rank_minilm}")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    main(filepath)