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
import hashlib
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
#
# MEASURED AND FOUND INADEQUATE ON ITS OWN. Running the demo set revealed this
# gate never fires: bge-small with the query-instruction prefix compresses
# cosine similarity into a narrow high band (~0.55-0.83 across everything
# tried), so 0.35 sits well below the noise floor. Worse, at the low end dense
# similarity is ANTI-CORRELATED with answerability -- pure gibberish
# ("asdkjfh qwoieur zxcvbnm") scored 0.623, HIGHER than two genuine
# out-of-corpus questions (0.567, 0.553). Kept anyway, as one of two triggers,
# because it catches a failure mode BM25 misses: a question sharing plenty of
# corpus vocabulary while meaning something unrelated. It does NOT rescue a
# low-BM25 question -- under OR logic no check can, see retrieve().
ABSTENTION_THRESHOLD = 0.35

# Lexical-overlap floor, added because ABSTENTION_THRESHOLD alone never fired.
# BM25 separates where dense similarity does not -- measured max BM25 score
# across the same probe questions:
#
#     45.69  "What year was Coney Island Beach by Reginald Marsh made?"  in
#     43.06  "What is Louise Bourgeois's Ode to My Mother made of?"      in
#     35.56  "...works in the corpus with no recorded dimensions?"       in
#     31.61  "When was Omer Fast's The Casting made?"                    in
#     29.39  "...artists whose names were recorded inconsistently...?"   in
#     23.48  "What did Helen Frankenthaler think about ...?"             in
#     20.15  "Which prints use a predominantly red palette?"             in
#     ----------------------------------------------------------------- gap
#     18.50  "What is the melting point of gallium arsenide?"            out
#     14.67  "What is the capital of Mongolia?"                          out
#     13.33  "How do I configure a Kubernetes ingress controller?"       out
#      0.00  "asdkjfh qwoieur zxcvbnm"                                   out
#
# 19.5 is placed in the gap between the highest out-of-corpus score (18.50)
# and the lowest in-corpus score (20.15). SAME CAVEAT AS ABOVE, and it should
# be read no more confidently: an educated placement from ELEVEN samples, not
# a tuned value, with still no labeled ground truth to tune against.
#
# THE FIRST ATTEMPT WAS 21.0, and the regression check caught it. That value
# came from a smaller sample whose lowest in-corpus score was 23.48, making
# the gap look ~5 points wide. Running the full demo set added the red-palette
# question at 20.15 -- a legitimate question about records that genuinely
# exist in this corpus -- which 21.0 wrongly abstained on. The real separating
# margin is therefore about 1.65 points (18.50 -> 20.15), not 5.
#
# AND THEN THE MARGIN TURNED OUT NOT TO EXIST AT ALL. Probing specifically for
# the opposite failure direction -- a genuinely answerable question with LOW
# lexical overlap -- found one that scores BELOW the worst junk question:
#
#     18.50  "What is the melting point of gallium arsenide?"          JUNK
#     16.96  "Which three-dimensional object was built from            ANSWERABLE
#             translucent resin material?"                             (aic-73423,
#                                                                       rank 10,
#                                                                       dense 0.684)
#
# The junk question scores HIGHER than the answerable one, so THE TWO CLASSES
# OVERLAP and no absolute BM25 cutoff can separate them. 19.5 does not sit in a
# gap; it sits inside a region where both classes live. It is chosen to favour
# rejecting junk, which costs one unanswered question, over accepting it, which
# costs a paid call plus a confident answer built on unrelated records.
#
# CONSEQUENCE, stated plainly rather than buried: this gate WILL falsely abstain
# on some legitimate questions, and that is not fixable by re-tuning the number.
# Measured scope of the damage on what is actually being submitted: zero of the
# eight demo questions, and zero of the six ground-truth pairs in
# test_embedding_choice.py (which score 34.27-40.51, far clear of the floor).
# The false abstention above is on a paraphrase deliberately constructed to
# avoid every title, artist and medium term -- harder than anything a real user
# is likely to type, but not impossible.
#
# The relative-signal fix is therefore not a nice-to-have but the ONLY thing
# that actually resolves this: gate on the top score relative to the score
# distribution FOR THAT QUERY (e.g. top-vs-median, or a corpus percentile)
# rather than on an absolute magnitude, because BM25 magnitudes are not
# comparable across queries of differing length and term rarity -- which is
# precisely why these two classes overlap on an absolute scale. Deliberately
# not built here: it needs a wider labelled question set to calibrate against
# than this exercise has, and an absolute cutoff with a documented, measured
# failure mode is more honest than a relative one tuned on eleven samples.
BM25_ABSTENTION_THRESHOLD = 19.5


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

    def _fingerprint_path(self):
        return os.path.join(self.cache_dir, "passage_embeddings.fingerprint")

    def _passages_fingerprint(self):
        """SHA-256 over the exact passage TEXT the embeddings were built from.

        REAL BUG THIS FIXES, found while re-running ingest: the cache was
        validated on ROW COUNT alone. Pattern D changed the passage text of 6
        records without changing the record count -- still 5,000 -- so the
        count check passed and the STALE embeddings would have been silently
        reused. Every retrieval measurement taken afterwards would have been
        against the old vectors while appearing to confirm the new ingest, with
        nothing anywhere reporting a problem. Exactly the "absence of an error
        treated as success" trap, and it would have quietly invalidated the
        verification it was standing in the middle of.

        Fingerprinting the content rather than the shape makes any change to
        title/artist/medium/classification/description invalidate the cache,
        because those are precisely the fields build_passage_text() reads.
        """
        h = hashlib.sha256()
        h.update(EMBEDDING_MODEL_NAME.encode("utf-8"))
        for p in self.passages:
            h.update(b"\x00")
            h.update(p.encode("utf-8"))
        return h.hexdigest()

    def _load_or_compute_embeddings(self):
        cache_path = self._embedding_cache_path()
        fp_path = self._fingerprint_path()
        current_fp = self._passages_fingerprint()

        if os.path.exists(cache_path):
            print(f"Loading cached embeddings from {cache_path}...")
            cached = np.load(cache_path)
            cached_fp = None
            if os.path.exists(fp_path):
                with open(fp_path, "r", encoding="utf-8") as f:
                    cached_fp = f.read().strip()

            if cached.shape[0] != len(self.passages):
                print(f"Cache has {cached.shape[0]} rows, corpus has "
                      f"{len(self.passages)} -- recomputing.")
            elif cached_fp is None:
                print("Cache has no content fingerprint (written by an older "
                      "version) -- recomputing rather than trusting it.")
            elif cached_fp != current_fp:
                print("Cache fingerprint does not match the current passage text "
                      "-- the corpus changed underneath it. Recomputing.")
            else:
                print("Cache fingerprint matches current passage text.")
                return cached

        print(f"Computing embeddings for {len(self.passages)} passages "
              f"(one-time cost, will be cached)...")
        embeddings = self.model.encode(
            self.passages, show_progress_bar=True, batch_size=64
        )
        np.save(cache_path, embeddings)
        with open(fp_path, "w", encoding="utf-8") as f:
            f.write(current_fp)
        print(f"Cached embeddings to {cache_path}")
        print(f"Wrote content fingerprint {current_fp[:16]}... to {fp_path}")
        return embeddings

    def _cosine_sim_all(self, query_embedding):
        norms = np.linalg.norm(self.passage_embeddings, axis=1)
        query_norm = np.linalg.norm(query_embedding)
        sims = np.dot(self.passage_embeddings, query_embedding) / (
            norms * query_norm + 1e-8
        )
        return sims

    def retrieve(self, question, top_k=20, rrf_k=60):
        """Returns (candidates, abstain_flag, best_similarity, signals).

        candidates: list of dicts with id, record, rrf_score, dense_similarity
        abstain_flag: True if EITHER retrieval signal looks bad -- caller
            should treat this as "corpus doesn't support a confident answer"
            rather than proceeding to a paid Haiku call.
        best_similarity: best dense cosine similarity (unchanged meaning).
        signals: dict recording BOTH signals and which one(s) fired, so the
            caller can report an accurate reason instead of assuming it was
            the dense check.

        ABSTENTION USES **OR**, NOT AND, AND THAT IS THE WHOLE POINT.
        Requiring both signals to agree would defeat the fix: gibberish's
        failure mode is to INFLATE dense similarity (0.623, higher than real
        out-of-corpus questions) while BM25 correctly reports 0.00. Under AND
        logic the healthy-looking dense score would veto the correct BM25
        signal and the junk question would sail through. Under OR, either
        signal alone is enough to stop the call.

        What each check contributes:
          - BM25 low  -> no lexical anchor anywhere in the corpus. Catches
            junk and off-domain questions, where dense is unreliable.
          - dense low -> no semantic match. Catches a question that happens
            to share keywords with the corpus but means something unrelated.

        CORRECTION, kept here because the wrong version was written down first
        and then measured: an earlier draft of this docstring claimed the dense
        check's PRESENCE "protects a legitimate paraphrased question that is
        semantically close while sharing few exact terms." That is FALSE under
        OR logic, and measurably so. Under OR, each check can only ADD
        abstentions -- neither can ever prevent one. A healthy dense score
        cannot rescue a question whose BM25 falls below the floor. Measured
        counter-example:

            "Which three-dimensional object was built from translucent resin
             material?"   -> dense 0.684 (healthy), BM25 16.96 (below floor)
            The correct record (aic-73423, Eva Hesse, fiberglass) IS retrieved
            at rank 10, so the question is genuinely answerable -- and it
            abstains anyway. A FALSE ABSTENTION caused by OR logic.

        So the honest description is: OR trades false abstentions for
        guaranteed junk rejection. That trade is deliberate and is the right
        one for a budget-constrained demo, since the cost of a false
        abstention is one unanswered question while the cost of a false
        acceptance is a paid call plus a confident answer built on unrelated
        records. It is NOT a free win, and see BM25_ABSTENTION_THRESHOLD for
        why no choice of threshold removes it.
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
        bm25_max = float(bm25_scores.max()) if len(bm25_scores) else 0.0

        dense_below = best_similarity < ABSTENTION_THRESHOLD
        bm25_below = bm25_max < BM25_ABSTENTION_THRESHOLD
        abstain = dense_below or bm25_below

        reasons = []
        if dense_below:
            reasons.append(f"best dense similarity {best_similarity:.3f} is below "
                            f"ABSTENTION_THRESHOLD {ABSTENTION_THRESHOLD} -- no record "
                            f"is semantically close to this question")
        if bm25_below:
            reasons.append(f"best BM25 score {bm25_max:.2f} is below "
                            f"BM25_ABSTENTION_THRESHOLD {BM25_ABSTENTION_THRESHOLD} -- "
                            f"no record shares enough distinctive vocabulary with this "
                            f"question to anchor an answer")

        signals = {
            "dense_similarity": best_similarity,
            "bm25_max": bm25_max,
            "dense_threshold": ABSTENTION_THRESHOLD,
            "bm25_threshold": BM25_ABSTENTION_THRESHOLD,
            "dense_below_threshold": dense_below,
            "bm25_below_threshold": bm25_below,
            "abstain_reasons": reasons,
        }

        candidates = []
        for idx in top_indices:
            candidates.append({
                "id": self.ids[idx],
                "record": self.records[idx],
                "rrf_score": rrf_scores[idx],
                "dense_similarity": float(sims[idx]),
            })

        return candidates, abstain, best_similarity, signals


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
        candidates, abstain, best_sim, signals = retriever.retrieve(question, top_k=10)

        print(f"Best dense similarity: {best_sim:.3f} "
              f"(threshold {ABSTENTION_THRESHOLD}, below={signals['dense_below_threshold']})")
        print(f"Best BM25 score:       {signals['bm25_max']:.2f} "
              f"(threshold {BM25_ABSTENTION_THRESHOLD}, below={signals['bm25_below_threshold']})")
        print(f"ABSTAIN (either signal bad): {abstain}")
        for reason in signals["abstain_reasons"]:
            print(f"  - {reason}")
        print()

        print("Top candidates:")
        for c in candidates:
            r = c["record"]
            print(f"  [{c['rrf_score']:.4f}] {c['id']}: {r.get('title')!r} "
                  f"by {r.get('artist')!r} (sim={c['dense_similarity']:.3f})")


if __name__ == "__main__":
    main()