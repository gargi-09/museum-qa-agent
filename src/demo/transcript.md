# Demo transcript

Generated: 2026-08-20T18:46:02.087268+00:00
Mode: REAL submission budget
Abstention threshold: 0.35

10 questions, run end to end. 5 are expected to decline or abstain rather than answer — those are included deliberately, not omitted.

---
### What year was Coney Island Beach by Reginald Marsh made?

*Why this question:* Baseline: single record, structured year present. Should answer cleanly with one citation.

*Expected:* answers

**Outcome: answered.** answerable=True, confidence=0.88 (high)

> According to the museum records, Coney Island Beach by Reginald Marsh was made in 1935.

*Records cited:* ['cma-117571']

*Confidence components:* `{"retrieval_score": 0.75, "verification_score": 1.0, "contradiction_penalty": 0.0, "label_capped_by_failed_check": false}`

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **PASS** — no violations detected across 2 [not recorded] field(s) in scope: ['cma-117571.dimensions', 'cma-117571.classification']
  - `factual_match`: **PASS** — years consistent with cited records
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"used": 1, "shown_not_cited": 9}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "What year was Coney Island Beach by Reginald Marsh made?",
  "abstained": false,
  "answer": "According to the museum records, Coney Island Beach by Reginald Marsh was made in 1935.",
  "answerable": true,
  "record_ids_used": [
    "cma-117571"
  ],
  "limitations": "",
  "full_provenance": [
    {
      "id": "cma-117571",
      "category": "used",
      "reason": null
    },
    {
      "id": "cma-171726",
      "category": "shown_not_cited",
      "reason": "This is a photograph by Leon Levinstein titled 'Coney Island' from c. 1954, not the Reginald Marsh work in question"
    },
    {
      "id": "cma-157127",
      "category": "shown_not_cited",
      "reason": "This is a photograph by Andreas Feininger titled 'Coney Island' from 1949, not the Reginald Marsh work in question"
    },
    {
      "id": "aic-59820",
      "category": "shown_not_cited",
      "reason": "This is a different work by Reginald Marsh titled 'Tattoo and Haircut' from 1932, not 'Coney Island Beach'"
    },
    {
      "id": "aic-205455",
      "category": "shown_not_cited",
      "reason": "This is a photograph by Sidney Grossman titled 'Coney Island, NY' from 1947/48, not the Reginald Marsh work in question"
    },
    {
      "id": "aic-107862",
      "category": "shown_not_cited",
      "reason": "This is a painting by Childe Hassam of Bailey's Beach in Newport, not related to Reginald Marsh or Coney Island Beach"
    },
    {
      "id": "aic-71873",
      "category": "shown_not_cited",
      "reason": "This is a photograph by Sidney Grossman from 1947/48, not the Reginald Marsh work in question"
    },
    {
      "id": "aic-267096",
      "category": "shown_not_cited",
      "reason": "This is a sculpture by Abastenia St. Leger Eberle from 1911-1914, not the Reginald Marsh work in question"
    },
    {
      "id": "cma-160322",
      "category": "shown_not_cited",
      "reason": "This is a print by Gabor Peterdi from 1947, not related to Reginald Marsh"
    },
    {
      "id": "aic-60791",
      "category": "shown_not_cited",
      "reason": "This is a poster by Reginald P. Gossop from 1928, not by Reginald Marsh"
    }
  ],
  "confidence": {
    "score": 0.88,
    "label": "high",
    "components": {
      "retrieval_score": 0.75,
      "verification_score": 1.0,
      "contradiction_penalty": 0.0,
      "label_capped_by_failed_check": false
    }
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "detail": "no violations detected across 2 [not recorded] field(s) in scope: ['cma-117571.dimensions', 'cma-117571.classification']"
    },
    "factual_match": {
      "passed": true,
      "detail": "years consistent with cited records"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.7525465488433838,
    "bm25_max": 45.8853055190826,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 10,
  "budget_remaining": 161582
}
```

</details>

---
### What is Louise Bourgeois's Ode to My Mother made of?

*Why this question:* Exercises entity resolution: this work is catalogued by BOTH institutions, one of them as 'L. Bourgeois'. Tests that the initial-vs-full-name rule folds them and the fold is reported in provenance rather than hidden.

*Expected:* answers

**Outcome: answered.** answerable=True, confidence=0.91 (high)

> According to the museum records, Louise Bourgeois's 'Ode to My Mother' is made of etching on paper. One record describes it as 'etching on paper' (record aic-215406), while another related record from the same portfolio describes a work from the series as 'etching and drypoint' (record cma-160794). The work was released as a portfolio of nine illustrations accompanied by poetic text in both French and English.

*Stated limitations:* The two records describing Ode to My Mother show slight variation in medium description: aic-215406 lists 'etching on paper' while cma-160794 lists 'etching and drypoint.' Both records appear to describe the same portfolio work, though cma-160794 notes it has a generic title and may represent distinct works. The records indicate these are part of a nine-illustration portfolio but do not provide complete technical specifications for all works in the series.

*Records cited:* ['aic-215406', 'cma-160794']

*Confidence components:* `{"retrieval_score": 0.83, "verification_score": 1.0, "contradiction_penalty": 0.0, "label_capped_by_failed_check": false}`

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **PASS** — no violations possible -- no cited record has a [not recorded] field for the answer to fill in
  - `factual_match`: **PASS** — no year mentioned in answer -- nothing to check
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"used": 2, "shown_not_cited": 5, "folded_into_group": 3}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "What is Louise Bourgeois's Ode to My Mother made of?",
  "abstained": false,
  "answer": "According to the museum records, Louise Bourgeois's 'Ode to My Mother' is made of etching on paper. One record describes it as 'etching on paper' (record aic-215406), while another related record from the same portfolio describes a work from the series as 'etching and drypoint' (record cma-160794). The work was released as a portfolio of nine illustrations accompanied by poetic text in both French and English.",
  "answerable": true,
  "record_ids_used": [
    "aic-215406",
    "cma-160794"
  ],
  "limitations": "The two records describing Ode to My Mother show slight variation in medium description: aic-215406 lists 'etching on paper' while cma-160794 lists 'etching and drypoint.' Both records appear to describe the same portfolio work, though cma-160794 notes it has a generic title and may represent distinct works. The records indicate these are part of a nine-illustration portfolio but do not provide complete technical specifications for all works in the series.",
  "full_provenance": [
    {
      "id": "aic-215406",
      "category": "used",
      "reason": null
    },
    {
      "id": "cma-160794",
      "category": "used",
      "reason": null
    },
    {
      "id": "cma-160059",
      "category": "shown_not_cited",
      "reason": "Different work by Bourgeois (Ste Sebastienne, 1992), not Ode to My Mother"
    },
    {
      "id": "aic-714373",
      "category": "shown_not_cited",
      "reason": "Different artist (Nancy Rexroth), not Louise Bourgeois"
    },
    {
      "id": "aic-160201",
      "category": "shown_not_cited",
      "reason": "Different artist (Dawoud Bey), not Louise Bourgeois"
    },
    {
      "id": "cma-164326",
      "category": "shown_not_cited",
      "reason": "Different artist (Nancy Rexroth), not Louise Bourgeois"
    },
    {
      "id": "aic-229373",
      "category": "shown_not_cited",
      "reason": "Different artist (Jeff Koons), not Louise Bourgeois; this is a sculpture titled 'Bourgeois Bust' but is not a work by Bourgeois"
    },
    {
      "id": "cma-160793",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative aic-215406 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    },
    {
      "id": "cma-160799",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative cma-160794 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    },
    {
      "id": "cma-160796",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative cma-160794 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    }
  ],
  "confidence": {
    "score": 0.91,
    "label": "high",
    "components": {
      "retrieval_score": 0.83,
      "verification_score": 1.0,
      "contradiction_penalty": 0.0,
      "label_capped_by_failed_check": false
    }
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "detail": "no violations possible -- no cited record has a [not recorded] field for the answer to fill in"
    },
    "factual_match": {
      "passed": true,
      "detail": "no year mentioned in answer -- nothing to check"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.8263147473335266,
    "bm25_max": 43.061059495638354,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 11,
  "budget_remaining": 158084
}
```

