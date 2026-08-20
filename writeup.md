# Cortex take-home — writeup

> **STATUS: sections (a) and (c) contain placeholders marked `[NEEDS REAL RUN]`.**
> Those numbers come from `python src/main.py demo` against the real endpoint and
> have deliberately not been invented. Everything not so marked is measured.

## (a) How it works, and where the tokens went

Five stages, of which **only one costs budget**:

| Stage | Module | Cost |
|---|---|---|
| Ingest / normalize 5,000 records | `ingest.py` | free, offline |
| Hybrid retrieval → 10 candidates | `retrieval.py` | free (embeddings are unbilled per §5) |
| Entity resolution (fold duplicates) | `entity_resolution.py` | free, deterministic |
| Contradiction detection | `contradiction.py` | free, deterministic |
| **Reasoning call** | `api_client.py` | **the entire budget** |

Retrieval is BM25 (lexical) fused with `bge-small-en-v1.5` embeddings via Reciprocal
Rank Fusion — rank-position fusion rather than score fusion, since the two scores
aren't on comparable scales and there's no ground truth to tune weights against.
Model choice was validated against `all-MiniLM-L6-v2` on six ground-truth pairs
(`test_embedding_choice.py`); bge-small won on paraphrased questions, average rank
2.5 vs 3.83. Embeddings are cached to disk, so re-runs cost nothing.

**Where the tokens go is structural: one Haiku call per question, and nothing else.**
Every reduction from 5,000 records to 10 happens in free local compute. That's the
funnel §5 describes, and it's why the interesting cost question is prompt size, not
call count.

One ingest change was worth making for retrieval rather than tidiness. Seven
semi-structured records failed all three deterministic patterns, because patterns B
and C both open with `if not accession_number: return None` and all seven have
`accession_number == ''`. That left title, artist, medium and classification all
`None`, so their retrieval passage was raw prose — and the measured consequence was
severe: BM25 ranked each one **#1 of 5,000** for a query drawn from its own text,
while the dense encoder ranked them **3,952–4,971 of 5,000**, so Reciprocal Rank
Fusion buried all seven outside the top 10. They were effectively unreachable. A
fourth pattern anchored on the year instead of the accession recovered 6 of 7, and
all seven now retrieve at rank 1. A broad scan (600-record random sample) found
**zero** other records with this divergence, so the vulnerability was genuinely
bounded to that population rather than a property of the embedding approach.

Two bugs surfaced during that work, both of the same family as the anti-patterns §7
names. The embedding cache validated **row count only**; the fix changed 6 passages
without changing the count, so stale vectors would have been silently reused while
appearing to confirm the new ingest. It now carries a SHA-256 fingerprint of the
passage text. And the verification harness itself filtered records by an
`extraction_method` string the fix had changed, so it matched nothing and reported
"0/0 buried" — success-shaped output from having measured no records at all.

Measured prompt cost (real, from assembled prompts — this is our own text, not a
server number): **~2,650 input tokens per question** — ~450 for the system prompt,
~2,200 for 10 context blocks. `max_tokens=1024` for output, matching the brief's
example. At ~2,650 in + realistic output, the 200,000 budget supports roughly
60–70 questions.

Two measured budget bugs worth naming, because both looked like features:

- **Markdown-fenced JSON was flagged as truncation**, firing a retry that costs a
  full extra call. Measured 5,380 tokens for one question instead of 2,690 — a
  silent 2× on every fenced response, and Haiku fences often. Fixed by separating
  the fence before the text-shape checks; an *unclosed* fence is now a genuine
  truncation signal instead.
- **`max_tokens=600` was a false economy.** The required JSON carries an answer plus
  one `{id, reason}` object per unused record; with 10 candidates that can exceed
  600, and a cap-truncation triggers the same paid retry. The tighter cap cost more
  than it saved.

`[NEEDS REAL RUN]` Actual totals, per-stage breakdown, and final `budget_remaining`
— emitted by `main.py demo` into `src/demo/transcript.md`.

## (b) The decision I was least sure about

