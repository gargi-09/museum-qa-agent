"""
entity_resolution.py -- Deterministic entity resolution + contradiction
detection over the museum corpus.

DETERMINISTIC BY DESIGN: uses fixed-rule normalization (name reordering,
punctuation stripping, parenthetical-qualifier stripping) followed by EXACT
string equality -- not fuzzy similarity scoring, not embedding-based
clustering, not keyword search. Same input always produces the same
output; every grouping decision is explainable by pointing to the exact
rule that fired.

WHY THIS MATTERS: the institution field itself is already a fully reliable,
deterministic signal for "which museum" (verified 0 mismatches against the
id prefix during ingestion). Combined with exact-match-after-normalization
on (title, artist), this lets us deterministically detect the assignment's
core "same entity recorded differently by different institutions" scenario,
without any fuzzy/probabilistic logic.

VALIDATED AGAINST REAL DATA (not assumed): tested against the full base
corpus and found 405 cross-institution candidate groups. Spot-checked two
by hand (Witkiewicz's "Arthur Rubinstein, Zakopane"; Man Ray's "Return to
Reason") -- both confirmed genuine matches via independent evidence
(matching dimensions after unit conversion, near-identical descriptive
content) -- not just coincidental title reuse.

IMPORTANT CAVEAT, FOUND AND QUANTIFIED: generic titles ("Untitled",
"Composition", "Still Life", etc.) are a real weakness of pure title+artist
matching, since artists (especially minimalists) reuse these titles across
genuinely distinct works. Quantified: only 16 of 405 groups (4%) use a
generic title. These are flagged as LOWER CONFIDENCE rather than silently
treated the same as distinctive-title matches.

BONUS FINDING: comparing already-normalized `years` lists (from ingest.py)
between records in a confirmed group gives a SECOND deterministic check for
free -- 244 of 405 groups (60%) show zero year overlap between institutions,
a genuine, numeric, no-keyword-search-required contradiction signal. Far
larger and more systematic than the ~18 records found via the earlier
keyword-based scan ("at odds with", "discrepancy").
"""
import json
import re
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import normalize_year  # reuse, don't reimplement


GENERIC_TITLES = {
    "untitled", "no title", "composition", "self portrait",
    "still life", "landscape", "abstraction", "portrait",
}


def normalize_artist(artist):
    """Deterministic rule: reorder 'Last, First' -> 'first last', strip
    punctuation, lowercase. Verified against a real corpus case: matches
    'Frankenthaler, Helen' with 'Helen Frankenthaler'.
    """
    if not artist:
        return ""
    artist = artist.strip()
    if "," in artist:
        parts = [p.strip() for p in artist.split(",", 1)]
        if len(parts) == 2:
            artist = f"{parts[1]} {parts[0]}"
    return re.sub(r"[^\w\s]", "", artist.lower()).strip()


def normalize_title(title):
    """Deterministic rule: strip trailing parenthetical qualifiers
    (e.g. '(plate 10)'), strip punctuation, lowercase. Verified: matches
    'I Need Yellow' with 'I Need Yellow (plate 10)'.
    """
    if not title:
        return ""
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title.strip())
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def build_entity_groups(records):
    """Groups records by exact (normalized_title, normalized_artist) match.
    Returns a list of group dicts, each with the records, whether it spans
    multiple institutions, and a confidence flag (generic titles are
    lower-confidence).
    """
    raw_groups = defaultdict(list)
    for r in records:
        key = (normalize_title(r.get("title")), normalize_artist(r.get("artist")))
        if key[0] and key[1]:
            raw_groups[key].append(r)

    groups = []
    for (norm_title, norm_artist), members in raw_groups.items():
        if len(members) < 2:
            continue
        institutions = set(m["institution"] for m in members)
        groups.append({
            "normalized_title": norm_title,
            "normalized_artist": norm_artist,
            "members": members,
            "spans_institutions": len(institutions) > 1,
            "institutions": institutions,
            "confidence": "low" if norm_title in GENERIC_TITLES else "high",
        })
    return groups


