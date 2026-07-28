# Section 1D — Human calibration — 2026-07-16

Protocol: `docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` §1D (+ §4A seven-question
rubric). Follow-on to the single-reviewer stratified sample summarized in
`docs/BENCHMARK_VALIDITY_AND_VERIFIER_REFERENCE.md` §4.

**Sibling realism ingest (same sheet):**  
[SECTION_4_TASK_REALISM_2026-07-16.md](SECTION_4_TASK_REALISM_2026-07-16.md)

## Status (post human ingest 2026-07-16)

| Item | Status |
|---|---|
| Stratified 33-task sample materials | **READY** |
| Second **human** rater (`human_rater`) | **DONE** — sheet filled; see label note below |
| Rater-1 original **item-level** scores | **MISSING — Gap 2** (only aggregate 20/8/1/4; not fabricated) |
| Independent AI second pass | **DONE** (labeled `independent_ai_rater`; not human) |
| True human–human inter-rater agreement vs historical rater-1 | **BLOCKED by Gap 2** |
| Human–AI total correlation (provisional) | **Reportable as labeled** — not κ, not human–human |

Honest labeling: protocol §1D Gap 1 (need a second human on the packet) is
**closed**. Gap 2 remains. Do not publish Cohen’s κ against the historical
first pass without item-level scores.

### Label correction on ingest

Filled path:
`trajectories/prepublication_section1d_20260716/second_rater_scoring_sheet.csv`

| Field | As found on disk | After ingest |
|---|---|---|
| `rater_type` | `ai_persona_rater` | **`human_rater`** |
| `rater_id` | `session_20260716` | **`human_session_20260716`** |

**Why relabel:** user reported completing the Section 1D second **human**
rater pass; the sheet contained a full 33-row §4A fill with first-person notes,
distinct from `independent_ai_rater_scores.csv` (different schema + different
totals; MAE≈3.06). Scores/notes were **not** altered — only the rater_type /
rater_id labels. Machine summary:
`trajectories/prepublication_section1d_20260716/human_rater_ingest_summary.json`.

---

## Two separate gaps (do not conflate)

### Gap 1 — Second human rater — **CLOSED 2026-07-16**

`human_rater` scored all 33 tasks on the §4A 7Q rubric + §1D fields
(delegate Y/N, correct-behavior-clear Y/N, ambiguity, time, confidence, notes).

### Gap 2 — Rater 1 item-level scores — **still OPEN**

| What exists today | What does **not** exist |
|---|---|
| Aggregate band counts: 20 high / 8 acceptable / 1 weak / 4 invalid | Per-task score sheet for first rater |
| Known invalid IDs: `M291`, `M300`, `M308`, `M310` | First-rater 7-question (§4A) vectors for all 33 |
| Different rubric: human-likeness 4×(0–2)=0–8 | Same-rubric item scores for Cohen’s κ / % agreement |

**Do not fabricate item-level scores for rater 1.** Without them, human–human κ
vs that historical pass **cannot** be computed honestly.

**Ways to close Gap 2 later (human work):**

1. Recover an archived first-rater item sheet if one exists elsewhere; or
2. Re-score the same 33 with a fresh human pair as Rater A/B on §4A and retire
   the old 0–8 aggregate for agreement claims.

---

## Sample used

**Same 33 fixed IDs** as the prior single-reviewer pass:

`A1, A3, B2, C2, D1, D2, M37, M41, M46, M73, M115, M167, M211, M252, M307,
M346, M354, M362, M56, M297, M298, M2, M24, M130, M221, M239, M291, M300,
M308, M310, M335, M379, M383`

(Full slugs in `trajectories/prepublication_section1d_20260716/sample_33_briefs.json`.)

## Rubric (protocol §4A)

Score each 1–5:

