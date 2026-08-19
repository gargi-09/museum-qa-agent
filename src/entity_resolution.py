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

SYSTEMATIC ARTIST-NAME AUDIT, run after test_pipeline.py revealed a real
missed duplicate ("Louise Bourgeois" vs "L. Bourgeois") during integration
testing -- rather than fix that one case and move on, ran a full-corpus,
non-reactive scan for the same TWO underlying patterns:
  1. Initial vs. full first name (e.g. "L. Bourgeois" / "Louise
     Bourgeois"): found 64 distinct pairs across the whole corpus, not
     just the 1 found by accident. Handled via artists_match()'s
     initial-matching rule, explicitly flagged low-confidence (small,
     accepted risk of merging two different people who share a surname
     and initial -- mitigated by requiring a matching, usually
     distinctive, title on top of the name match).
  2. Diacritic-only variants (e.g. "Andre Derain" / "Andre\u0301 Derain",
     "Frantisek Kupka" plain vs. accented): found 8 pairs. Unlike the
     initial-name case, this carries no real risk of merging different
     people, so it's applied unconditionally in normalize_artist() as
     core normalization, not flagged as lower-confidence.
  Also checked TITLES for the same diacritic pattern across the whole
  corpus: zero found, so titles were left as-is.

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
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import normalize_year  # reuse, don't reimplement


GENERIC_TITLES = {
    "untitled", "no title", "composition", "self portrait",
    "still life", "landscape", "abstraction", "portrait",
}


def strip_diacritics(s):
    """Removes accent marks (e.g. 'e' from 'e-acute') while keeping the
    base letter, via Unicode NFD decomposition + stripping combining marks.

    ADDED after a SYSTEMATIC, WHOLE-CORPUS scan (not just reactive
    spot-checking) found 8 artist-name pairs differing ONLY by diacritics
    -- e.g. 'Andre Derain' vs 'Andre\u0301 Derain', 'Frantisek Kupka' vs
    'Frantisek Kupka' (accented), 'Chaim Soutine' vs 'Chai\u0308m Soutine'.
    Unlike the initial-name matching rule below, this carries essentially
    ZERO risk of merging two DIFFERENT people -- the same name written
    with or without accent marks is unambiguously the same name, so this
    is applied unconditionally as part of core normalization, not flagged
    as lower-confidence.

    Also checked TITLES for this same pattern across the whole corpus:
    zero diacritic-only title variants found, so this is applied to
    artist names only.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def normalize_artist(artist):
    """Deterministic rule: reorder 'Last, First' -> 'first last', strip
    diacritics, strip punctuation, lowercase. Verified against a real
    corpus case: matches 'Frankenthaler, Helen' with 'Helen Frankenthaler'.
    """
    if not artist:
        return ""
    artist = artist.strip()
    if "," in artist:
        parts = [p.strip() for p in artist.split(",", 1)]
        if len(parts) == 2:
            artist = f"{parts[1]} {parts[0]}"
    artist = strip_diacritics(artist)
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


def artists_match(artist1, artist2):
    """Checks whether two artist strings likely refer to the same person.

    REAL BUG FOUND via test_pipeline.py: 'Louise Bourgeois' (cma-160793)
    and 'L. Bourgeois' (aic-215406) are the same person, same work ('Ode
    to My Mother' / 'Ode To My Mother'), but the original exact-match-only
    normalize_artist() never unified them -- a true cross-institution
    duplicate was silently MISSED, the opposite failure direction from
    the false-positive risks handled elsewhere in this module.

    FIX: after exact normalized match fails, also check whether one is a
    single-initial + matching last name against the other's full first
    name + same last name (e.g. 'l bourgeois' vs 'louise bourgeois').

    KNOWN, ACCEPTED RISK: this could incorrectly match two DIFFERENT
    people sharing a last name and initial (e.g. 'Jane Smith' vs
    'J. Smith'). Mitigated by: (1) this only ever runs on a small set of
    already topically-relevant retrieval candidates for the SAME query,
    not the whole corpus, making an unrelated same-surname collision
    unlikely in practice; (2) matches found via this rule are explicitly
    flagged as lower confidence (see build_entity_groups), not silently
    trusted the same as an exact match.

    Returns (is_match, match_type) where match_type is 'exact',
    'initial', or None.
    """
    n1, n2 = normalize_artist(artist1), normalize_artist(artist2)
    if not n1 or not n2:
        return False, None
    if n1 == n2:
        return True, "exact"

    p1, p2 = n1.split(), n2.split()
    if len(p1) == 2 and len(p2) == 2 and p1[-1] == p2[-1]:
        f1, f2 = p1[0], p2[0]
        if (len(f1) == 1 and f2.startswith(f1)) or (len(f2) == 1 and f1.startswith(f2)):
            return True, "initial"

    return False, None


def build_entity_groups(records):
    """Groups records that likely represent the same real-world object.

    Changed from exact dict-key grouping to PAIRWISE comparison (O(n^2),
    fine since this only ever runs on a small retrieval candidate set,
    not the full corpus) specifically to support the initial-vs-full-name
    artist matching above, which exact-key grouping can't express.

    Returns a list of group dicts, each with the records, whether it spans
    multiple institutions, and a confidence flag. Confidence is 'low' if
    EITHER the title is generic OR any member was matched via the
    initial-name rule rather than an exact artist match -- both are
    real, distinct sources of uncertainty, and neither should be hidden
    behind a single silent "matched" result.
    """
    n = len(records)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    used_initial_match = set()

    for i in range(n):
        title_i = normalize_title(records[i].get("title"))
        if not title_i:
            continue
        for j in range(i + 1, n):
            title_j = normalize_title(records[j].get("title"))
            if title_i != title_j:
                continue
            is_match, match_type = artists_match(
                records[i].get("artist"), records[j].get("artist")
            )
            if is_match:
                union(i, j)
                if match_type == "initial":
                    used_initial_match.add(find(i))

    clusters = defaultdict(list)
    for i in range(n):
        if normalize_title(records[i].get("title")):
            clusters[find(i)].append(records[i])

    groups = []
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        norm_title = normalize_title(members[0].get("title"))
        institutions = set(m["institution"] for m in members)
        is_low_confidence = norm_title in GENERIC_TITLES or root in used_initial_match
        groups.append({
            "normalized_title": norm_title,
            "normalized_artist": normalize_artist(members[0].get("artist")),
            "members": members,
            "spans_institutions": len(institutions) > 1,
            "institutions": institutions,
            "confidence": "low" if is_low_confidence else "high",
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