"""
reasoning.py -- Assembles retrieval + entity-resolution + contradiction
context into a prompt, calls Haiku, parses the answer, runs deterministic
verification checks, and computes confidence.

This is the ORCHESTRATOR: it imports and calls retrieval.py,
entity_resolution.py, contradiction.py, and api_client.py directly.
Nothing calls this file except the eventual top-level main.py.

Fully buildable and testable RIGHT NOW without real API credentials --
api_client.call_haiku() checks credentials first and returns a clean
'missing_credentials' error rather than crashing, so everything up to
the actual network call (context assembly, prompt construction, output
parsing, verification logic) can be built and verified today.

SCOPE DECISION: vision is NOT used, despite 1,788 of 5,000 records
(35.8%) carrying an image_path the assignment doc explicitly makes
available. This is a deliberate choice, not an oversight: the text
fields (description, title, artist, medium) are complete enough for
every question in the demo set to be answered from text alone, and
image content would add real token cost (vision tokens count against
the same 200k budget per the assignment doc) for a capability not yet
shown to be needed. If a future question genuinely required visual
information text doesn't capture (e.g. "which of these prints uses a
red color palette"), the natural extension point is here: fetch the
image via {CORTEX_DATA_BASE}/images/{image_path}, pass it as a vision
content part to Haiku alongside the text context already assembled.
Not built now because it was never demonstrated to be necessary, and
building it speculatively would spend budget on an unproven need.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval import HybridRetriever, load_records
from entity_resolution import build_entity_groups, summarize_group_for_prompt
from contradiction import check_internal_contradiction
from api_client import call_haiku, get_tracker
from memory import apply_corrections_to_record, load_corrections


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

# Field label shown in the prompt -> the record key it reads from. Ordered:
# this is the order fields appear in the prompt, and dicts preserve it.
#
# 'year' reads from 'year_raw' deliberately -- the human-written string
# ("c. 1926", "1967-68") is what should be shown, while the parsed 'years'
# list stays internal for check_factual_match to compare against.
PROMPT_FIELDS = {
    "title": "title",
    "artist": "artist",
    "year": "year_raw",
    "medium": "medium",
    "dimensions": "dimensions",
    "classification": "classification",
}


def build_not_recorded_view(record):
    """Converts internal None values into the explicit '[not recorded]'
    marker for anything shown in a prompt. This is deliberately a
    PROMPT-TIME concern, not baked into ingest.py's data storage --
    internal code keeps using None/truthiness checks; only text actually
    shown to Haiku uses this marker.

    REAL BUG, found on the first live dev call: 'year' was MISSING from this
    list entirely. The context block carried a 'years' key and
    format_context_blocks_for_prompt() rendered exactly this dict plus the
    description, so no record's year was ever written into the prompt at all.
    The parsed year was used only for post-hoc verification. Asked "what year
    was Coney Island Beach made?", the model answered "the corpus does not
    record the year" and set answerable=false -- which was the CORRECT reading
    of a prompt that genuinely did not contain it, for a record whose
    year_raw is '1935'.

    WHAT MAKES THIS THE WORST KIND OF BUG HERE: every verification check
    passed and confidence came back 0.88/high. check_not_recorded_violation
    compares the answer against the fields it was SHOWN, and factual_match
    reported "no year mentioned in answer -- nothing to check". Neither can
    detect a field that never made it into the prompt, because both validate
    answer-vs-context consistency, not context completeness. A missing input
    field is invisible to output verification -- which is exactly why the
    demo run mattered and why offline prompt inspection alone would not have
    caught it either.
    """
    return {shown: (record.get(src) if record.get(src) else "[not recorded]")
            for shown, src in PROMPT_FIELDS.items()}


def assemble_context_blocks(candidates):
    """Runs entity resolution + contradiction checking over retrieval's
    candidates, returning (context_blocks, folded_ids_map).

    context_blocks: list of blocks ready to format into a prompt. Mirrors
    test_pipeline.py's logic exactly (already validated there against
    real data).

    folded_ids_map: dict of {representative_id: [other_member_ids]} --
    PREVIOUSLY DISCARDED, now returned explicitly. This is what makes
    deterministic provenance tracking possible (see
    build_full_provenance() below): without this, the IDs of non-
    representative entity-group members only survived as unstructured
    text inside group_note, with no way to programmatically account for
    them as "considered but not shown independently" -- a real gap
    against the assignment's "what was NOT considered" requirement.
    """
    candidate_records = [c["record"] for c in candidates]

    # Apply any persisted human corrections BEFORE anything else touches
    # these records -- this means entity resolution, contradiction
    # checking, and context assembly all automatically see corrected
    # values, without needing separate correction-handling logic
    # scattered through multiple stages. See memory.py for the full
    # design rationale (a scoped, honest implementation of correction
    # persistence).
    corrections = load_corrections()
    candidate_records = [apply_corrections_to_record(r, corrections) for r in candidate_records]

    # VISIBILITY FIX: apply_corrections_to_record() applies silently by
    # design (no print inside memory.py itself, since that module has no
    # opinion about how its caller wants to log things) -- but that meant
    # running reasoning.py gave ZERO console confirmation that a
    # correction was picked up and used, even though it genuinely was.
    # Print explicitly here so this is directly observable, not just
    # trusted to have happened silently.
    for r in candidate_records:
        if r.get("_correction_notes"):
            print(f"[reasoning] Correction applied to {r['id']}:")
            for note in r["_correction_notes"]:
                print(f"    {note}")

    entity_groups = build_entity_groups(candidate_records)

    grouped_ids = set()
    for g in entity_groups:
        grouped_ids.update(m["id"] for m in g["members"])

    context_blocks = []
    folded_ids_map = {}

    for g in entity_groups:
        summary = summarize_group_for_prompt(g)
        rep = summary["representative"]
        other_ids = [m["id"] for m in g["members"] if m["id"] != rep["id"]]
        folded_ids_map[rep["id"]] = other_ids

        contradiction_result = check_internal_contradiction(rep)
        context_blocks.append({
            "id": rep["id"],
            "institution": rep.get("institution"),
            "accession_number": rep.get("accession_number"),
            "fields": build_not_recorded_view(rep),
            "description": rep.get("description") or "[not recorded]",
            "years": rep.get("years") or [],
            "group_note": summary["note"],
            "correction_notes": rep.get("_correction_notes"),
            "internal_contradiction": contradiction_result if contradiction_result["has_contradiction"] else None,
        })

    for c in candidate_records:
        r = c
        if r["id"] in grouped_ids:
            continue
        contradiction_result = check_internal_contradiction(r)
        context_blocks.append({
            "id": r["id"],
            "institution": r.get("institution"),
            "accession_number": r.get("accession_number"),
            "fields": build_not_recorded_view(r),
            "description": r.get("description") or "[not recorded]",
            "years": r.get("years") or [],
            "group_note": None,
            "correction_notes": r.get("_correction_notes"),
            "internal_contradiction": contradiction_result if contradiction_result["has_contradiction"] else None,
        })

    return context_blocks, folded_ids_map


def build_full_provenance(context_blocks, folded_ids_map, parsed_response):
    """Deterministically accounts for EVERY retrieved candidate -- not
    just relying on Haiku's self-reported exclusions, which only ever
    covers records it was actually shown, and only explains if it
    bothers to.

    Three categories, covering every retrieved candidate ID exactly once:

    1. 'used' -- Haiku explicitly cited this record ID.
    2. 'shown_not_cited' -- this record got its OWN full context block
       (as a singleton or an entity-group representative), but Haiku did
       not cite it. If Haiku provided a reason via record_ids_excluded,
       that reason is used. IMPORTANT: if Haiku did NOT provide a reason,
       this is flagged EXPLICITLY as "NO REASON GIVEN" rather than
       silently treated as fine -- a shown-but-uncited record with no
       explanation is itself a real signal (the model not fully following
       instruction #4 in the system prompt), not something to paper over.
    3. 'folded_into_group' -- this record was a NON-representative member
       of an entity-resolution cluster. It never received its own context
       block at all, so it structurally could not have been
       independently cited. This category is known with FULL CERTAINTY
       from entity_resolution.py's own output -- it requires zero input
       from Haiku, unlike categories 1-2.

    Returns a list of dicts: {id, category, reason}, one entry per
    retrieved candidate, covering the full set with no gaps.
    """
    used_ids = set(parsed_response.get("record_ids_used", [])) if parsed_response else set()

    haiku_excluded_reasons = {}
    if parsed_response:
        for item in parsed_response.get("record_ids_excluded", []):
            if isinstance(item, dict) and "id" in item:
                haiku_excluded_reasons[item["id"]] = item.get("reason", "")

    provenance = []

    for block in context_blocks:
        rid = block["id"]
        if rid in used_ids:
            provenance.append({"id": rid, "category": "used", "reason": None})
        else:
            reason = haiku_excluded_reasons.get(rid)
            if reason:
                provenance.append({"id": rid, "category": "shown_not_cited", "reason": reason})
            else:
                provenance.append({
                    "id": rid, "category": "shown_not_cited",
                    "reason": "NO REASON GIVEN by model -- shown but silently unused, "
                              "worth scrutinizing whether this should have been cited",
                })

    for rep_id, folded_ids in folded_ids_map.items():
        for fid in folded_ids:
            provenance.append({
                "id": fid,
                "category": "folded_into_group",
                "reason": f"Same title+artist match as representative {rep_id} -- "
                          f"treated as a duplicate record, not shown to the model "
                          f"independently (see entity_resolution.py)",
            })

    return provenance


def format_context_blocks_for_prompt(context_blocks):
    """Turns the structured context blocks into the actual text that goes
    into the prompt. Every fact traces back to a specific record ID --
    this IS the provenance mechanism.
    """
    lines = []
    for block in context_blocks:
        lines.append(f"--- RECORD {block['id']} ({block['institution']}, "
                      f"accession {block['accession_number'] or '[not recorded]'}) ---")
        # Renders whatever build_not_recorded_view() returns, which is why
        # adding 'year' to PROMPT_FIELDS is sufficient to surface it here --
        # and why omitting it there silently removed it from every prompt.
        for field, value in block["fields"].items():
            lines.append(f"{field}: {value}")
        # The parsed year list is normally redundant with the year string above,
        # so emit it ONLY when it expands to more than one year (year_raw
        # "1967-68" -> [1967, 1968]). In that case the model should read the
        # same range that check_factual_match will validate its answer against,
        # rather than having to infer the expansion itself.
        if len(block.get("years") or []) > 1:
            lines.append(f"year (parsed): {block['years']}")
        lines.append(f"description: {block['description']}")
        if block["group_note"]:
            lines.append(f"NOTE: {block['group_note']}")
        if block.get("correction_notes"):
            for note in block["correction_notes"]:
                lines.append(f"HUMAN CORRECTION APPLIED: {note}")
        if block["internal_contradiction"]:
            ic = block["internal_contradiction"]
            lines.append(f"INTERNAL CONTRADICTION FLAG: this record's own prose cites "
                          f"an alternate year ({ic['conflicting_years']}) not matching its "
                          f"structured year ({ic['structured_years']}) -- source: "
                          f"\"{ic['matched_sentence']}\"")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt -- this is where the two named-and-documented fixes from
# retrieval testing actually become real instructions, not just decisions
# written down in notes.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are answering questions about a museum records corpus. You will be given a set of retrieved records and must answer ONLY using what is stated in them.

CRITICAL RULES:

1. NOT-RECORDED FIELDS: Any field marked "[not recorded]" means that information does not exist in this corpus for that record. Do NOT fill it in from your own general knowledge, even if you recognize the artwork or artist. If asked about a [not recorded] field, say plainly that the corpus doesn't record that information.

2. RELEVANCE IS NOT THE SAME AS ANSWERABILITY: Records can be topically related to a question WITHOUT actually answering it. For example, if asked "what did an artist think about a movement," records that are simply catalog entries describing that artist's paintings do NOT answer a question about their personal opinions, even if they are the most relevant records available. Before answering, check: do these records literally STATE the fact being asked, or are they merely ABOUT the same general subject? If the records don't literally state it, say so explicitly rather than answering confidently from a related record.

3. CONTRADICTIONS: If a record has an INTERNAL CONTRADICTION FLAG, or a NOTE indicating disagreement with another record, you must mention this in your answer rather than picking one value silently.

4. CITE YOUR SOURCES: Every factual claim must be traceable to a specific record ID from the context provided.

Respond ONLY with valid JSON in this exact format, nothing else before or after:
{
  "answer": "your answer text here",
  "answerable": true or false,
  "record_ids_used": ["id1", "id2"],
  "record_ids_excluded": [{"id": "id3", "reason": "why this was retrieved but not used"}],
  "limitations": "any caveats, contradictions, or gaps worth noting, or empty string if none"
}"""


# The rules above, wrapped in an explicit delimiter.
#
# WHY THE TAGS EXIST: measurement showed the Cortex proxy DISCARDS the system
# prompt however it is passed separately -- prompt_tokens did not move for a
# top-level 'system' key, nor for a {"role": "system"} entry in messages, and
# the model returned an identical generic greeting in both cases. The only
# placement that provably survives is inside the user message itself
# (CORTEX_MESSAGE_FORMAT=prepend, see api_client._prepend_system).
#
# That creates a problem the tags solve: once these rules sit in the same
# message as the question and 5,000-ish characters of retrieved records, the
# model has no structural cue separating standing instructions from user
# content. An explicit <instructions> block restores that boundary, and
# Claude follows XML-delimited sections reliably.
#
# The tags live HERE, not in api_client, on purpose. Where the text goes on
# the wire is a network concern and belongs to build_payload(); how the prompt
# is worded and demarcated is prompt engineering and belongs to this module.
# Harmless in the other placements too -- a tagged system prompt is still a
# perfectly good system prompt -- so this does not have to change if the
# endpoint's behaviour ever does.
INSTRUCTIONS_BLOCK = f"<instructions>\n{SYSTEM_PROMPT}\n</instructions>"


def build_prompt(question, context_blocks):
    """Returns (instructions, messages) -- deliberately provider-NEUTRAL.

    messages contains ONLY 'user'/'assistant' turns. The instructions come
    back SEPARATELY rather than as a {"role": "system"} entry, because the
    three candidate placements disagree about where they belong (Anthropic:
    top-level 'system'; OpenAI: first messages entry; prepend: folded into
    the user message). Committing to one here would bake a wire-format
    decision into the reasoning layer.

    api_client.build_payload() owns that translation, consistent with this
    pipeline's rule that every network concern lives in exactly one file.
    What this module owns is the CONTENT -- the rules themselves and the
    <instructions> delimiter around them.
    """
    context_text = format_context_blocks_for_prompt(context_blocks)
    user_message = f"QUESTION: {question}\n\nRETRIEVED RECORDS:\n\n{context_text}"
    return INSTRUCTIONS_BLOCK, [{"role": "user", "content": user_message}]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_haiku_response(raw_content):
    """Parses Haiku's JSON output defensively -- real API responses don't
    always perfectly follow instructions, so this handles the common
    failure modes (extra text before/after the JSON, markdown code fences)
    rather than assuming a perfectly clean response.
    """
    if not raw_content:
        return None, "empty_response"

    text = raw_content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None, "no_json_found"

    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        return None, f"json_decode_error: {e}"

    required_keys = {"answer", "answerable", "record_ids_used", "record_ids_excluded", "limitations"}
    missing_keys = required_keys - set(parsed.keys())
    if missing_keys:
        return parsed, f"missing_keys: {missing_keys}"

    return parsed, None


# ---------------------------------------------------------------------------
# Verification suite -- deterministic checks run AFTER Haiku answers
# ---------------------------------------------------------------------------

# A check that CANNOT FAIL must not report a pass. Every check below returns
# inconclusive=True when the conditions it needs to detect anything are absent,
# and run_verification_suite() excludes those from the pass-rate denominator.
#
# WHY: on the dev demo run, a correct decline citing zero records reported 3/3
# verification passes, because every check iterates the cited records and there
# were none. That fed a 1.0 verification_score into confidence and produced
# 0.88/"high" for an answer that asserted nothing. Fix 1 stops scoring those
# responses at all; this makes the checks themselves say why they were silent
# instead of claiming a clean bill of health.
#
# NOTE on the `passed` key when inconclusive is set: it is left True so that a
# consumer reading only `passed` does not render a FAIL for a check that did not
# fail either. `passed` is MEANINGLESS when inconclusive is True -- read
# inconclusive first. main.format_result_md() does.
INCONCLUSIVE_NO_CITATIONS = (
    "INCONCLUSIVE -- the response cited no records, so this check had nothing to "
    "examine. It did not pass; it could not run."
)


def check_citation_membership(parsed_response, context_blocks):
    """Are all cited record IDs actually among the records Haiku was given?
    Catches fabricated citations. Pure set membership, free.

    Reports inconclusive rather than a pass when nothing was cited -- an empty
    citation set trivially contains no fabricated citations, which is not
    evidence that the response is well-grounded.
    """
    if not parsed_response:
        return {"passed": False, "detail": "no response to check"}
    valid_ids = set(b["id"] for b in context_blocks)
    used_ids = set(parsed_response.get("record_ids_used") or [])
    if not used_ids:
        return {"passed": True, "inconclusive": True,
                "detail": INCONCLUSIVE_NO_CITATIONS}
    fabricated = used_ids - valid_ids
    return {
        "passed": len(fabricated) == 0,
        "detail": f"fabricated citations: {fabricated}" if fabricated else "all citations valid",
    }


def check_not_recorded_violation(parsed_response, context_blocks):
    """Did the answer state a specific value for a field that was marked
    [not recorded] in the record(s) it cites? This is the concrete,
    automated check for the exact hallucination risk found during
    data-quality analysis (104 records with empty artist/dimensions/etc).
    """
    if not parsed_response:
        return {"passed": False, "detail": "no response to check"}

    answer_text = (parsed_response.get("answer") or "").lower()
    used_ids = set(parsed_response.get("record_ids_used") or [])
    if not used_ids:
        return {"passed": True, "inconclusive": True,
                "detail": INCONCLUSIVE_NO_CITATIONS}
    blocks_by_id = {b["id"]: b for b in context_blocks}

    # THE GUARD, and why it is now reported rather than trusted. These terms
    # suppress the substring test below for EVERY field on EVERY cited record,
    # because answer_text is the whole answer. Measured on the dev demo run:
    # the dimensions question's answer contained "[not recorded]" three times,
    # so the check was structurally dead and still reported
    # "no violations detected" -- an unfailable check claiming a clean result,
    # which is the brief's "absence of an error treated as success" exactly.
    guard_terms = [t for t in ("not recorded", "unknown") if t in answer_text]

    violations = []
    in_scope = []
    for rid in used_ids:
        block = blocks_by_id.get(rid)
        if not block:
            continue
        for field, value in block["fields"].items():
            if value == "[not recorded]":
                # Every [not recorded] field on a cited record is something
                # this check is SUPPOSED to be watching. Counted separately so
                # the detail string can say how much went unexamined.
                in_scope.append(f"{rid}.{field}")
                # crude but cheap: if the answer mentions this field name
                # in a way that suggests it stated a value, flag for review
                # (this is intentionally conservative -- a real
                # implementation might check more precisely)
                if field in answer_text and not guard_terms:
                    violations.append((rid, field))

    if violations:
        return {"passed": False,
                "detail": f"possible violations: {violations}"}

    if guard_terms and in_scope:
        return {
            "passed": True,
            "inconclusive": True,
            "detail": (f"INCONCLUSIVE -- the answer contains {guard_terms}, which "
                       f"suppresses this substring-based check for ALL fields on ALL "
                       f"cited records. {len(in_scope)} field(s) marked [not recorded] "
                       f"were in scope and went unexamined: {in_scope}. No violation "
                       f"was detected, but none could have been."),
        }

    if not in_scope:
        return {"passed": True,
                "detail": "no violations possible -- no cited record has a "
                          "[not recorded] field for the answer to fill in"}

    return {"passed": True,
            "detail": f"no violations detected across {len(in_scope)} "
                      f"[not recorded] field(s) in scope: {in_scope}"}


def check_factual_match(parsed_response, context_blocks):
    """Does a year mentioned in the answer actually match the cited
    record's real structured year(s)? Reuses normalize_year, same tool
    used throughout ingestion and contradiction detection -- catches the
    case where Haiku states a date that contradicts the very record it
    cites as its source.
    """
    from ingest import normalize_year

    if not parsed_response:
        return {"passed": False, "detail": "no response to check"}

    # Citation check FIRST, so an uncited response reports the same
    # inconclusive reason as the other two checks rather than the incidental
    # "no year mentioned" one.
    used_ids = set(parsed_response.get("record_ids_used") or [])
    if not used_ids:
        return {"passed": True, "inconclusive": True,
                "detail": INCONCLUSIVE_NO_CITATIONS}

    answer_text = parsed_response.get("answer") or ""
    answer_years = set(normalize_year(answer_text))
    if not answer_years:
        return {"passed": True, "detail": "no year mentioned in answer -- nothing to check"}

    blocks_by_id = {b["id"]: b for b in context_blocks}

    mismatches = []
    for rid in used_ids:
        block = blocks_by_id.get(rid)
        if not block:
            continue
        record_years = set(block.get("years") or [])
        if not record_years:
            continue  # record has no structured year to check against
        # If the answer mentions a year that's NOT in this record's own
        # years at all, that's worth flagging -- though note this is
        # conservative: an answer citing multiple records with different
        # years for legitimate comparative reasons wouldn't be a real
        # mismatch, so this flags for review rather than hard-failing.
        if not (answer_years & record_years):
            mismatches.append({"record_id": rid, "record_years": sorted(record_years),
                                "answer_years": sorted(answer_years)})

    return {
        "passed": len(mismatches) == 0,
        "detail": f"year mismatches: {mismatches}" if mismatches else "years consistent with cited records",
    }


def check_not_truncated(haiku_result):
    """Was the response complete, or did truncation detection fire?

    WHY THIS IS A VERIFICATION CHECK AND NOT A FOOTNOTE: silent truncation is
    the ONE fault the brief injects, and api_client.detect_truncation() was
    already finding it -- the flag was returned all the way up to
    answer_question() and then nothing read it. So a response that survived
    call_haiku()'s single retry and was STILL truncated came back with three
    clean checks and a full confidence score. Detecting the injected fault and
    then not reporting it is worse than not detecting it, because it produces a
    confident answer built on text that stops mid-thought.

    Counted in the pass rate, not merely displayed: a check that is shown but
    excluded from scoring is the same half-measure in a new place. Note this is
    score-NEUTRAL for clean answers -- 4/4 and 3/3 are both a 1.0 rate -- and
    only bites when truncation actually fires, which is the intended behaviour.
    """
    if not haiku_result:
        return {"passed": True, "inconclusive": True,
                "detail": "INCONCLUSIVE -- no API result was available to inspect."}

    if haiku_result.get("is_truncated"):
        reasons = haiku_result.get("truncation_reasons") or []
        return {
            "passed": False,
            "detail": (f"TRUNCATION SUSPECTED -- this response still tripped truncation "
                       f"detection after call_haiku()'s retry. Signals that fired: "
                       f"{reasons}. Treat the answer as possibly INCOMPLETE: the missing "
                       f"content is cut off, not absent, so anything the answer does not "
                       f"mention may simply never have been emitted."),
        }

    # THE FAULT FIRED AND WAS RECOVERED. This is NOT the same as "no truncation",
    # and reporting it as such was hiding the only evidence that the injected
    # fault had ever been exercised: the retry's return value replaces the
    # truncated attempt's, so a successful recovery left no trace in the result.
    prior = haiku_result.get("prior_truncation")
    if prior:
        return {
            "passed": True,
            "recovered": True,
            "detail": (f"TRUNCATION DETECTED AND RECOVERED -- attempt "
                       f"{prior.get('attempt')} (call_seq {prior.get('call_seq')}) came "
                       f"back truncated and was retried; this answer is the clean retry. "
                       f"Signals that fired on the truncated attempt: "
                       f"{prior.get('reasons')}. The answer below is complete, but this "
                       f"question cost TWO paid calls, and the injected silent-truncation "
                       f"fault is confirmed to have fired here."),
        }

    return {"passed": True, "detail": "no truncation signal fired"}


def score_checks(checks):
    """(passed, scorable_total) over a checks dict, excluding inconclusive ones.

    Single definition of the pass rate, so adding a check anywhere cannot
    accidentally use a different denominator rule than the others.
    """
    scorable = [c for c in checks.values() if not c.get("inconclusive")]
    return sum(1 for c in scorable if c["passed"]), len(scorable)


def run_verification_suite(parsed_response, context_blocks, haiku_result=None):
    """Runs every check and returns (checks, passed_count, scorable_count).

    scorable_count EXCLUDES checks that reported inconclusive=True, so the
    pass rate is computed only over checks that could actually have failed.
    Counting an inconclusive check as a pass is what let a response citing
    nothing report 3/3 and score 0.88/"high" -- the denominator has to shrink
    with the numerator or the rate is measuring the wrong thing.

    Consequence worth knowing: when every check is inconclusive, this returns
    a total of 0, and compute_confidence() already treats a zero total as a
    0.0 verification_score. In practice confidence_for_response() short-circuits
    those responses before the score is ever used.

    haiku_result is OPTIONAL so this stays callable with two arguments by any
    existing caller or test. When supplied, the truncation check is included.
    """
    checks = {
        "citation_membership": check_citation_membership(parsed_response, context_blocks),
        "not_recorded_violation": check_not_recorded_violation(parsed_response, context_blocks),
        "factual_match": check_factual_match(parsed_response, context_blocks),
    }
    if haiku_result is not None:
        checks["not_truncated"] = check_not_truncated(haiku_result)
    passed_count, scorable_total = score_checks(checks)
    return checks, passed_count, scorable_total


# ---------------------------------------------------------------------------
# Confidence scoring -- DETERMINISTIC, not Haiku's self-report
# ---------------------------------------------------------------------------

def compute_confidence(best_similarity, verification_passed, verification_total,
                        has_contradiction_on_used_records):
    """Confidence is a function of retrieval strength + verification pass
    rate + contradiction status -- NEVER a number Haiku reports about
    itself. This directly avoids the explicitly-penalized anti-pattern
    "confidence numbers with nothing behind them."
    """
    verification_score = verification_passed / verification_total if verification_total else 0
    retrieval_score = min(best_similarity, 1.0)
    contradiction_penalty = 0.3 if has_contradiction_on_used_records else 0.0

    raw_score = (0.5 * retrieval_score) + (0.5 * verification_score) - contradiction_penalty
    score = max(0.0, min(1.0, raw_score))

    # Band the ROUNDED score -- the same number that gets reported. Banding the
    # unrounded value made the two disagree at the boundary: retrieval 0.70 with
    # 1 of 5 checks passing gives 0.44999999999999996, which reports as
    # "score": 0.45 while landing in the "low" band, even though the documented
    # boundary is >= 0.45 -> medium. Anyone recomputing the label from the
    # printed score would get a different answer than the system did, which
    # defeats the point of exposing the number at all.
    reported_score = round(score, 2)

    if reported_score >= 0.75:
        raw_label = "high"
    elif reported_score >= 0.45:
        raw_label = "medium"
    else:
        raw_label = "low"

    # LABEL CAP: never "high" when a check that COULD have failed DID fail.
    #
    # WHY: the arithmetic alone put a caught fabrication in the "high" band. A
    # response citing a record it was never shown scored 0.78 -- one failed
    # check out of four leaves verification_score at 0.75, and 0.5*0.83 + 0.375
    # still clears the 0.75 threshold. Same for a truncated response at 0.76.
    # So verification could catch the single worst failure mode in the system,
    # correctly lower the number, and still hand back the word "high".
    #
    # The label is what a reader acts on; the score is what they audit. A label
    # that says "high" while a deterministic check is failing is the brief's
    # "confidence numbers with nothing behind them" surviving in the one field
    # most likely to be read on its own.
    #
    # This only ever DOWNGRADES. A response already at medium or low is not
    # promoted, and inconclusive checks are excluded upstream by score_checks()
    # so they cannot trigger the cap -- only a genuine failure can.
    any_check_failed = bool(verification_total) and verification_passed < verification_total
    label = "medium" if (any_check_failed and raw_label == "high") else raw_label

    return {
        "score": reported_score,
        "label": label,
        "components": {
            "retrieval_score": round(retrieval_score, 2),
            "verification_score": round(verification_score, 2),
            "contradiction_penalty": contradiction_penalty,
            # True only when the cap ACTUALLY changed the label, so the flag is
            # not itself a slightly-false statement on responses where the
            # label was already below "high".
            "label_capped_by_failed_check": label != raw_label,
        },
    }


# Used when the response cited NOTHING. Every check below is vacuous, so the
# second clause is literally true.
NOT_APPLICABLE_CONFIDENCE_REASON = (
    "no factual claim was asserted and no record was cited, so there is nothing "
    "to be confident about. The verification checks below pass vacuously on an "
    "empty citation set and are reported as inconclusive, not as passes."
)

# Used when the model set answerable=false but DID cite records -- which is what
# the dev demo's dimensions question actually did. The reason has to differ,
# because saying "no record was cited" there would itself be a false statement
# in user-facing output, which is exactly the failure mode this pass is fixing
# elsewhere. Same verdict, accurate justification.
NOT_APPLICABLE_DECLINED_REASON = (
    "the model set answerable=false, so no factual claim was asserted and there is "
    "nothing to be confident about. Records WERE cited (see record_ids_used), so "
    "the checks below did run against them -- but a pass rate on a response that "
    "asserts nothing is not evidence about anything, and is deliberately not "
    "converted into a score."
)


def confidence_for_response(parsed_response, best_similarity, verification_passed,
                             verification_total, has_contradiction_on_used_records):
    """Decides whether a confidence score is MEANINGFUL for this response at
    all, and only then delegates to compute_confidence().

    REAL BUG THIS FIXES, measured on the dev demo run: a correct DECLINE was
    reported at 0.88/"high". Three of the eight demo questions did it, and all
    three were the system working exactly as designed.

    The mechanism is that every verification check passes VACUOUSLY on an empty
    citation set -- check_citation_membership has no citations to find
    fabricated, check_not_recorded_violation iterates an empty used_ids, and
    check_factual_match reports "no year mentioned in answer". So
    verification_score is 1.0 and 0.5*0.77 + 0.5*1.0 rounds to 0.88 for an
    answer that asserts nothing about anything.

    That is both of the brief's §7 anti-patterns in one field: a confidence
    number with nothing behind it, and the absence of a detectable error being
    read as success.

    A response that cites nothing therefore gets NO score -- not a low one. A
    low score is still a claim about how well-supported an answer is, and there
    is no answer to support. `reason` says why, so the absence is explained
    rather than merely blank.
    """
    cited = (parsed_response.get("record_ids_used") or []) if parsed_response else []
    answerable = parsed_response.get("answerable") if parsed_response else None

    if not cited:
        reason = NOT_APPLICABLE_CONFIDENCE_REASON
    elif not answerable:
        reason = NOT_APPLICABLE_DECLINED_REASON
    else:
        return compute_confidence(best_similarity, verification_passed,
                                   verification_total, has_contradiction_on_used_records)

    return {
        "score": None,
        "label": "not_applicable",
        "reason": reason,
        "components": None,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

ANSWER_MAX_TOKENS = 1024


def answer_question(question, retriever, dev_mode=False, top_k=10,
                     max_tokens=ANSWER_MAX_TOKENS):
    """The full pipeline for one question. Ties together every module
    built so far. Buildable/testable end-to-end right now -- if
    credentials are missing, call_haiku() returns cleanly and this
    function reports that clearly rather than crashing.

    max_tokens=1024 matches the brief's own client example. Previously 600,
    which was too tight for the required output: the response has to carry
    answer + limitations + one {id, reason} object per retrieved-but-unused
    record, and with top_k=10 that can plausibly exceed 600 tokens. A
    genuine cap-truncation there is not free -- detect_truncation() flags it
    and call_haiku() spends a WHOLE EXTRA CALL retrying, so an over-tight
    cap costs more budget than the larger cap it was trying to save.

    top_k=10 is EXPLICIT here, matching what was actually validated via
    test_pipeline.py's manual testing (entity groupings, context block
    counts, etc. were all checked against this value). REAL BUG FOUND by
    running this file directly: without specifying top_k here, this
    function was silently falling back to retrieval.py's own class
    default of top_k=20 -- double the candidates actually validated,
    producing 17 context blocks instead of the expected/tested 9 for the
    same question. More candidates = more tokens spent per call than
    intended, which matters directly for the "is this scalable" question.
    Making this explicit here, rather than relying on retrieval.py's
    internal default, prevents this kind of silent drift.
    """
    candidates, abstain, best_sim, signals = retriever.retrieve(question, top_k=top_k)

    if abstain:
        # Report the signal that ACTUALLY fired. The old message always blamed
        # dense similarity, which would now be wrong whenever the BM25 floor is
        # what stopped the call -- and BM25 is the trigger for exactly the junk
        # questions the dense check was letting through.
        return {
            "question": question,
            "abstained": True,
            "reason": "Abstained before any paid call: " + "; ".join(signals["abstain_reasons"]),
            "retrieval_signals": signals,
            "answer": None,
        }

    context_blocks, folded_ids_map = assemble_context_blocks(candidates)
    system_prompt, messages = build_prompt(question, context_blocks)

    haiku_result = call_haiku(messages, system=system_prompt, max_tokens=max_tokens,
                               dev_mode=dev_mode, stage="reasoning", expect_json=True)

    if haiku_result["error_type"]:
        return {
            "question": question,
            "abstained": False,
            "error": haiku_result["error_type"],
            # The server's own error text, when there was one. On a 4xx this
            # names the offending field, which is what distinguishes a wrong
            # CORTEX_MODEL from a wrong CORTEX_MESSAGE_FORMAT -- worth
            # surfacing all the way up rather than only printing it.
            "error_detail": haiku_result.get("error_detail"),
            "answer": None,
            "context_blocks_prepared": len(context_blocks),
        }

    parsed_response, parse_error = parse_haiku_response(haiku_result["content"])

    if parse_error and not parsed_response:
        return {
            "question": question,
            "abstained": False,
            "error": f"failed_to_parse_response: {parse_error}",
            "answer": None,
            "raw_content": haiku_result["content"],
        }

    checks, passed, total = run_verification_suite(parsed_response, context_blocks,
                                                    haiku_result=haiku_result)

    has_contradiction = any(
        b["internal_contradiction"] is not None
        for b in context_blocks
        if b["id"] in set(parsed_response.get("record_ids_used", []))
    )

    confidence = confidence_for_response(parsed_response, best_sim, passed, total,
                                          has_contradiction)

    full_provenance = build_full_provenance(context_blocks, folded_ids_map, parsed_response)

    return {
        "question": question,
        "abstained": False,
        "answer": parsed_response.get("answer"),
        "answerable": parsed_response.get("answerable"),
        "record_ids_used": parsed_response.get("record_ids_used"),
        "limitations": parsed_response.get("limitations"),
        "full_provenance": full_provenance,
        "confidence": confidence,
        "verification_checks": checks,
        # The retrieval evidence behind confidence.components.retrieval_score.
        # Previously published ONLY on the abstain path, which meant the one
        # number a reader would want to interrogate came with nothing to
        # interrogate it against on every answered question.
        "retrieval_signals": signals,
        # Retained for backward compatibility with anything reading the flag
        # directly; the graded outcome now lives in
        # verification_checks["not_truncated"].
        "is_truncated": haiku_result["is_truncated"],
        # Evidence that the injected fault fired on this question even though the
        # answer that came back is complete. Surfaced at top level, not only
        # inside the check, because "this cost two calls" is a budget fact as
        # well as a verification one.
        "truncation_recovered": bool(haiku_result.get("truncation_recovered")),
        "prior_truncation": haiku_result.get("prior_truncation"),
        "call_seq": haiku_result["call_seq"],
        "budget_remaining": haiku_result["budget_remaining"],
    }


if __name__ == "__main__":
    # dev_mode is now an EXPLICIT flag rather than hardcoded True, which it was
    # until now. The brief, §5: "While you're building, send the header
    # X-Cortex-Mode: dev... Drop the header for the run you submit. We log
    # both." With dev_mode hardcoded on, every run of this file -- including
    # one used to produce the submitted demo transcript -- drew on the 50k
    # sandbox instead of the real budget. Since Cortex logs both, that would
    # have been visible on their side as a submission run that never really
    # ran. Defaults to OFF so the honest thing happens unless --dev is asked
    # for explicitly.
    args = [a for a in sys.argv[1:] if a != "--dev"]
    dev = "--dev" in sys.argv

    if len(args) < 2:
        print('Usage: python reasoning.py [--dev] <normalized.jsonl> "<question>"')
        print()
        print('  --dev   send X-Cortex-Mode: dev, drawing on the free 50,000-token')
        print('          sandbox instead of the 200,000-token submission budget.')
        print('          Use this while building. OMIT it for the submitted run.')
        sys.exit(0)

    filepath, question = args[0], args[1]

    records = load_records(filepath)
    print(f"Loaded {len(records)} records")
    retriever = HybridRetriever(records)

    print(f"[reasoning] dev_mode={dev} -- "
          + ("free 50k sandbox (X-Cortex-Mode: dev)" if dev
             else "REAL 200k submission budget, no dev header"))

    result = answer_question(question, retriever, dev_mode=dev)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n" + get_tracker().summary())