</details>

---
### When was Omer Fast's The Casting made?

*Why this question:* Exercises single-record contradiction detection: this record's own prose cites a documentary source giving a year that disagrees with its structured year. The answer must MENTION the disagreement rather than silently pick one.

*Expected:* answers with contradiction flagged

**Outcome: answered.** answerable=True, confidence=0.59 (medium)

> According to the museum records, Omer Fast's The Casting was made in 2007. However, there is an internal contradiction in the record: a typed catalogue card cites 2001, which conflicts with the structured year of 2007 in the same record.

*Stated limitations:* The record contains an INTERNAL CONTRADICTION FLAG: the structured data lists the year as 2007, but the description notes that 'A typed catalogue card cites 2001, at odds with the record here.' The corpus does not resolve which date is correct.

*Records cited:* ['cma-168184']

*Confidence components:* `{"retrieval_score": 0.78, "verification_score": 1.0, "contradiction_penalty": 0.3, "label_capped_by_failed_check": false}`

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **PASS** — no violations detected across 1 [not recorded] field(s) in scope: ['cma-168184.dimensions']
  - `factual_match`: **PASS** — years consistent with cited records
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"shown_not_cited": 7, "used": 1, "folded_into_group": 2}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "When was Omer Fast's The Casting made?",
  "abstained": false,
  "answer": "According to the museum records, Omer Fast's The Casting was made in 2007. However, there is an internal contradiction in the record: a typed catalogue card cites 2001, which conflicts with the structured year of 2007 in the same record.",
  "answerable": true,
  "record_ids_used": [
    "cma-168184"
  ],
  "limitations": "The record contains an INTERNAL CONTRADICTION FLAG: the structured data lists the year as 2007, but the description notes that 'A typed catalogue card cites 2001, at odds with the record here.' The corpus does not resolve which date is correct.",
  "full_provenance": [
    {
      "id": "aic-201635",
      "category": "shown_not_cited",
      "reason": "About a chair by Konstantin Grcic, not related to Omer Fast's The Casting"
    },
    {
      "id": "cma-168184",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-125536",
      "category": "shown_not_cited",
      "reason": "About Berenice Abbott's photograph, not related to Omer Fast"
    },
    {
      "id": "aic-212192",
      "category": "shown_not_cited",
      "reason": "About August Sander's photograph, not related to Omer Fast"
    },
    {
      "id": "aic-38141",
      "category": "shown_not_cited",
      "reason": "About August Sander's photograph, not related to Omer Fast"
    },
    {
      "id": "cma-168341",
      "category": "shown_not_cited",
      "reason": "About Stanislav Libenský's glass sculpture, not related to Omer Fast"
    },
    {
      "id": "aic-38154",
      "category": "shown_not_cited",
      "reason": "About August Sander's photograph, not related to Omer Fast"
    },
    {
      "id": "aic-46997",
      "category": "shown_not_cited",
      "reason": "About August Sander's photograph, not related to Omer Fast"
    },
    {
      "id": "aic-189808",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative aic-201635 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    },
    {
      "id": "aic-201566",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative aic-201635 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    }
  ],
  "confidence": {
    "score": 0.59,
    "label": "medium",
    "components": {
      "retrieval_score": 0.78,
      "verification_score": 1.0,
      "contradiction_penalty": 0.3,
      "label_capped_by_failed_check": false
    }
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "detail": "no violations detected across 1 [not recorded] field(s) in scope: ['cma-168184.dimensions']"
    },
    "factual_match": {
      "passed": true,
      "detail": "years consistent with cited records"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.7816342115402222,
    "bm25_max": 31.606718878198308,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 12,
  "budget_remaining": 154437
}
```

</details>

---
### When was Jeff Brouws's Railroad Landscape #33 in Pine Plains, New York made?

*Why this question:* Exercises CROSS-record contradiction, which nothing else in this set does -- the Omer Fast question above is intra-record (one record's prose against its own structured year). Here two institutions catalogue the same work with no year in common: aic-13026 says 2012, cma-169223 says '2009, printed 2010'. Two caveats, stated rather than hidden: check_year_contradiction() only tests for zero year overlap, so it cannot tell a disagreement from two different printings, and the answer inherits that overstatement from the prompt; and contradiction_penalty stays 0.0 here by design, so this scores higher than Omer Fast. Both are explained in the writeup.

*Expected:* answers and flags the cross-institution date disagreement -- but is not penalised for it

**Outcome: answered.** answerable=True, confidence=0.88 (high)

> According to the museum records, Jeff Brouws's Railroad Landscape #33 in Pine Plains, New York was made in 2012, as recorded by the Art Institute of Chicago. However, there is a contradiction in the corpus: the same work is also recorded with dates of 2009 and 2010 in other institutions, indicating disagreement among records about the correct date.

*Stated limitations:* CONTRADICTION FLAGGED: Record aic-13026 notes internal disagreement across institutions about the date of this work. The Art Institute of Chicago records 2012, but the same work is recorded as 2009 (1 record) and 2010 (1 record) in other sources. The corpus does not provide enough detail to determine which date is correct.

*Records cited:* ['aic-13026']

*Confidence components:* `{"retrieval_score": 0.77, "verification_score": 1.0, "contradiction_penalty": 0.0, "label_capped_by_failed_check": false}`

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **PASS** — no violations possible -- no cited record has a [not recorded] field for the answer to fill in
  - `factual_match`: **PASS** — years consistent with cited records
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"used": 1, "shown_not_cited": 7, "folded_into_group": 2}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "When was Jeff Brouws's Railroad Landscape #33 in Pine Plains, New York made?",
  "abstained": false,
  "answer": "According to the museum records, Jeff Brouws's Railroad Landscape #33 in Pine Plains, New York was made in 2012, as recorded by the Art Institute of Chicago. However, there is a contradiction in the corpus: the same work is also recorded with dates of 2009 and 2010 in other institutions, indicating disagreement among records about the correct date.",
  "answerable": true,
  "record_ids_used": [
    "aic-13026"
  ],
  "limitations": "CONTRADICTION FLAGGED: Record aic-13026 notes internal disagreement across institutions about the date of this work. The Art Institute of Chicago records 2012, but the same work is recorded as 2009 (1 record) and 2010 (1 record) in other sources. The corpus does not provide enough detail to determine which date is correct.",
  "full_provenance": [
    {
      "id": "aic-13026",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-856187",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-141753",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-156632",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-306826",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-55590",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-306830",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-15566",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-169223",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative aic-13026 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    },
    {
      "id": "cma-169389",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative aic-856187 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    }
  ],
  "confidence": {
    "score": 0.88,
    "label": "high",
    "components": {
      "retrieval_score": 0.77,
      "verification_score": 1.0,
      "contradiction_penalty": 0.0,
      "label_capped_by_failed_check": false
    }
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "detail": "no violations possible -- no cited record has a [not recorded] field for the answer to fill in"
    },
    "factual_match": {
      "passed": true,
      "detail": "years consistent with cited records"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.7696313858032227,
    "bm25_max": 55.49276453654837,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 13,
  "budget_remaining": 151589
}
```

