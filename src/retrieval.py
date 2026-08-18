"""
retrieval.py -- Hybrid retrieval over the normalized museum corpus.

Combines two FREE, local retrieval signals:
  1. BM25 (sparse, lexical) -- catches exact terminology: artist names,
     specific titles, medium terms.
  2. Dense embeddings via bge-small-en-v1.5 (semantic) -- catches
     paraphrased/conceptual questions that don't share exact keywords
     with the record text.

Fused via Reciprocal Rank Fusion (RRF) -- combines rank POSITION across
methods rather than raw scores, since BM25 and cosine-similarity scores
aren't on comparable scales. No training data or calibration needed,
which matters here: there's no ground truth to tune fusion weights against.

Model choice (bge-small-en-v1.5, with query-instruction prefix) was
empirically validated against all-MiniLM-L6-v2 on 6 real test questions --
see test_embedding_choice.py. bge-small's advantage showed specifically on
semantically-paraphrased questions (the harder, more realistic case),
average rank 2.5 vs MiniLM's 3.83.

Includes an ABSTENTION GATE: if the best retrieval score falls below a
threshold, the system should say the corpus doesn't support an answer
rather than forcing a guess -- this is checked here, before any paid
Haiku call, so it also saves budget on genuinely unanswerable questions.

Usage:
    python src/retrieval.py data/normalized.jsonl "your question here"
"""
import json
import os
import re
import sys

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CACHE_DIR = "cache"

# Empirically chosen based on eyeballing similarity score distributions --
# NOT tuned against labeled ground truth (none exists). Worth revisiting
# once real demo questions are run; documented here as a decision to revisit,
# not a final, confident number.
ABSTENTION_THRESHOLD = 0.35


def tokenize(text):
    """Simple lowercase word tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


def build_passage_text(record):
    """Combines the fields most relevant for retrieval into one passage
    string per record. Same field set used for both BM25 and embeddings,
    for simplicity and consistency.
    """
    parts = [
        record.get("title") or "",
        record.get("artist") or "",
        record.get("medium") or "",
        record.get("classification") or "",
        record.get("description") or "",
    ]
    return " ".join(p for p in parts if p)


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


class HybridRetriever:
    def __init__(self, records, cache_dir=CACHE_DIR):
        self.records = records
        self.ids = [r["id"] for r in records]
        self.passages = [build_passage_text(r) for r in records]
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        print("Building BM25 index...")
        tokenized = [tokenize(p) for p in self.passages]
        self.bm25 = BM25Okapi(tokenized)

        print(f"Loading embedding model ({EMBEDDING_MODEL_NAME})...")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        self.passage_embeddings = self._load_or_compute_embeddings()

    def _embedding_cache_path(self):
        return os.path.join(self.cache_dir, "passage_embeddings.npy")

    def _load_or_compute_embeddings(self):
        cache_path = self._embedding_cache_path()
        if os.path.exists(cache_path):
            print(f"Loading cached embeddings from {cache_path}...")
            cached = np.load(cache_path)
            if cached.shape[0] == len(self.passages):
                return cached
            print("Cache size mismatch with current corpus -- recomputing.")

        print(f"Computing embeddings for {len(self.passages)} passages "
              f"(one-time cost, will be cached)...")
        embeddings = self.model.encode(
            self.passages, show_progress_bar=True, batch_size=64
        )
        np.save(cache_path, embeddings)
        print(f"Cached embeddings to {cache_path}")
        return embeddings

    def _cosine_sim_all(self, query_embedding):
        norms = np.linalg.norm(self.passage_embeddings, axis=1)
        query_norm = np.linalg.norm(query_embedding)
        sims = np.dot(self.passage_embeddings, query_embedding) / (
            norms * query_norm + 1e-8
        )
        return sims

    def retrieve(self, question, top_k=20, rrf_k=60):
        """Returns (candidates, abstain_flag, best_similarity).
        candidates: list of dicts with id, record, rrf_score, dense_similarity
        abstain_flag: True if the best similarity is below threshold --
        caller should treat this as "corpus doesn't support a confident
        answer" rather than proceeding to a Haiku call.
        """
        bm25_scores = self.bm25.get_scores(tokenize(question))
        bm25_rank = np.argsort(bm25_scores)[::-1]

        query_embedding = self.model.encode(BGE_QUERY_PREFIX + question)
        sims = self._cosine_sim_all(query_embedding)
        dense_rank = np.argsort(sims)[::-1]

        rrf_scores = {}
        for rank, idx in enumerate(bm25_rank, start=1):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rrf_k + rank)
        for rank, idx in enumerate(dense_rank, start=1):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rrf_k + rank)

        fused_order = sorted(rrf_scores.keys(), key=lambda i: rrf_scores[i], reverse=True)
        top_indices = fused_order[:top_k]

        best_similarity = float(sims[dense_rank[0]])
        abstain = best_similarity < ABSTENTION_THRESHOLD

        candidates = []
        for idx in top_indices:
            candidates.append({
                "id": self.ids[idx],
                "record": self.records[idx],
                "rrf_score": rrf_scores[idx],
                "dense_similarity": float(sims[idx]),
            })

        return candidates, abstain, best_similarity


def main():
    if len(sys.argv) < 3:
        print('Usage: python retrieval.py <normalized.jsonl> "<question1>" "<question2>" ...')
        return

    filepath = sys.argv[1]
    questions = sys.argv[2:]  # accept one or more questions

    records = load_records(filepath)
    print(f"Loaded {len(records)} records\n")

    retriever = HybridRetriever(records)

    for question in questions:
        print("\n" + "=" * 70)
        print(f"Question: {question!r}")
        print("=" * 70)
        candidates, abstain, best_sim = retriever.retrieve(question, top_k=10)

        print(f"Best dense similarity: {best_sim:.3f} (abstention threshold: {ABSTENTION_THRESHOLD})")
        print(f"ABSTAIN (corpus likely doesn't support a confident answer): {abstain}\n")

        print("Top candidates:")
        for c in candidates:
            r = c["record"]
            print(f"  [{c['rrf_score']:.4f}] {c['id']}: {r.get('title')!r} "
                  f"by {r.get('artist')!r} (sim={c['dense_similarity']:.3f})")


if __name__ == "__main__":
    main()