# Museum Records QA

*MAKE SURE TO USE THE CORRECT ENV & Database VARIABLE NAME BEFORE RUNNING!!*

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

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # or: source venv/bin/activate
pip install -r requirements.txt
```

`.env` in the repo root:

```
API_KEY=...
MODEL_ENDPOINT=...
DATA_BASE=...
MESSAGE_FORMAT=prepend
```

`prepend` is required, not a preference: this endpoint silently discards a
separately-supplied system prompt (measured both ways — `prompt_tokens` didn't
move for a top-level `system` key or a `{"role": "system"}` entry). Folding
instructions into the user message is the only placement that arrives. See the
header of [`src/api_client.py`](src/api_client.py).

`data/` and `.env` are gitignored, so fetch the corpus:

```bash
mkdir -p data
curl -o data/base.jsonl "$DATA_BASE/corpus/base.jsonl"   # into data/
python src/main.py ingest                      # -> data/normalized.jsonl
```

`ingest` makes no network calls and costs nothing.

## Architecture

<img width="5890" height="8192" alt="image" src="https://github.com/user-attachments/assets/05983f83-2227-493a-996a-619794b2c7bd" />


## Usage

Run single queries or the end-to-end evaluation suite via the CLI:

```bash
# Query the pipeline
python src/main.py ask "What year was Coney Island Beach made?"

# Run the end-to-end benchmark suite (10 sample questions)
python src/main.py demo
```

### Run against a mock/development environment without calling live endpoints

```bash
python src/main.py ask --dev "What year was Coney Island Beach made?"
Caching & Invalidation
Run all commands from the repository root. On the first run, the pipeline generates dense embeddings for ~5,000 records (~4–5 min) and saves them to cache/ backed by a SHA-256 fingerprint of the passage text. If corpus ingestion changes, the fingerprint mismatches and automatically invalidates the cache instead of serving stale vectors.

Curator Corrections & Stateful Overrides
Explicit factual corrections persist across runs and are evaluated upstream—prior to retrieval, entity resolution, and contradiction checking:
```

### Add a manual correction for an ambiguous or disputed record

```bash
python src/memory.py add cma-168184 year_raw 1999 "curator correction"
```
### Inspect current active overrides

```bash
python src/memory.py list
```
Token Efficiency & Guardrails
The reasoning engine enforces strict cost and latency constraints:

Local Pre-filtering: Sparse/dense candidate fusion eliminates remote calls during the ranking stage.

Single-Call Bounding: Generates verified answers in exactly one bounded model invocation per question.

Deterministic Verification: Programmatic validation runs post-generation with zero additional token overhead.

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
