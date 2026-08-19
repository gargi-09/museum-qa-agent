"""
memory.py -- Lightweight CORRECTION PERSISTENCE.

Lets a human correct a specific field on a specific record, and have
that correction stick across future runs -- rather than the system
starting fresh with no memory of prior fixes every time it's re-run.
This is the simplest honest implementation of that concept, scoped appropriately for an
8-hour take-home: when a human corrects a specific field on a specific
record, that correction is persisted to disk and applied on every
subsequent run -- cleanly and VISIBLY (never silently) overriding what
the raw corpus says for that field, going forward.

DELIBERATELY NOT ATTEMPTED, and why: semantic/lab-level belief maps,
confidence-weighted corrections, divergent personal-vs-lab beliefs,
working-context sliding windows -- these are real, more sophisticated
extensions of the same underlying idea, but building them properly is a
genuinely larger project than an optional add-on to an 8-hour take-home
allows. This module solves exactly one narrow, real problem: "a
correction should stick," nothing more, stated explicitly rather than
silently expanded or silently skipped.

Storage: a single JSON file, corrections.json, at the project root.
Chosen over a database specifically because persistence-across-runs is
the only property that matters here -- a database would add real
complexity for zero additional capability at this scale.
"""
import json
import os
from datetime import datetime, timezone

CORRECTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "corrections.json"
)
CORRECTIONS_FILE = os.path.normpath(CORRECTIONS_FILE)


def load_corrections():
    """Loads the persisted corrections store. Returns {} if the file
    doesn't exist yet -- a store with zero corrections is the normal
    starting state, not an error condition.
    """
    if not os.path.exists(CORRECTIONS_FILE):
        return {}
    try:
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[memory] Warning: corrections file exists but could not be read "
              f"({e}) -- treating as empty rather than crashing.")
        return {}


def save_corrections(corrections):
    os.makedirs(os.path.dirname(CORRECTIONS_FILE), exist_ok=True)
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, indent=2, ensure_ascii=False)


def add_correction(record_id, field, corrected_value, note=""):
    """Records a correction for one field on one record. PERSISTS
    IMMEDIATELY to disk -- this is what makes it survive across separate
    script invocations, not just within one running process, which is
    the actual substance of "state persistence" here.

    VALIDATION, added after considering what happens if someone gives
    INCORRECT information (a real risk: this mechanism has no way to
    verify a correction is TRUE -- there's no ground truth available,
    the same fundamental limitation as the rest of this assignment).
    What CAN be checked deterministically: for 'year_raw' specifically,
    reject a correction that doesn't contain any extractable year at
    all (garbage input like "notavalidyear"), since that would silently
    corrupt both year_raw AND the derived years list going forward.
    This does NOT verify the correction is factually correct -- only
    that it's a plausible, well-formed value, which is a meaningfully
    smaller and more honest claim.
    """
    if field == "year_raw":
        from ingest import normalize_year
        if not normalize_year(corrected_value):
            print(f"[memory] REJECTED: {corrected_value!r} does not contain any "
                  f"extractable year -- correction not saved. If this is genuinely "
                  f"correct, check the value and try again.")
            return False

    corrections = load_corrections()
    corrections.setdefault(record_id, {})[field] = {
        "corrected_value": corrected_value,
        "note": note,
        "corrected_at": datetime.now(timezone.utc).isoformat(),
    }
    save_corrections(corrections)
    print(f"[memory] Correction saved: {record_id}.{field} -> {corrected_value!r}")
    return True


def remove_correction(record_id, field=None):
    """Undoes a correction -- addresses the real risk that a correction
    itself turns out to be wrong. If field is None, removes ALL
    corrections for that record; otherwise removes just the one field.
    Returns True if something was actually removed, False if there was
    nothing to remove (not an error -- just nothing to do).
    """
    corrections = load_corrections()
    if record_id not in corrections:
        print(f"[memory] No corrections found for {record_id} -- nothing to remove.")
        return False

    if field is None:
        del corrections[record_id]
        save_corrections(corrections)
        print(f"[memory] Removed ALL corrections for {record_id}.")
        return True

    if field in corrections[record_id]:
        del corrections[record_id][field]
        if not corrections[record_id]:
            del corrections[record_id]
        save_corrections(corrections)
        print(f"[memory] Removed correction: {record_id}.{field}")
        return True

    print(f"[memory] No correction found for {record_id}.{field} -- nothing to remove.")
    return False