**The abstention gate**, and I was right to be unsure — measuring it changed the
design twice.

It began as a single dense-similarity floor, `ABSTENTION_THRESHOLD = 0.35`, chosen
by eyeballing score distributions. **It never fired once.** bge-small with a query
prefix compresses cosine similarity into ~0.55–0.83 for *everything*, so 0.35 sat
far below the noise floor. Worse, at the low end dense similarity is
**anti-correlated with answerability**: pure gibberish (`"asdkjfh qwoieur zxcvbnm"`)
scored **0.623**, higher than two genuine out-of-corpus questions (0.567, 0.553).
A confidence score partly derived from that number is the "confidence with nothing
behind it" §7 warns about.

Adding a BM25 floor with **OR** logic fixed the junk direction — BM25 scores
gibberish at exactly 0.00, and OR matters because gibberish's failure mode is an
*inflated* dense score that would veto the correct signal under AND.

Then I probed the opposite direction, and found the real problem:

> **"Which three-dimensional object was built from translucent resin material?"**
> dense **0.684** (healthy) · BM25 **16.96** (below the 19.5 floor) → **abstains**
> The correct record (`aic-73423`, Eva Hesse, fiberglass) is retrieved at **rank 10**.
> The question is genuinely answerable. **This is a false abstention.**

Two things follow, and the second is the one that matters.

First, a claim I'd written into the code was simply false: that keeping the dense
check "protects a paraphrased question that shares few exact terms." Under OR, each
check can only *add* abstentions — neither can prevent one. A dense score of 0.684
rescued nothing.

Second, and decisively:

```
18.50   "What is the melting point of gallium arsenide?"          JUNK
16.96   "Which three-dimensional object ... translucent resin?"   ANSWERABLE
```

**The junk question scores higher than the answerable one, so the two classes
overlap and no absolute BM25 threshold can separate them.** 19.5 is not sitting in
a gap; it sits inside a region where both classes live. Lowering it to admit the
Hesse paraphrase readmits gallium arsenide. This is not a tuning problem, and
re-tuning the number cannot fix it.

The root cause is that BM25 magnitudes aren't comparable across queries of differing
length and term rarity — which is *why* the classes overlap on an absolute scale.

I kept 19.5 and accepted the trade: a false abstention costs one unanswered
question, a false acceptance costs a paid call plus a confident answer built on
unrelated records. Measured exposure on what's actually submitted: **0 of 8 demo
questions** and **0 of 6 ground-truth pairs** (which score 34.27–40.51, far clear).
The failing paraphrase was constructed to avoid every title, artist, and medium
term — harder than a real user is likely to type, but not impossible. Any question
naming a title, artist, or medium is comfortably safe.

**What would change my mind:** a labelled set of a few hundred questions with known
answerable/unanswerable targets. That would show whether the overlap is a
two-sample artefact or a systematic property, and it's the minimum needed to
calibrate anything better.

**Named future direction — and explicitly a different bet, not a solved fix:**
gate on a *relative* signal instead — top score against the score distribution for
that same query (top-vs-median, or a corpus percentile) rather than an absolute
magnitude. That removes the incomparability that causes the overlap. But **its own
calibration would face exactly the same small-sample limitation**: choosing a
percentile cutoff on eleven questions is no better founded than choosing 19.5 on
eleven questions. It's a more principled *shape* of solution whose parameters are
just as unvalidated. I did not build it today, because an absolute cutoff with a
measured and documented failure mode is more honest than a relative one that
merely looks more sophisticated while resting on the same eleven data points.

## (c) A question it answers badly

`[NEEDS REAL RUN]` — needs the model's actual output, not a prediction.

The demo set includes three questions expected to fail, with the mechanism stated
in `DEMO_QUESTIONS` in `src/main.py`. The strongest candidate is the brief's own
example:

> "What did Helen Frankenthaler think about Abstract Expressionism?"

