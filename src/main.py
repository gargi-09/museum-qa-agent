"""
main.py -- Single entry point for the Cortex take-home pipeline.

Subcommands:
    ingest                  normalize data/base.jsonl -> data/normalized.jsonl
    ask [--dev] "question"  answer one question, print the full result JSON
    demo [--dev]            run the demo question set end to end and write
                            src/demo/transcript.md

DEV MODE, per the brief §5: "While you're building, send the header
X-Cortex-Mode: dev... Drop the header for the run you submit. We log both."
So --dev is OPT-IN everywhere here and defaults to OFF. Every command prints
which budget it is about to draw on before spending anything, because the
difference is a free 50,000-token sandbox versus the real 200,000-token
submission budget and that is not a thing to get wrong silently.

Usage:
    python src/main.py ingest
    python src/main.py ask --dev "What year was Coney Island Beach made?"
    python src/main.py demo --dev          # iterate for free
    python src/main.py demo                # the run you actually submit
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import get_tracker, check_credentials
from retrieval import HybridRetriever, load_records, ABSTENTION_THRESHOLD
from reasoning import answer_question

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_NORMALIZED = os.path.join(REPO_ROOT, "data", "normalized.jsonl")
DEFAULT_BASE = os.path.join(REPO_ROOT, "data", "base.jsonl")
TRANSCRIPT_PATH = os.path.join(REPO_ROOT, "src", "demo", "transcript.md")


# ---------------------------------------------------------------------------
# Demo question set
# ---------------------------------------------------------------------------
#
# The brief asks for "five to ten questions you picked, run end to end" and
# requires "at least one question where it falls over". These are chosen to
# exercise a DIFFERENT code path each, not to flatter the system -- the last
# three are expected to fail or decline, and that is the point.
DEMO_QUESTIONS = [
    {
        "q": "What year was Coney Island Beach by Reginald Marsh made?",
        "why": "Baseline: single record, structured year present. Should answer "
               "cleanly with one citation.",
        "expect": "answers",
    },
    {
        "q": "What is Louise Bourgeois's Ode to My Mother made of?",
        "why": "Exercises entity resolution: this work is catalogued by BOTH "
               "institutions, one of them as 'L. Bourgeois'. Tests that the "
               "initial-vs-full-name rule folds them and the fold is reported "
               "in provenance rather than hidden.",
        "expect": "answers",
    },
    {
        "q": "When was Omer Fast's The Casting made?",
        "why": "Exercises single-record contradiction detection: this record's "
               "own prose cites a documentary source giving a year that "
               "disagrees with its structured year. The answer must MENTION the "
               "disagreement rather than silently pick one.",
        "expect": "answers with contradiction flagged",
    },
    {
        "q": "What are the dimensions of the works in the corpus with no recorded "
             "dimensions?",
        "why": "Exercises the [not recorded] rule. The only correct answer is "
               "that the corpus does not record this -- filling it in from "
               "general knowledge is the exact hallucination the system prompt "
               "forbids and check_not_recorded_violation() looks for.",
        "expect": "declines",
    },
    {
        "q": "Which prints in the collection use a predominantly red palette?",
        "why": "not a clean failure, but a genuine, nuanced demonstration of the "
               "limits of opportunistic text-grounding for visual properties",
        "expect": "falls over",
    },
    {
        "q": "What did Helen Frankenthaler think about Abstract Expressionism?",
        "why": "FALLS OVER BY DESIGN, and it is the brief's own example. "
               "Catalog entries describing her paintings are highly relevant "
               "but do not state her opinions. A confident answer here would be "
               "the system failing while looking like it worked.",
        "expect": "falls over",
    },
    {
        "q": "What is the melting point of gallium arsenide?",
        "why": "Exercises the abstention gate. Nothing in a museum corpus "
               "supports this, so retrieval similarity should fall below "
               f"{ABSTENTION_THRESHOLD} and the system should abstain BEFORE "
               "spending a paid call.",
        "expect": "abstains",
    },
    {
        "q": "How many works in the collection are by artists whose names were "
             "recorded inconsistently between the two museums?",
        "why": "Aggregate question over the whole corpus, which a top-k "
               "retrieval funnel structurally cannot answer -- it only ever "
               "sees 10 records. Included to show a known architectural limit "
               "rather than leave it for the reader to discover.",
        "expect": "falls over",
    },
]


def announce_budget(dev):
    """Always say which budget is about to be spent, before spending it."""
    if dev:
        print("[main] dev_mode=True  -> X-Cortex-Mode: dev, free 50,000-token sandbox.")
    else:
        print("[main] dev_mode=False -> NO dev header. This draws on the REAL")
        print("       200,000-token submission budget. Use --dev while iterating.")


def cmd_ingest(args):
    from ingest import main as ingest_main
    in_path = args[0] if args else DEFAULT_BASE
    out_path = args[1] if len(args) > 1 else DEFAULT_NORMALIZED
    if not os.path.exists(in_path):
        print(f"[main] Corpus not found at {in_path}")
        print(f"[main] Fetch it first:  curl -O {{CORTEX_DATA_BASE}}/corpus/base.jsonl")
        return 1
    ingest_main(in_path, out_path)
    return 0


def build_retriever(path=DEFAULT_NORMALIZED):
    if not os.path.exists(path):
        print(f"[main] {path} not found -- run 'python src/main.py ingest' first.")
        return None
    records = load_records(path)
    print(f"[main] Loaded {len(records)} normalized records")
    return HybridRetriever(records)


def cmd_ask(args, dev):
    if not args:
        print('Usage: python src/main.py ask [--dev] "<question>"')
        return 1
    announce_budget(dev)
    retriever = build_retriever()
    if retriever is None:
        return 1
    result = answer_question(args[0], retriever, dev_mode=dev)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n" + get_tracker().summary())
    return 0


def format_result_md(item, result):
    """One transcript entry. Deliberately includes the failures verbatim."""
    lines = [f"### {item['q']}", ""]
    lines.append(f"*Why this question:* {item['why']}")
    lines.append("")
    lines.append(f"*Expected:* {item['expect']}")
    lines.append("")

    if result.get("abstained"):
        lines.append("**Outcome: ABSTAINED before any paid call.**")
        lines.append("")
        lines.append(f"> {result.get('reason')}")
    elif result.get("error"):
        lines.append(f"**Outcome: ERROR — `{result['error']}`**")
        if result.get("error_detail"):
            lines.append("")
            lines.append(f"> {result['error_detail']}")
    else:
        conf = result.get("confidence") or {}
        lines.append(f"**Outcome: answered.** "
                     f"answerable={result.get('answerable')}, "
                     f"confidence={conf.get('score')} ({conf.get('label')})")
        lines.append("")
        lines.append(f"> {result.get('answer')}")
        lines.append("")
        if result.get("limitations"):
            lines.append(f"*Stated limitations:* {result['limitations']}")
            lines.append("")
        lines.append(f"*Records cited:* {result.get('record_ids_used')}")
        lines.append("")
        lines.append(f"*Confidence components:* `{json.dumps(conf.get('components', {}))}`")
        lines.append("")
        checks = result.get("verification_checks") or {}
        lines.append("*Verification:*")
        for name, c in checks.items():
            mark = "PASS" if c.get("passed") else "FAIL"
            lines.append(f"  - `{name}`: **{mark}** — {c.get('detail')}")
        lines.append("")
        prov = result.get("full_provenance") or []
        counts = {}
        for p in prov:
            counts[p["category"]] = counts.get(p["category"], 0) + 1
        lines.append(f"*Provenance:* {len(prov)} candidates accounted for — "
                     f"`{json.dumps(counts)}`")

    lines.append("")
    lines.append("<details><summary>Full result JSON</summary>")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(result, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def cmd_demo(args, dev):
    announce_budget(dev)
    retriever = build_retriever()
    if retriever is None:
        return 1

    header = [
        "# Demo transcript",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Mode: {'dev sandbox (X-Cortex-Mode: dev)' if dev else 'REAL submission budget'}",
        f"Abstention threshold: {ABSTENTION_THRESHOLD}",
        "",
        f"{len(DEMO_QUESTIONS)} questions, run end to end. Four are expected to "
        "decline, abstain, or fail outright — those are included deliberately, "
        "not omitted.",
        "",
        "---",
        "",
    ]
    entries = []

    for i, item in enumerate(DEMO_QUESTIONS, start=1):
        print(f"\n[main] ({i}/{len(DEMO_QUESTIONS)}) {item['q']}")
        result = answer_question(item["q"], retriever, dev_mode=dev)
        entries.append(format_result_md(item, result))
        if result.get("error") in ("budget_exhausted", "bad_key"):
            print(f"[main] STOPPING: {result['error']} -- writing partial transcript.")
            entries.append(f"**Run stopped early: `{result['error']}`.** "
                           f"Remaining questions were not attempted.\n\n---\n")
            break

    tracker = get_tracker()
    footer = [
        "## Token accounting",
        "",
        "```",
        tracker.summary(),
        "```",
        "",
        f"Calls logged: {len(tracker.log)}",
        f"Last reported budget_remaining: {tracker.last_known_budget_remaining}",
        "",
    ]

    os.makedirs(os.path.dirname(TRANSCRIPT_PATH), exist_ok=True)
    with open(TRANSCRIPT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "".join(entries) + "\n".join(footer))

    print(f"\n[main] Transcript written to {TRANSCRIPT_PATH}")
    print("\n" + tracker.summary())
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 1

    dev = "--dev" in argv
    rest = [a for a in argv if a != "--dev"]
    cmd, cmd_args = rest[0], rest[1:]

    if cmd == "ingest":
        return cmd_ingest(cmd_args)
    if cmd == "ask":
        return cmd_ask(cmd_args, dev)
    if cmd == "demo":
        return cmd_demo(cmd_args, dev)

    print(f"Unknown command {cmd!r}.")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