def list_corrections():
    """Returns every active correction currently stored, for auditing --
    a human should always be able to see everything that's been
    overridden, not just trust it's fine. Prints a readable summary and
    also returns the raw data for programmatic use.
    """
    corrections = load_corrections()
    if not corrections:
        print("[memory] No corrections currently stored.")
        return corrections

    print(f"[memory] {sum(len(f) for f in corrections.values())} active correction(s) "
          f"across {len(corrections)} record(s):\n")
    for record_id, fields in corrections.items():
        for field, entry in fields.items():
            print(f"  {record_id}.{field} -> {entry['corrected_value']!r}")
            print(f"    note: {entry.get('note') or '(none)'}")
            print(f"    corrected at: {entry['corrected_at']}")
    return corrections


def get_correction(record_id, field, corrections=None):
    """Returns the corrected value for a field if one exists, else None."""
    if corrections is None:
        corrections = load_corrections()
    entry = corrections.get(record_id, {}).get(field)
    return entry["corrected_value"] if entry else None


def apply_corrections_to_record(record, corrections=None):
    """Returns a COPY of the record with any stored corrections applied.
    Every applied correction is recorded in a new '_correction_notes'
    list on the returned copy, so it is always visible and checkable
    that a value came from a human correction rather than the raw
    corpus -- never a silent overwrite.

    SPECIAL CASE, found by testing this end-to-end rather than assuming
    it was complete: 'years' is a DERIVED field (computed from
    'year_raw' via ingest.py's normalize_year()), not an independent one.
    Correcting 'year_raw' without also recomputing 'years' would leave a
    stale, inconsistent value behind -- and reasoning.py's
    check_factual_match verification check reads 'years', not 'year_raw',
    so an uncorrected 'years' list would silently undermine the very
    correction being applied. Fixed here: if 'year_raw' is corrected,
    'years' is recomputed from the NEW value using the same function
    ingest.py already uses, keeping the two fields consistent.
    """
    if corrections is None:
        corrections = load_corrections()
    record_corrections = corrections.get(record.get("id"), {})
    if not record_corrections:
        return record

    corrected = dict(record)
    notes = []
    for field, entry in record_corrections.items():
        original_value = record.get(field)
        corrected[field] = entry["corrected_value"]
        notes.append(
            f"{field}: corrected from {original_value!r} to "
            f"{entry['corrected_value']!r} (human correction, "
            f"{entry['corrected_at']}, note: {entry.get('note') or 'none'})"
        )

    if "year_raw" in record_corrections:
        from ingest import normalize_year
        corrected["years"] = normalize_year(corrected["year_raw"])

    corrected["_correction_notes"] = notes
    return corrected


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python memory.py add <record_id> <field> <corrected_value> [note]')
        print('  python memory.py remove <record_id> [field]')
        print('  python memory.py list')
        sys.exit(0)

    action = sys.argv[1]

    if action == "list":
        list_corrections()
    elif action == "remove":
        if len(sys.argv) < 3:
            print("Usage: python memory.py remove <record_id> [field]")
            sys.exit(0)
        record_id = sys.argv[2]
        field = sys.argv[3] if len(sys.argv) > 3 else None
        remove_correction(record_id, field)
    elif action == "add":
        if len(sys.argv) < 5:
            print("Usage: python memory.py add <record_id> <field> <corrected_value> [note]")
            sys.exit(0)
        record_id, field, corrected_value = sys.argv[2], sys.argv[3], sys.argv[4]
        note = sys.argv[5] if len(sys.argv) > 5 else ""
        add_correction(record_id, field, corrected_value, note)
    else:
        print(f"Unknown action: {action!r}. Use 'add', 'remove', or 'list'.")