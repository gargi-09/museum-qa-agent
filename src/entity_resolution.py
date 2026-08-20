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

VALIDATED AGAINST REAL DATA (not assumed): tested against the full corpus
and found 461 cross-institution candidate groups (610 groups total, of which
149 are same-institution). Spot-checked two by hand (Witkiewicz's "Arthur
Rubinstein, Zakopane"; Man Ray's "Return to Reason") -- both confirmed
genuine matches via independent evidence (matching dimensions after unit
conversion, near-identical descriptive content) -- not just coincidental
title reuse.

ALL NUMBERS IN THIS DOCSTRING WERE RECOMPUTED FROM SCRATCH against the
current data/normalized.jsonl and diffed against what was written here. Four
were stale and are corrected above and below; the correct-as-written ones are
listed at the end so the audit is reproducible rather than just asserted.
The cross-institution count was the largest drift -- 405 -> 461 -- and the
cause is visible in this docstring's own structure: 405 was measured BEFORE
the initial-vs-full-name matching rule described below was added. That rule
unifies more records, which creates more groups, and the earlier figure was
never revisited. A number measured before a change to the thing it measures
is not evidence about the current system.

SYSTEMATIC ARTIST-NAME AUDIT, run after test_pipeline.py revealed a real
missed duplicate ("Louise Bourgeois" vs "L. Bourgeois") during integration
testing -- rather than fix that one case and move on, ran a full-corpus,
non-reactive scan for the same TWO underlying patterns:
  1. Initial vs. full first name (e.g. "L. Bourgeois" / "Louise
     Bourgeois"): found 73 distinct pairs across the whole corpus, not
     just the 1 found by accident. (Recount method, so this is
     reproducible: take the set of DISTINCT artist strings, bucket them by
     normalized surname, and count within-bucket pairs for which
     artists_match() returns 'initial'. The previous figure of 64 may have
     been a different counting method rather than drift -- stating the
     method so the next recount is comparable.) Handled via artists_match()'s
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
free -- 274 of 461 cross-institution groups (59%) show zero year overlap
between institutions, a genuine, numeric, no-keyword-search-required
contradiction signal. Across ALL 610 groups (not just cross-institution),
312 show a year contradiction. Far larger and more systematic than the 18
records found via the earlier keyword-based scan ("at odds with",
"discrepancy").

AUDIT TRAIL -- every number above, recomputed fresh and diffed:
    CORRECTED (was stale):
      cross-institution groups              405 -> 461
      initial-vs-full-name pairs             64 -> 73   (method now stated)
      cross-inst groups, zero year overlap  244 -> 274
      that as a percentage                   60% -> 59%
    CONFIRMED STILL CORRECT:
      institution vs id-prefix mismatches     0   (checked all 5,000 records)
      diacritic-only ARTIST variant pairs     8
      diacritic-only TITLE variant pairs      0
      keyword-scan records ("at odds with"
        / "discrepancy")                     18   (the "~" is now unnecessary)
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
    multiple institutions, and BOTH a coarse 'confidence' flag and an itemised
    'low_confidence_reasons' list. The reasons matter because the two sources
    of uncertainty are not interchangeable and one of them was being reported
    as the other:

      'generic_title'      -- the title is in GENERIC_TITLES, so these may be
                              genuinely DISTINCT works that merely share a name.
      'initial_name_match' -- at least one member was folded via artists_match()'s
                              initial-vs-full-name rule rather than an exact
                              artist match.

    REAL BUG THIS FIXES, observed in the dev demo output. Previously there was
    only a single boolean, and summarize_group_for_prompt() rendered every
    low-confidence group with the generic-title wording. The Bourgeois group is
    low-confidence for the OTHER reason -- 'L. Bourgeois' vs 'Louise Bourgeois'
    -- and 'Ode to My Mother' is not a generic title, so the prompt asserted
    something false and the model repeated it verbatim to the user:
    "Both records note this is a generic title and these may be distinct works."
    A fabrication the pipeline itself authored is worse than one the model
    invents, because the model was being faithful to what it was told.

    ROBUSTNESS CHANGE, deliberately NOT described as a bug fix, because it was
    checked and it was not one. The flag used to be stored as
    `used_initial_match.add(find(i))` -- a union-find ROOT captured at match
    time -- which looks stale-able, since union() re-parents (`parent[ri] = rj`)
    and a later merge moves the root. It is not reachable in practice: the
    abbreviated-name record is compared against EVERY other same-title record,
    the add runs after each of those unions, so the flag is re-added under the
    current root every time; and any later exact-match union inside an
    already-merged cluster is a no-op that cannot re-root it. Brute-forced over
    5,586 synthetic configurations (2-4 records, 7 artist-name variants, 2
    titles): ZERO divergence in the low/high verdict between the old root-based
    version and the index-based one below.

    Kept anyway because recording member INDICES is correct BY CONSTRUCTION
    rather than by the argument above -- an index identifies a record
    permanently, a root is a transient property of the forest -- so it stays
    correct if the pairing loop or the union order is ever changed. That is a
    cheaper thing to maintain than a subtle invariant about iteration order.
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

    # Record INDICES, not roots -- see the docstring. An index identifies a
    # record permanently; a root is a transient property of the forest.
    initial_match_members = set()

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
                    initial_match_members.add(i)
                    initial_match_members.add(j)

    clusters = defaultdict(list)
    for i in range(n):
        if normalize_title(records[i].get("title")):
            clusters[find(i)].append(i)

    groups = []
    for member_idxs in clusters.values():
        if len(member_idxs) < 2:
            continue
        members = [records[i] for i in member_idxs]
        norm_title = normalize_title(members[0].get("title"))
        institutions = set(m["institution"] for m in members)

        low_confidence_reasons = []
        if norm_title in GENERIC_TITLES:
            low_confidence_reasons.append("generic_title")
        if any(i in initial_match_members for i in member_idxs):
            low_confidence_reasons.append("initial_name_match")

        groups.append({
            "normalized_title": norm_title,
            "normalized_artist": normalize_artist(members[0].get("artist")),
            "members": members,
            "spans_institutions": len(institutions) > 1,
            "institutions": institutions,
            "low_confidence_reasons": low_confidence_reasons,
            # Retained so existing readers (test_pipeline.py, main() below)
            # keep working -- this is now derived from the reasons above.
            "confidence": "low" if low_confidence_reasons else "high",
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

    # One note per REASON. Emitting the generic-title wording for every
    # low-confidence group put a false statement in the prompt, which the model
    # then repeated to the user -- see build_entity_groups()'s docstring.
    # Falls back to the old behaviour only for a group dict built before
    # low_confidence_reasons existed, so an external caller cannot crash here.
    reasons = group.get("low_confidence_reasons")
    if reasons is None:
        reasons = ["generic_title"] if group.get("confidence") == "low" else []

    if "generic_title" in reasons:
        note_parts.append("NOTE: generic title -- these may be DISTINCT works, not confirmed duplicates.")
    if "initial_name_match" in reasons:
        note_parts.append("NOTE: these were folded on an initial-vs-full-name artist "
                          "match (e.g. 'L. Bourgeois' / 'Louise Bourgeois'), not an exact "
                          "name match. Probably the same person, but a shared surname and "
                          "initial could in principle belong to two different people.")

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

    # Broken out by REASON. The old single line said "(generic title)" for every
    # low-confidence group, which mislabelled every initial-name fold.
    low_conf = [g for g in groups if g["confidence"] == "low"]
    generic = [g for g in groups if "generic_title" in g["low_confidence_reasons"]]
    initial = [g for g in groups if "initial_name_match" in g["low_confidence_reasons"]]
    both = [g for g in groups if len(g["low_confidence_reasons"]) > 1]
    print(f"  Low-confidence (any reason): {len(low_conf)}")
    print(f"    generic title:              {len(generic)}")
    print(f"    initial-vs-full-name fold:  {len(initial)}")
    print(f"    both reasons:               {len(both)}")

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