def check_year_contradiction(group):
    """Deterministic check: do all members of this group share at least
    one common year? Compares already-normalized year lists -- pure
    number comparison, no keyword matching, no NLP.

    Also returns a vote count per year, so a lone outlier disagreeing with
    a strong majority (e.g. 6 records say 1973, 1 says 1969) can be told
    apart from an even split (e.g. 1 vs 1) -- these are meaningfully
    different situations for confidence scoring later, not the same flat
    "contradiction" flag.

    Returns (has_contradiction, all_years_seen, year_vote_counts).
    """
    year_sets = [set(normalize_year(m.get("year_raw") or m.get("year")))
                 for m in group["members"]]
    year_sets = [s for s in year_sets if s]
    if not year_sets:
        return False, set(), {}

    vote_counts = defaultdict(int)
    for s in year_sets:
        for y in s:
            vote_counts[y] += 1

    common = set.intersection(*year_sets)
    all_years = set.union(*year_sets)
    has_contradiction = not common and bool(all_years)
    return has_contradiction, all_years, dict(vote_counts)


def pick_representative(group):
    """Selects one record to send in full to the reasoning step, to avoid
    sending near-duplicate text for every cluster member (token savings).

    If there's a year contradiction with a clear majority, prefers a
    member matching the majority year (more likely correct) over one
    matching a minority/outlier year. Falls back to longest description
    as a simple, deterministic tiebreaker.
    """
    has_contradiction, all_years, vote_counts = check_year_contradiction(group)
    if has_contradiction and vote_counts:
        sorted_votes = sorted(vote_counts.items(), key=lambda x: -x[1])
        if len(sorted_votes) >= 2 and sorted_votes[0][1] > sorted_votes[1][1]:
            majority_year = sorted_votes[0][0]
            majority_members = [
                m for m in group["members"]
                if majority_year in set(normalize_year(m.get("year_raw") or m.get("year")))
            ]
            if majority_members:
                return max(majority_members, key=lambda m: len(m.get("description") or ""))

    return max(group["members"], key=lambda m: len(m.get("description") or ""))


def summarize_group_for_prompt(group):
    """Builds a compact, human-readable summary of a group for inclusion
    in the reasoning prompt: the representative's full text, plus a
    one-line note about the other members and any detected contradiction,
    including whether it's a majority/minority split or an even disagreement.
    """
    rep = pick_representative(group)
    other_ids = [m["id"] for m in group["members"] if m["id"] != rep["id"]]
    has_contradiction, all_years, vote_counts = check_year_contradiction(group)

    note_parts = []
    if group["spans_institutions"]:
        insts = ", ".join(sorted(group["institutions"]))
        note_parts.append(f"Also recorded independently by: {insts} (record IDs: {other_ids})")
    else:
        note_parts.append(f"{len(other_ids)} additional related catalog entries: {other_ids}")

    if group["confidence"] == "low":
        note_parts.append("NOTE: generic title -- these may be DISTINCT works, not confirmed duplicates.")

    if has_contradiction:
        sorted_votes = sorted(vote_counts.items(), key=lambda x: -x[1])
        vote_str = ", ".join(f"{y} ({c} record{'s' if c != 1 else ''})" for y, c in sorted_votes)
        if len(sorted_votes) >= 2 and sorted_votes[0][1] > sorted_votes[1][1]:
            note_parts.append(f"CONTRADICTION (majority/minority split): {vote_str}")
        else:
            note_parts.append(f"CONTRADICTION (even disagreement, no clear majority): {vote_str}")

    return {
        "representative": rep,
        "note": " ".join(note_parts),
        "has_contradiction": has_contradiction,
    }


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


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/normalized.jsonl"
    records = load_records(filepath)
    print(f"Loaded {len(records)} records\n")

    groups = build_entity_groups(records)
    cross_inst = [g for g in groups if g["spans_institutions"]]
    same_inst = [g for g in groups if not g["spans_institutions"]]

    print(f"Total entity groups (2+ records, same normalized title+artist): {len(groups)}")
    print(f"  Cross-institution (assignment's core scenario): {len(cross_inst)}")
    print(f"  Same-institution (multi-part/proof clusters): {len(same_inst)}")

    low_conf = [g for g in groups if g["confidence"] == "low"]
    print(f"  Low-confidence (generic title): {len(low_conf)}")

    contradictions = [g for g in groups if check_year_contradiction(g)[0]]
    print(f"\nGroups with a deterministic year contradiction: {len(contradictions)}")

    print("\nSample cross-institution groups with contradictions:")
    shown = 0
    for g in cross_inst:
        has_contra, years, vote_counts = check_year_contradiction(g)
        if has_contra and shown < 5:
            ids = [(m["id"], m["institution"][:3], m.get("year_raw") or m.get("year")) for m in g["members"]]
            print(f"  {g['normalized_title']!r} / {g['normalized_artist']!r} "
                  f"[{g['confidence']} confidence]: {ids}")
            shown += 1


if __name__ == "__main__":
    main()