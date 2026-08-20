# Cortex Take-Home: Museum Records QA

Answers plain-language questions over ~5,000 museum records from the Cleveland
Museum of Art and the Art Institute of Chicago, with provenance and
verification on every answer.

Retrieval narrows 5,000 records to 10 using free local compute (BM25 +
`bge-small-en-v1.5`, fused by Reciprocal Rank Fusion). Exactly one paid model
call per question. Each answer returns the records it used, the records it saw
and didn't use, four deterministic verification checks, and a computed
confidence score.

- **Demo:** [`src/demo/transcript.md`](src/demo/transcript.md) — 10 questions
  run end to end on the real budget.
- **Writeup:** Same directory - writeup.docx

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # or: source venv/bin/activate
pip install -r requirements.txt
```

`.env` in the repo root:

```
CORTEX_API_KEY=...
CORTEX_MODEL_ENDPOINT=...
CORTEX_DATA_BASE=...
CORTEX_MESSAGE_FORMAT=prepend
```

`prepend` is required, not a preference: this endpoint silently discards a
separately-supplied system prompt (measured both ways — `prompt_tokens` didn't
move for a top-level `system` key or a `{"role": "system"}` entry). Folding
instructions into the user message is the only placement that arrives. See the
header of [`src/api_client.py`](src/api_client.py).

`data/` and `.env` are gitignored, so fetch the corpus:

```bash
mkdir -p data
curl -o data/base.jsonl "$CORTEX_DATA_BASE/corpus/base.jsonl"   # into data/
python src/main.py ingest                      # -> data/normalized.jsonl
```

`ingest` makes no network calls and costs nothing.

## Usage

```bash
python src/main.py ask --dev "What year was Coney Island Beach made?"
python src/main.py demo --dev
```

`--dev` uses the free 50,000-token sandbox. **Omitting it spends the real
200,000-token budget** (`demo` costs ~29,000). Both commands print which budget
they're about to draw on first.

Run from the repo root — data and cache paths are relative to the working
directory. The first run computes embeddings (~4–5 min, 5,000 passages) and
caches them to `cache/` behind a SHA-256 fingerprint of the passage text, so an
ingest change invalidates the cache instead of reusing stale vectors.

Corrections persist across runs and are applied before retrieval, entity
resolution and contradiction detection:

```bash
python src/memory.py add cma-168184 year_raw 1999 "curator correction"
python src/memory.py list
```

## Layout

```
src/
  main.py              CLI: ingest | ask | demo
  ingest.py            normalisation, 4 deterministic extraction patterns
  retrieval.py         BM25 + bge-small + RRF + abstention gate
  entity_resolution.py duplicate folding, cross-record year checks
  contradiction.py     prose-vs-structured-field contradictions
  memory.py            correction persistence
  reasoning.py         orchestrator: prompt, parse, verify, score
  api_client.py        the only module that calls the endpoint
test_scripts/          contains test scripts, used during building
data/                  corpus and normalised output (gitignored)
cache/                 embedding cache (gitignored, rebuilt on first run)
```

Root-level scripts are development tools, not pipeline code: data forensics
(`analyze_corpus.py`, `final_stress_test.py`, `inspect_*.py`), and rejected
experiments kept as evidence (`nli_contradiction_test.py`,
`contradiction_nli_approach.py` — NLI was tested twice for contradiction
detection and was worse both times).

Two exceptions:
- `mock_reasoning_test.py` — runs the full pipeline with `call_haiku`
  monkeypatched. Five failure scenarios, zero tokens.
- `probe_schema.py` — makes **real** dev-mode API calls, gated behind `--yes`.
  Resolved the wire format above.

Total spend: **64,127 of 200,000 tokens** across 17 paid calls.