Retrieval returns her paintings' catalog entries — highly relevant, and they do not
state her opinions. dense 0.770 / BM25 23.48, so it passes the gate and reaches the
model, exactly as intended: this failure belongs at the reasoning layer, not the
retrieval layer. Whether rule #2 in the system prompt ("relevance is not the same
as answerability") actually holds is the thing the real run tests. Also included:
a vision question (no vision built, by choice) and a corpus-wide aggregate
question that a top-10 funnel structurally cannot answer.

## (d) How I'd know the system was wrong in production

The honest answer is that most of the machinery here exists because *I* couldn't
check the answers either — there's no ground truth in this corpus.

**Signals that need no ground truth**, all implemented and all deterministic:

- **Citation membership** — is every cited ID actually in what the model was shown?
  Catches fabricated citations by pure set membership, free.
- **`[not recorded]` violations** — did the answer state a value for a field the
  cited record leaves empty? This is the 104-record hallucination risk found during
  data analysis, checked automatically.
- **Year cross-check** — does a year in the answer match the cited record's own
  structured years, via the same `normalize_year` used at ingest?
- **Full provenance** — every retrieved candidate is accounted for in one of three
  categories: cited, shown-but-uncited, or folded into an entity group. The third
  is known with certainty from `entity_resolution.py` and needs no model input.
  A shown-but-uncited record with **no reason given** is flagged explicitly rather
  than passed over — the model not following instructions is itself a signal.
- **Confidence is computed, never self-reported** — retrieval strength ×
  verification pass rate, minus a contradiction penalty, with components exposed.

**Two production monitors I'd add**, which this exercise can't:

1. **Verification-failure rate over time.** Any individual failure is noise; a rising
   `not_recorded_violation` rate across many questions means the prompt has drifted
   or the corpus has changed shape. That's detectable without knowing any single
   answer.
2. **Abstention-rate drift, in both directions.** Section (b) is precisely why. A
   *falling* rate means junk is getting through; a *rising* one means the gate has
   started refusing legitimate questions — and given the overlap, I would not know
   which from the score alone. Sampling abstained questions for human review is the
   only way to tell, and it's the first thing I'd instrument.

**Known limitations, stated plainly:**

- The abstention gate provably falsely abstains on some legitimate questions —
  section (b), with the specific case.
- No vision, though ~1,800 records carry images. A deliberate scope choice: text
  answers every demo question, and vision tokens are billed. Any genuinely visual
  question fails.
- Corpus-wide aggregate questions cannot be answered at all — the funnel only ever
  sees 10 records.
- Contradiction detection is validated to 142 records via a documentary-source +
  attribution-verb pattern. It catches structure, not meaning; differently-worded
  contradictions are missed. An NLI model was tested and was worse (1,389 false
  positives), which is documented in `contradiction.py` rather than quietly dropped.
- One record (`aic-136265`) has a duplicated leading phrase from corrupted source
  markup, knowingly left as-is.
- **1 record** (`aic-244616`) still fails all four extraction patterns; its
  `raw_text` is preserved as description and flagged, not dropped. It was 7
  before pattern D — see below.
- **An unexplained side effect I can't account for, flagged rather than
  smoothed over.** Pattern D fixed 6 of the 7 fallback records, and their
  retrieval burial resolved as expected: dense rank went from ~4,000–4,970 of
  5,000 to rank 1 once their title/artist/year fields were populated. But
  `aic-244616` — the one record pattern D *rejected*, whose structured fields
  are still all `None` — also went from dense rank 3,952 to rank 1. Its passage
  text did not change, so the metadata fix cannot be the cause. The plausible
  explanation is that re-embedding a corpus in which 6 sibling records changed
  shape shifted its relative position among near-neighbours, but I did not
  confirm that and I am not claiming it. What is verified is the measurement
  itself, taken by explicit record ID against a fingerprint-validated cache.
  Recorded here because an unexplained improvement is still an unexplained
  result, and the honest version of "we fixed 6 records" is "we fixed 6 records
  and a 7th improved for reasons we did not establish."
- `interpret_budget_remaining()` fails *open* if the server's units aren't a token
  count, because a guard that bricks the pipeline on an unverified assumption is
  worse than the gap it closes.
