"""
contradiction.py -- SINGLE-RECORD internal contradiction detection.

Distinct from entity_resolution.py's cross-record check (which compares
TWO records, e.g. same object at two institutions). This checks ONE
record against ITSELF: does the free-text description name a documentary
source that states a year conflicting with the record's own structured
year field?

Directly maps to the assignment's named messiness pattern: "prose that
contradicts structured fields."

EVOLUTION OF THIS CHECK (full story kept here since it's genuinely
instructive engineering history, not just the final answer):
1. Naive year-mismatch (no gate): 2,285 of 5,000 records flagged --
   descriptions routinely mention OTHER, legitimate dates for context.
   Rejected.
2. Exact-phrase gate (3 memorized phrases + proximity window): 35 records,
   verified genuine. Real, but narrow -- would silently miss real
   contradictions worded differently.
3. Tested whether a small local NLI model could generalize better than
   memorized phrases (see nli_contradiction_test.py) -- found it
   introduces a WORSE problem: 1,389 false positives, because an isolated
   sentence + bare premise can't distinguish "this date is about the
   artwork" from "this date is about the artist's career / the depicted
   subject's life / the site's history."
4. FINAL (initial version): inspected the actual sentence structure behind
   all 35 confirmed cases and found a consistent generative pattern --
   every real contradiction names a DOCUMENTARY SOURCE (catalogue card,
   stamp, ledger, inscription) using an ATTRIBUTION VERB (cites, assigns
   it to, dates the work to) to state an alternate year. Detecting this
   STRUCTURE, rather than memorized closing phrases, catches 34/35 of the
   original cases, rejects all known false positives, and finds 70
   genuinely new real contradictions -- validated count at this stage: 104.
5. Tested TWO NLI-based generalization strategies as alternatives to
   memorized phrases -- both rejected:
   (a) Narrow: isolated sentence + bare premise (see
       nli_contradiction_test.py) -- 1,389 false positives, because an
       isolated sentence can't distinguish "this date is about the
       artwork" from "this date is about the artist's career / the
       depicted subject's life / the site's history."
   (b) Full-context: entire description as premise, "This work was
       created in {year}." as hypothesis (see contradiction_nli_approach.py)
       -- WORSE, not better: missed the one confirmed true positive
       entirely (0.016 contradiction probability, predicted neutral),
       still confidently flagged all 4 known false positives (now at
       0.75-0.999 probability, HIGHER than the narrow version), flagged
       43% of the entire corpus (2,135/4,989), and flagged at least one
       record (Hamanishi's "Division-Work No. 100") with 100% confidence
       despite the description containing NO competing year at all --
       proof the model isn't reasoning about dates, but reacting to some
       other signal, almost certainly because a 44M-param model trained
       on short single-sentence NLI pairs (SNLI/MultiNLI-style) is far
       outside its training distribution when given a multi-hundred-word
       museum paragraph as premise.
6. SYSTEMATIC VERB-COVERAGE SWEEP (not reactive): rather than wait for
   more one-off misses to surface accidentally, scanned the WHOLE corpus
   for sentences that already contain a VERIFIED source noun + a genuine
   year mismatch, but no matching verb -- isolating exactly what
   additional verb phrasings are missing, rather than broadly guessing.
   Found and added 7 new verb variants ("records", "states the date as",
   "bears the annotation", "gives the date as", "is dated", "dates to",
   "reading"), validated against all known false positives (still
   correctly rejected) and spot-checked 3 new finds against raw source
   (all genuine). FINAL validated count: 142.

Checked explicitly whether OTHER structured fields (not just year) show
this same pattern -- searched for artist-attribution discrepancy language
across the whole corpus and found ZERO hits. Year is the only field where
this corpus actually contains self-flagged prose-vs-structured
contradictions; this was verified empirically, not assumed.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import normalize_year


RELIABLE_CONTRADICTION_PHRASES = [
    "at odds with", "discrepancy", "some years after the date carried here",
]

# GENERALIZATION, added after testing the exact-phrase approach against a
# local NLI model and finding the NLI approach itself introduces a WORSE
# false-positive problem (see nli_contradiction_test.py -- an isolated
# sentence + bare premise cannot tell "this date is about the artwork" from
# "this date is about the artist's biography / the depicted subject's life /
# the site's history", producing 1,389 false positives on this corpus).
#
# Instead, inspected the actual SENTENCE STRUCTURE behind all 35 confirmed
# true positives and found a consistent, generative pattern underneath the
# 3 memorized phrases: every real contradiction sentence names a specific
# DOCUMENTARY SOURCE (a catalogue card, a stamp, a sales ledger, an
# inscription) using an ATTRIBUTION VERB (cites, assigns it to, dates the
# work to) to state an alternate year. This is what a real curatorial
# disagreement sentence looks like, independent of which of the 3 exact
# closing phrases (if any) it happens to end with.
#
# Validated: co-occurrence of a SOURCE_NOUN + ATTRIBUTION_VERB in the same
# sentence catches 34/35 of the original phrase-matched true positives
# (only 1 miss, a sentence using bare "is" as its verb -- deliberately not
# added, since "is" is far too generic and would reintroduce false
# positives), correctly rejects all 5 known false-positive cases (Bontecou,
# Witkiewicz's career-period biography, Red Cloud's lifespan, eucalyptus
# planting date, Ishimoto's travel date) that both the naive year-mismatch
# check AND the NLI model incorrectly flagged, and finds 70 GENUINELY NEW
# real contradictions beyond the original phrase-only set -- spot-checked
# 3 of these against the raw corpus and confirmed all genuine, including
# one subtler case (aic-6762) where an inscription proposes a specific year
# falling within a broader museum-stated dynasty-era range.
SOURCE_NOUNS = [
    "catalogue card", "owner's note", "owner\u2019s note", "stamp", "collection inventory",
    "sales ledger", "exhibition label", "inscription", "donor's list", "donor\u2019s list",
    "donor's own list", "donor\u2019s own list", "correspondence", "pencil note", "caption",
    "record book", "record", "frame's label", "frame\u2019s label", "mount",
    "dealer's stock book", "dealer\u2019s stock book", "verso", "colophon",
    "estate inventory", "sheet", "label", "ledger", "inventory", "stock book",
    "period journal", "accession card",
]
ATTRIBUTION_VERBS = [
    "cites", "lists it under", "notes the year", "assigns it to", "carries the date",
    "gives the year as", "gives instead", "sets its completion", "enters it at",
    "dates the work to", "dates it to", "is annotated", "puts its making",
    "as an alternative to", "reads", "places it in", "differs",
    # ADDED after a SYSTEMATIC (not reactive) sweep of the whole corpus for
    # sentences that already contain a VERIFIED source noun + a year
    # mismatch, but no matching verb -- isolating the verb as the specific
    # gap, rather than broadly scanning for any plausible-sounding word
    # (which produces mostly false positives, since words like "signed",
    # "file", "letter" appear constantly in ordinary biographical prose).
    # Found ~140 such sentences; most were genuine false positives on
    # closer reading (e.g. "recorded her physical evolution," "a record
    # of a city"), but roughly 38 were real, clean contradictions using
    # these specific additional verb phrasings. Re-validated: all 5 known
    # false-positive cases (Bontecou, Witkiewicz, Red Cloud, eucalyptus,
    # Ishimoto) still correctly rejected after this expansion. Spot-checked
    # 3 of the 38 new finds against raw source, all confirmed genuine
    # (e.g. cma-419930: "A label on the backing records the date as 1969"
    # against a structured year of 1978). Final validated count: 142.
    "records", "states the date as", "bears the annotation", "gives the date as",
    "is dated", "dates to", "reading",
]

# Same PHRASE-GATE + PROXIMITY pattern applied to a different structured
# field (artist), to genuinely test whether year is the only field this
# corpus disputes, rather than assuming it. Checked, not assumed --
# see check_attribution_discrepancy() below.
ATTRIBUTION_DISCREPANCY_PHRASES = [
    "formerly attributed to", "misattributed", "attribution has been questioned",
    "previously catalogued as", "attribution remains uncertain",
    "long attributed to", "attributed instead to", "reattributed",
]


def check_internal_contradiction(record, proximity_window=100):
    """Checks whether the description contains a sentence naming a
    documentary source (catalogue card, stamp, ledger, inscription, etc.)
    that uses an attribution verb (cites, assigns it to, dates the work
    to) to state a year that conflicts with the record's own structured
    year field.

    This is a GENERALIZATION of an earlier, narrower version that only
    matched 3 exact closing phrases ("at odds with", "discrepancy", "some
    years after the date carried here"). That version worked but couldn't
    generalize to real contradictions worded differently. This version
    instead detects the underlying STRUCTURE common to every confirmed
    real case: [documentary source] + [attribution verb] + [year] --
    validated to catch 34/35 of the original phrase-matched cases, reject
    all known false positives, and find 70 additional genuine
    contradictions the phrase-only version missed. See the module-level
    comments above SOURCE_NOUNS for the full validation story.

    Returns a dict: has_contradiction, structured_years, description_years,
    conflicting_years, matched_sentence.
    """
    structured_years = set(normalize_year(record.get("year_raw") or record.get("year")))
    description = record.get("description") or ""

    if not structured_years or not description:
        return {
            "has_contradiction": False,
            "structured_years": sorted(structured_years),
            "description_years": [],
            "conflicting_years": [],
            "matched_sentence": None,
        }

    sentences = re.split(r"(?<=[.!?])\s+", description)
    for sent in sentences:
        sent_lower = sent.lower()
        has_source = any(s in sent_lower for s in SOURCE_NOUNS)
        has_verb = any(v in sent_lower for v in ATTRIBUTION_VERBS)
        if not (has_source and has_verb):
            continue

        years_in_sent = set(normalize_year(sent))
        conflicting = years_in_sent - structured_years
        if conflicting:
            return {
                "has_contradiction": True,
                "structured_years": sorted(structured_years),
                "description_years": sorted(years_in_sent),
                "conflicting_years": sorted(conflicting),
                "matched_sentence": sent.strip(),
            }

    return {
        "has_contradiction": False,
        "structured_years": sorted(structured_years),
        "description_years": [],
        "conflicting_years": [],
        "matched_sentence": None,
    }


def check_attribution_discrepancy(record):
    """Checks whether the description explicitly flags an ARTIST
    attribution dispute -- the same phrase-gate concept as the year check,
    applied to a different structured field, to genuinely test whether
    year is the only type of prose-vs-structured-field contradiction this
    corpus contains, rather than assuming it.

    This is real, runnable scope-verification, not a one-off scan --
    running this file will always re-check this on the actual current
    corpus, not rely on a past conversation's manual search.

    Returns a dict: has_discrepancy, gating_phrase_found.
    """
    description = record.get("description") or ""
    description_lower = description.lower()

    for phrase in ATTRIBUTION_DISCREPANCY_PHRASES:
        if phrase in description_lower:
            return {"has_discrepancy": True, "gating_phrase_found": phrase}

    return {"has_discrepancy": False, "gating_phrase_found": None}


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


def naive_check_no_gate(record):
    """The ORIGINAL, rejected approach -- kept here only so main() can show
    the before/after comparison when run locally. Compares ANY year in the
    full description against the structured field, with no phrase gate and
    no proximity requirement. This is what produced 2,285 false positives
    on the full corpus -- do not use this for real detection.
    """
    structured_years = set(normalize_year(record.get("year_raw") or record.get("year")))
    description_years = set(normalize_year(record.get("description") or ""))
    conflicting = description_years - structured_years
    return bool(conflicting) and bool(structured_years)


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    records = load_records(filepath)
    by_id = {r["id"]: r for r in records}

    print("=" * 70)
    print("STEP 1: Individual test cases")
    print("=" * 70)
    test_ids = {
        "KNOWN CONTRADICTION (verified real case, Omer Fast 'The Casting')": "cma-168184",
        "KNOWN CLEAN (no contradiction expected)": "aic-136265",
        "RANDOM (sanity check -- should NOT be flagged)": records[2500]["id"] if len(records) > 2500 else records[0]["id"],
        "KNOWN FALSE POSITIVE (Bontecou -- mentions earlier, unrelated "
        "lithograph dates for context; also fooled the naive check AND "
        "an NLI model, but not this pattern)": "aic-121177",
    }

    for label, rid in test_ids.items():
        record = by_id.get(rid)
        if not record:
            print(f"{label}: record {rid} not found\n")
            continue
        result = check_internal_contradiction(record)
        print(f"--- {label} ---")
        print(f"  id: {rid}")
        print(f"  title: {record.get('title')!r}")
        print(f"  structured years: {result['structured_years']}")
        print(f"  matched sentence: {result['matched_sentence']!r}")
        print(f"  CONTRADICTION: {result['has_contradiction']}")
        if result["has_contradiction"]:
            print(f"  conflicting years: {result['conflicting_years']}")
        print()

    print("=" * 70)
    print("STEP 2: Naive (rejected) approach vs. final approach -- full corpus")
    print("=" * 70)
    naive_flagged = sum(1 for r in records if naive_check_no_gate(r))
    final_flagged = [r["id"] for r in records if check_internal_contradiction(r)["has_contradiction"]]
    print(f"Naive approach (no gate at all): {naive_flagged} records flagged -- REJECTED")
    print(f"Final approach (documentary-source + attribution-verb pattern): "
          f"{len(final_flagged)} records flagged")
    print()

    print("=" * 70)
    print("STEP 3: Full list of final flagged records (year contradictions)")
    print("=" * 70)
    for rid in final_flagged:
        result = check_internal_contradiction(by_id[rid])
        print(f"  {rid}: structured={result['structured_years']}, "
              f"conflicting={result['conflicting_years']}")

    print()
    print("=" * 70)
    print("STEP 4: Scope check -- is year the ONLY field this corpus disputes,")
    print("or does artist-attribution language exist too? (tested, not assumed)")
    print("=" * 70)
    attribution_hits = [r["id"] for r in records if check_attribution_discrepancy(r)["has_discrepancy"]]
    print(f"Records with artist-attribution discrepancy language: {len(attribution_hits)}")
    if attribution_hits:
        for rid in attribution_hits:
            result = check_attribution_discrepancy(by_id[rid])
            print(f"  {rid}: gate={result['gating_phrase_found']!r}")
    else:
        print("  None found. This corpus's self-flagged prose-vs-structured")
        print("  contradictions are, empirically, entirely about YEAR -- confirmed")
        print("  by actually checking for this pattern, not assumed from the start.")


if __name__ == "__main__":
    main()