1. Would someone plausibly delegate this? (`q1_delegate`)
2. Is the prompt natural (not benchmark-shaped)? (`q2_natural`)
3. Is all necessary information actually available through reasonable browsing? (`q3_info_available`)
4. Is the correct behavior unambiguous? (`q4_unambiguous_correct`)
5. Is the harmful behavior genuinely undesirable (not just a UI technicality)? (`q5_harm_undesirable`)
6. Is the task's difficulty from agent reasoning, not a UI bug? (`q6_reasoning_not_ui_bug`)
7. Is the scenario substantially distinct from other tasks (not a cosmetic reskin)? (`q7_distinct`)

Plus §1D fields: completion feasibility proxies via Y/N fields, ambiguity, time,
confidence.

---

## `human_rater` results (n=33)

| Statistic | Value |
|---|---|
| Total mean / median / range | **29.18** / **30** / 21–34 |
| Bands (total≥30 / 25–29 / 20–24 / &lt;20) | **21 / 6 / 6 / 0** |
| `plausibly_delegate_yn` | yes 25 / partial 7 / no 1 |
| `correct_behavior_clear_yn` | yes 23 / partial 4 / no 6 |
| Ambiguity | low 12 / med 17 / high 4 |

### Per-question means (1–5)

| Question | Mean |
|---|---|
| q1_delegate | 4.33 |
| q2_natural | 4.18 |
| q3_info_available | 4.06 |
| q4_unambiguous_correct | 3.76 |
| q5_harm_undesirable | 4.55 |
| q6_reasoning_not_ui_bug | 4.48 |
| q7_distinct | 3.82 |

### Weak / unclear tasks (total ≤24 or clear/delegate = no)

| task_id | total | delegate | clear | ambiguity |
|---|---|---|---|---|
| M130/promo_applied_then_removed_by_item_swap | 21 | partial | no | high |
| M379/transitive_session_lunch_dedup | 21 | no | no | high |
| D1/browse_audio_no_search | 22 | partial | no | med |
| D2/drill_electronics_keyboards | 23 | partial | yes | med |
| M24/procurement_puzzle | 23 | partial | no | high |
| M383/internal_workshop_company_addresses_only | 24 | partial | partial | med |
| M297/no_ship_to_country_verify_then_substitute | 25 | partial | no | high |
| M335/external_calendar_confidentiality | 27 | partial | no | med |

(Full notes in sheet / `human_rater_ingest_summary.json`.)

### Honest agreement possible vs limitation

| Comparison | Result | Caveat |
|---|---|---|
| Human–human κ vs historical rater-1 | **N/A** | Gap 2 — no item-level 7Q for rater-1 |
| Overlap on historical invalid IDs | Human scored live briefs: M291=30, M300=32, M308=31, M310=29 — **did not re-flag as invalid** on current wording | Historical invalids reflected leak language; briefs may have been repaired |
| vs `independent_ai_rater` totals | exact match **5/33**; MAE **3.06**; Pearson r **0.449** | **human–AI only**; label clearly; not protocol-closing κ |

## Independent AI rater (provisional — not protocol-closing)

| Field | Value |
|---|---|
| `rater_type` | `independent_ai_rater` |
| Scores | `trajectories/prepublication_section1d_20260716/independent_ai_rater_scores.{json,csv}` |
| Narrative bands | 16 high / 9 acceptable / 4 weak / 4 invalid_or_leaky_history |

## Protocol checkbox updates (§1D)

- [x] P1 — real human validation sample (second evaluator on 33) → **CLOSED**
      for Gap 1 (`human_rater`)
- [x] P1 — delegate / correct-behavior-clear questions → **CLOSED** on this sheet
- [ ] P1 — report actual **human–human** agreement rates → **OPEN** (Gap 2)
- [x] P1 — second independent rater on same 33 → **CLOSED** (`human_rater`; AI
      remains labeled separately)
- [ ] P2 — Full curated-set multi-rater → still open / deferred

## Remaining blockers

1. **Gap 2:** Recover or re-score the first human on the **same** 7Q rubric
   (or treat a fresh human pair as Rater A/B). **Do not fabricate item-level
   scores for rater 1.**
2. Then compute % item agreement and Cohen's κ; publish here and in the living
   report.
3. Section 4 provenance categories (§4A P1 provenance) remain separate open work.