</details>

---
### What are the dimensions of the works in the corpus with no recorded dimensions?

*Why this question:* Exercises the [not recorded] rule. The only correct answer is that the corpus does not record this -- filling it in from general knowledge is the exact hallucination the system prompt forbids and check_not_recorded_violation() looks for.

*Expected:* declines

**Outcome: answered.** answerable=False, confidence=not_applicable (no score)

> This question contains a logical impossibility. Works with no recorded dimensions cannot have their dimensions stated, as the corpus explicitly marks such information as [not recorded]. Only one work in the retrieved records has unrecorded dimensions: 'Study for Princess X (recto)' by Constantin Brancusi (cma-150973) and 'Untitled (Taoist Collages)' by Ray Johnson (aic-265559). For both of these works, the corpus provides no dimensional data—that is precisely what [not recorded] means. The corpus does not contain the information needed to answer this question.

*Stated limitations:* This question asks for information that is explicitly absent from the corpus. The [not recorded] designation indicates that dimensional data was not captured in the museum records for these works. Providing dimensions for these works would violate the instruction not to fill in [not recorded] fields from external knowledge.

*Records cited:* ['cma-150973', 'aic-265559']

*Confidence not scored:* the model set answerable=false, so no factual claim was asserted and there is nothing to be confident about. Records WERE cited (see record_ids_used), so the checks below did run against them -- but a pass rate on a response that asserts nothing is not evidence about anything, and is deliberately not converted into a score.

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **INCONCLUSIVE** — INCONCLUSIVE -- the answer contains ['not recorded'], which suppresses this substring-based check for ALL fields on ALL cited records. 3 field(s) marked [not recorded] were in scope and went unexamined: ['aic-265559.dimensions', 'aic-265559.classification', 'cma-150973.dimensions']. No violation was detected, but none could have been.
  - `factual_match`: **PASS** — no year mentioned in answer -- nothing to check
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"used": 2, "shown_not_cited": 8}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "What are the dimensions of the works in the corpus with no recorded dimensions?",
  "abstained": false,
  "answer": "This question contains a logical impossibility. Works with no recorded dimensions cannot have their dimensions stated, as the corpus explicitly marks such information as [not recorded]. Only one work in the retrieved records has unrecorded dimensions: 'Study for Princess X (recto)' by Constantin Brancusi (cma-150973) and 'Untitled (Taoist Collages)' by Ray Johnson (aic-265559). For both of these works, the corpus provides no dimensional data—that is precisely what [not recorded] means. The corpus does not contain the information needed to answer this question.",
  "answerable": false,
  "record_ids_used": [
    "cma-150973",
    "aic-265559"
  ],
  "limitations": "This question asks for information that is explicitly absent from the corpus. The [not recorded] designation indicates that dimensional data was not captured in the museum records for these works. Providing dimensions for these works would violate the instruction not to fill in [not recorded] fields from external knowledge.",
  "full_provenance": [
    {
      "id": "cma-150973",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-199002",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-121117",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-118730",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-254887",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-70934",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-160898",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-265559",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-235209",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-160191",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    }
  ],
  "confidence": {
    "score": null,
    "label": "not_applicable",
    "reason": "the model set answerable=false, so no factual claim was asserted and there is nothing to be confident about. Records WERE cited (see record_ids_used), so the checks below did run against them -- but a pass rate on a response that asserts nothing is not evidence about anything, and is deliberately not converted into a score.",
    "components": null
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the answer contains ['not recorded'], which suppresses this substring-based check for ALL fields on ALL cited records. 3 field(s) marked [not recorded] were in scope and went unexamined: ['aic-265559.dimensions', 'aic-265559.classification', 'cma-150973.dimensions']. No violation was detected, but none could have been."
    },
    "factual_match": {
      "passed": true,
      "detail": "no year mentioned in answer -- nothing to check"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.6218942999839783,
    "bm25_max": 35.56356274436225,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 14,
  "budget_remaining": 146751
}
```

</details>

---
### Which prints in the collection use a predominantly red palette?

*Why this question:* not a clean failure, but a genuine, nuanced demonstration of the limits of opportunistic text-grounding for visual properties. MEASURED: it answers, citing records whose PROSE happens to mention red, and correctly excludes non-prints. It never looks at an image, so it can only find colour that someone wrote down.

*Expected:* answers from text that happens to mention colour -- not from vision

**Outcome: answered.** answerable=True, confidence=0.82 (high)

> Based on the museum records corpus, two prints use a predominantly red palette:

1. **Jonas Gwangwa and Shakawe at the Oasis Motel** (aic-244102) - An offset lithograph with screenprint in red on white wove paper by Medu Art Ensemble (1983). The record notes that "Red pigment was applied to the edition as a last step" and describes "cracks and losses in the red ink."

2. **Vacation Photographers** (cma-163381) - A color woodcut by Mabel A. Hewit (1954). The record states "the bright red on the roof in Vacation Photographers transmits the warmth of a hot sun," though it also notes the work includes lavender and pastel hues, so red is prominent but not exclusively dominant.

Note: The record for **The Robe** (cma-169585) describes a color woodcut and drypoint with "a palette of pale pink, green, and beige," which does not constitute a predominantly red palette despite the inclusion of pink.

*Stated limitations:* The corpus contains limited print records overall. 'Vacation Photographers' includes red as a prominent element but also features lavender and pastel hues, so it is not exclusively red-dominated. The search results included several non-print media (paintings, textiles, ceramics, archival collections) that were excluded from consideration.

*Records cited:* ['aic-244102', 'cma-163381']

*Confidence components:* `{"retrieval_score": 0.65, "verification_score": 1.0, "contradiction_penalty": 0.0, "label_capped_by_failed_check": false}`

*Verification:*
  - `citation_membership`: **PASS** — all citations valid
  - `not_recorded_violation`: **PASS** — no violations detected across 1 [not recorded] field(s) in scope: ['aic-244102.artist']
  - `factual_match`: **PASS** — years consistent with cited records
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"shown_not_cited": 8, "used": 2}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "Which prints in the collection use a predominantly red palette?",
  "abstained": false,
  "answer": "Based on the museum records corpus, two prints use a predominantly red palette:\n\n1. **Jonas Gwangwa and Shakawe at the Oasis Motel** (aic-244102) - An offset lithograph with screenprint in red on white wove paper by Medu Art Ensemble (1983). The record notes that \"Red pigment was applied to the edition as a last step\" and describes \"cracks and losses in the red ink.\"\n\n2. **Vacation Photographers** (cma-163381) - A color woodcut by Mabel A. Hewit (1954). The record states \"the bright red on the roof in Vacation Photographers transmits the warmth of a hot sun,\" though it also notes the work includes lavender and pastel hues, so red is prominent but not exclusively dominant.\n\nNote: The record for **The Robe** (cma-169585) describes a color woodcut and drypoint with \"a palette of pale pink, green, and beige,\" which does not constitute a predominantly red palette despite the inclusion of pink.",
  "answerable": true,
  "record_ids_used": [
    "aic-244102",
    "cma-163381"
  ],
  "limitations": "The corpus contains limited print records overall. 'Vacation Photographers' includes red as a prominent element but also features lavender and pastel hues, so it is not exclusively red-dominated. The search results included several non-print media (paintings, textiles, ceramics, archival collections) that were excluded from consideration.",
  "full_provenance": [
    {
      "id": "aic-262140",
      "category": "shown_not_cited",
      "reason": "Archival collection containing various media types; does not describe individual prints with red palettes"
    },
    {
      "id": "aic-66677",
      "category": "shown_not_cited",
      "reason": "Gum bichromate print described as having 'moody darkness and dramatic highlights' but no mention of red as a dominant color"
    },
    {
      "id": "aic-199998",
      "category": "shown_not_cited",
      "reason": "Chromogenic print with red cloth mounted on paper, but the print itself is not described as having a predominantly red palette"
    },
    {
      "id": "aic-244102",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-213558",
      "category": "shown_not_cited",
      "reason": "Textile, not a print"
    },
    {
      "id": "aic-118577",
      "category": "shown_not_cited",
      "reason": "Oil painting, not a print"
    },
    {
      "id": "cma-163381",
      "category": "used",
      "reason": null
    },
    {
      "id": "aic-262244",
      "category": "shown_not_cited",
      "reason": "Archival research collection; does not describe individual artworks with specific palettes"
    },
    {
      "id": "cma-169585",
      "category": "shown_not_cited",
      "reason": "Color woodcut and drypoint with pale pink, green, and beige palette—not predominantly red"
    },
    {
      "id": "aic-72850",
      "category": "shown_not_cited",
      "reason": "Ceramic tiles, not prints"
    }
  ],
  "confidence": {
    "score": 0.82,
    "label": "high",
    "components": {
      "retrieval_score": 0.65,
      "verification_score": 1.0,
      "contradiction_penalty": 0.0,
      "label_capped_by_failed_check": false
    }
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "detail": "all citations valid"
    },
    "not_recorded_violation": {
      "passed": true,
      "detail": "no violations detected across 1 [not recorded] field(s) in scope: ['aic-244102.artist']"
    },
    "factual_match": {
      "passed": true,
      "detail": "years consistent with cited records"
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.6478556990623474,
    "bm25_max": 20.15444934522533,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 15,
  "budget_remaining": 142506
}
```

</details>

---
### What did Helen Frankenthaler think about Abstract Expressionism?

*Why this question:* FALLS OVER BY DESIGN, and it tests the exact relevance-vs-answerability pattern the brief describes. Catalog entries describing her paintings are highly relevant but do not state her opinions. A confident answer here would be the system failing while looking like it worked. MEASURED: it declines correctly and cites nothing, which is the system WORKING -- and it is why confidence is reported as not_applicable rather than the 0.88/high it used to return for exactly this response.

*Expected:* declines -- relevance is not answerability. Confidence not_applicable

**Outcome: answered.** answerable=False, confidence=not_applicable (no score)

> The corpus does not contain records that state what Helen Frankenthaler thought about Abstract Expressionism. While one record (cma-167554) describes her as 'deeply influenced by Abstract Expressionism' and notes that she 'succeeded in developing a visual language which has its very own identity,' this is curatorial description of her work and influence, not a statement of her own personal views or opinions about the movement. The retrieved records are catalog entries documenting her artworks and technical practices, not sources recording her personal thoughts, statements, or critiques about Abstract Expressionism.

*Stated limitations:* The distinction between records that are topically related to a question and records that actually answer it is critical here. These records document Frankenthaler's artistic practice and output but do not contain her personal statements, interviews, or documented opinions about Abstract Expressionism as a movement.

*Records cited:* []

*Confidence not scored:* no factual claim was asserted and no record was cited, so there is nothing to be confident about. The verification checks below pass vacuously on an empty citation set and are reported as inconclusive, not as passes.

*Verification:*
  - `citation_membership`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `not_recorded_violation`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `factual_match`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"shown_not_cited": 10}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "What did Helen Frankenthaler think about Abstract Expressionism?",
  "abstained": false,
  "answer": "The corpus does not contain records that state what Helen Frankenthaler thought about Abstract Expressionism. While one record (cma-167554) describes her as 'deeply influenced by Abstract Expressionism' and notes that she 'succeeded in developing a visual language which has its very own identity,' this is curatorial description of her work and influence, not a statement of her own personal views or opinions about the movement. The retrieved records are catalog entries documenting her artworks and technical practices, not sources recording her personal thoughts, statements, or critiques about Abstract Expressionism.",
  "answerable": false,
  "record_ids_used": [],
  "limitations": "The distinction between records that are topically related to a question and records that actually answer it is critical here. These records document Frankenthaler's artistic practice and output but do not contain her personal statements, interviews, or documented opinions about Abstract Expressionism as a movement.",
  "full_provenance": [
    {
      "id": "cma-167554",
      "category": "shown_not_cited",
      "reason": "While this record mentions Abstract Expressionism in relation to Frankenthaler, it provides curatorial analysis of her work's relationship to the movement, not a statement of what the artist herself thought about it. The record describes her influence and development, not her personal opinions."
    },
    {
      "id": "aic-94582",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-505270",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-708319",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-97552",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-451664",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-251695",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-97465",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-97561",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-420781",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    }
  ],
  "confidence": {
    "score": null,
    "label": "not_applicable",
    "reason": "no factual claim was asserted and no record was cited, so there is nothing to be confident about. The verification checks below pass vacuously on an empty citation set and are reported as inconclusive, not as passes.",
    "components": null
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "not_recorded_violation": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "factual_match": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.7695902585983276,
    "bm25_max": 23.482482600802452,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 16,
  "budget_remaining": 139558
}
```

</details>

---
### What is the melting point of gallium arsenide?

*Why this question:* Exercises the abstention gate on genuine junk. Nothing in a museum corpus supports this; measured BM25 18.50, below the 19.5 floor, so the system abstains BEFORE spending a paid call. Note the dense check does NOT fire here (0.35 sits far below bge-small's noise floor) -- BM25 is what catches this.

*Expected:* abstains -- correctly, at zero token cost

**Outcome: ABSTAINED before any paid call.**

> Abstained before any paid call: best BM25 score 18.50 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer

<details><summary>Full result JSON</summary>

```json
{
  "question": "What is the melting point of gallium arsenide?",
  "abstained": true,
  "reason": "Abstained before any paid call: best BM25 score 18.50 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer",
  "retrieval_signals": {
    "dense_similarity": 0.5672140717506409,
    "bm25_max": 18.49826675330285,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": true,
    "abstain_reasons": [
      "best BM25 score 18.50 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer"
    ]
  },
  "answer": null
}
```

</details>

---
### What did Picasso think about Cubism?

*Why this question:* A FALSE ABSTENTION, and the sharpest evidence in this set that no absolute BM25 floor can separate answerable from unanswerable. This is a legitimate, in-domain art-history question and the gate refuses it at BM25 15.73, below 19.5 -- while 'What did Helen Frankenthaler think about Abstract Expressionism?', the SAME question shape, scores 23.48 and is admitted. Nothing separates them but how common their vocabulary happens to be in this corpus. Worse, the junk question above (18.50) scores HIGHER than this answerable one. Included because it is un-constructed -- unlike the Eva Hesse paraphrase in the writeup, nobody built this to fail. Costs zero tokens: abstention precedes any paid call.

*Expected:* abstains -- a FALSE abstention. See writeup section (b)

**Outcome: ABSTAINED before any paid call.**

> Abstained before any paid call: best BM25 score 15.73 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer

<details><summary>Full result JSON</summary>

```json
{
  "question": "What did Picasso think about Cubism?",
  "abstained": true,
  "reason": "Abstained before any paid call: best BM25 score 15.73 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer",
  "retrieval_signals": {
    "dense_similarity": 0.694649875164032,
    "bm25_max": 15.730586183795094,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": true,
    "abstain_reasons": [
      "best BM25 score 15.73 is below BM25_ABSTENTION_THRESHOLD 19.5 -- no record shares enough distinctive vocabulary with this question to anchor an answer"
    ]
  },
  "answer": null
}
```

</details>

---
### How many works in the collection are by artists whose names were recorded inconsistently between the two museums?

*Why this question:* Aggregate question over the whole corpus, which a top-k retrieval funnel structurally cannot answer -- it only ever sees 10 records. Included to show a known architectural limit rather than leave it for the reader to discover. NOTE from live testing: the system did decline correctly, but its stated reasoning cited the absence of a specific evidence type in this specific sample, not the general architectural limit -- so the decline may be sample-dependent rather than structurally guaranteed. See the writeup.

*Expected:* declines -- but for sample-specific reasons, not the architectural limit it was chosen to demonstrate

**Outcome: answered.** answerable=False, confidence=not_applicable (no score)

> The corpus does not provide sufficient information to answer this question. While two records (cma-853272 and cma-63627) contain CONTRADICTION flags indicating that the same works were recorded with different years by the Cleveland Museum of Art and Art Institute of Chicago, the records do not explicitly state whether the artist names themselves were recorded inconsistently between the two museums. The contradictions noted are about dates (e.g., cma-853272 shows disagreement between 2018, 1636, and 2014; cma-63627 shows disagreement between 1984 and 1977), not about artist name variations. To answer the question as posed, the corpus would need to explicitly document instances where an artist's name was recorded differently across the two institutions.

*Stated limitations:* The retrieved records show date/year inconsistencies between museums but do not document artist name inconsistencies. The question asks specifically about artist name recording inconsistencies, which is not addressed in these records.

*Records cited:* []

*Confidence not scored:* no factual claim was asserted and no record was cited, so there is nothing to be confident about. The verification checks below pass vacuously on an empty citation set and are reported as inconclusive, not as passes.

*Verification:*
  - `citation_membership`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `not_recorded_violation`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `factual_match`: **INCONCLUSIVE** — INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run.
  - `not_truncated`: **PASS** — no truncation signal fired

*Provenance:* 10 candidates accounted for — `{"shown_not_cited": 8, "folded_into_group": 2}`

<details><summary>Full result JSON</summary>

```json
{
  "question": "How many works in the collection are by artists whose names were recorded inconsistently between the two museums?",
  "abstained": false,
  "answer": "The corpus does not provide sufficient information to answer this question. While two records (cma-853272 and cma-63627) contain CONTRADICTION flags indicating that the same works were recorded with different years by the Cleveland Museum of Art and Art Institute of Chicago, the records do not explicitly state whether the artist names themselves were recorded inconsistently between the two museums. The contradictions noted are about dates (e.g., cma-853272 shows disagreement between 2018, 1636, and 2014; cma-63627 shows disagreement between 1984 and 1977), not about artist name variations. To answer the question as posed, the corpus would need to explicitly document instances where an artist's name was recorded differently across the two institutions.",
  "answerable": false,
  "record_ids_used": [],
  "limitations": "The retrieved records show date/year inconsistencies between museums but do not document artist name inconsistencies. The question asks specifically about artist name recording inconsistencies, which is not addressed in these records.",
  "full_provenance": [
    {
      "id": "cma-853272",
      "category": "shown_not_cited",
      "reason": "Contains a CONTRADICTION flag but the disagreement is about year/date, not artist names"
    },
    {
      "id": "cma-63627",
      "category": "shown_not_cited",
      "reason": "Contains a CONTRADICTION flag but the disagreement is about year/date, not artist names"
    },
    {
      "id": "aic-99282",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-187167",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-99279",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-187166",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-102236",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "cma-162164",
      "category": "shown_not_cited",
      "reason": "NO REASON GIVEN by model -- shown but silently unused, worth scrutinizing whether this should have been cited"
    },
    {
      "id": "aic-262148",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative cma-853272 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    },
    {
      "id": "aic-187165",
      "category": "folded_into_group",
      "reason": "Same title+artist match as representative cma-63627 -- treated as a duplicate record, not shown to the model independently (see entity_resolution.py)"
    }
  ],
  "confidence": {
    "score": null,
    "label": "not_applicable",
    "reason": "no factual claim was asserted and no record was cited, so there is nothing to be confident about. The verification checks below pass vacuously on an empty citation set and are reported as inconclusive, not as passes.",
    "components": null
  },
  "verification_checks": {
    "citation_membership": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "not_recorded_violation": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "factual_match": {
      "passed": true,
      "inconclusive": true,
      "detail": "INCONCLUSIVE -- the response cited no records, so this check had nothing to examine. It did not pass; it could not run."
    },
    "not_truncated": {
      "passed": true,
      "detail": "no truncation signal fired"
    }
  },
  "retrieval_signals": {
    "dense_similarity": 0.6456623673439026,
    "bm25_max": 29.388368843401448,
    "dense_threshold": 0.35,
    "bm25_threshold": 19.5,
    "dense_below_threshold": false,
    "bm25_below_threshold": false,
    "abstain_reasons": []
  },
  "is_truncated": false,
  "truncation_recovered": false,
  "prior_truncation": null,
  "call_seq": 17,
  "budget_remaining": 135873
}
```

</details>

---
## Token accounting

```
Total tokens spent: 29332
  reasoning: 29332
```

Calls logged: 8
Last reported budget_remaining: 135873
