# Demo transcript — NOT YET GENERATED

This file is a placeholder.

```bash
python src/main.py demo --dev
```

Iterate with `--dev` (free 50,000-token sandbox):

```bash
python src/main.py demo
```

Requires real credentials in `.env`, and the schema confirmed first via
`python probe_schema.py --yes`.

The question set lives in `DEMO_QUESTIONS` in `src/main.py`, with a stated
reason for each question and an expected outcome. Four of the eight are
expected to decline, abstain, or fail outright — the brief requires "at least
one question where it falls over", and those are included deliberately rather
than quietly dropped.
