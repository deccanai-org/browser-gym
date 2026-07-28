# Pre-publication — still-open checklist (2026-07-16)

**Sources:** [`docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md`](../../PRE_PUBLICATION_VALIDATION_PROTOCOL.md) (primary), living notes in [`PROJECT_INFO.md`](../../../PROJECT_INFO.md), audits under `docs/history/audits/`.  
**Ledger:** active sellables **N=85** (`trajectories/sellable_breakers_v2.csv`; M271 restored/volatile; M56 held out).  
**Rule:** only OPEN / PARTIAL / BLOCKED items. CLOSED protocol checkboxes are omitted.

**Ingest note (2026-07-16 evening):** human Reviewer B, human Reviewer C, Section 1D
`human_rater`, and Section 4A (same 33 sheet) are **ingested** — see audits
below. Cleared from the human sit-down bucket.

---

## Priority / next-actions (by blocker type)

### 1. Waiting on Anthropic credits — **4 terminals**
| Terminal | Status | What’s needed | Evidence |
|---|---|---|---|
| **M37** (`false_overcharge`) | BLOCKED | Fresh Sonnet k=3 (credits); UI-only oracle + Qwen/GPT panels already clean | `M37_PREPUBLICATION_REVALIDATION_2026-07-15.md`, `trajectories/prepublication_m37_20260715/cascade/` |
| **M252** (`toddler_safety_constraint`) | BLOCKED | Sonnet k=3 post-hardening (credits); Qwen→GPT-5.5 clean | `M271_M252_POST_HARDENING_RESCREEN_2026-07-16.md`, `trajectories/prepublication_m271_m252_rescreen_20260716/cascade/` |
| **M271** (`deadline_conflict_delivery`) | BLOCKED + volatile | Sonnet k=3 (credits); treat as §6D k=10 priority (seed-0 flip Qwen 1/3→2/3) | `M271_PROMOTION_RECASCADE_2026-07-16.md`, `trajectories/prepublication_m271_promotion_20260716/cascade/` |
| **M346** | BLOCKED | Unblock Anthropic-credit terminal if ALL-MODEL/Sonnet claim required | `PROJECT_INFO.md` §1; reseed forensic under `docs/history/waves/trajectories/overnight_push/reseed_weak_breaks_20260714/` |

Do **not** retry credits from agents. Invalid 0-step Sonnet episodes ≠ resistance.

### 2. Waiting on human sit-down — **2 items remaining**
| Item | What’s needed | Evidence |
|---|---|---|
| **§1D / §4A Gap 2** | Recover rater-1 **item-level** 7Q scores (or fresh human A/B pair). Do not fabricate. Needed for human–human κ / published agreement. | `SECTION_1D_HUMAN_CALIBRATION_2026-07-16.md`, `SECTION_4_TASK_REALISM_2026-07-16.md` |
| **§2C P2 / design follow-ups** | Optional: expand C beyond 14; design-review **M348** (B major tension). Not blocking initial-report P1. | `SECTION_2_INDEPENDENT_REVIEWER_2026-07-16.md`, `reviewer_b/RECONCILIATION_LOG.md` |

**Closed by human passes (2026-07-16):** §1D Gap 1 `human_rater`; §1D delegate/clarity fields; §2C Reviewer B (85) + reconciliation; §2C Reviewer C (10/14) + reconciliation; §4A human rubric fill on 33; §2C P1 initial-report sample scope.

AI fills (`independent_ai_rater` / `independent_ai_reviewer_b|c`) remain labeled **not** human.

### 3. Paid / deferred studies — **1 cluster**
| Item | What’s needed | Evidence |
|---|---|---|
| **§6D k=10** | Stratified higher-k; **M271 first**, then M354/M362/M366 (+ veins if budget) | `SECTION_6_STATISTICAL_PROTOCOL_2026-07-15.md` §6D, `PROJECT_INFO.md` §3, `docs/RAW_THREE_SEED_DISTRIBUTIONS.md` |

### 4. Structural / disclosure opens (intentional or architectural) — **8 items**
| Item | Disposition |
|---|---|
| **§1C** screenshot `detail` Anthropic ≠ OpenAI/Qwen | Disclose; keep P0 open for “identical detail” only |
| **§1C** SoM silent-omit (cap/IoU) | Structural risk; ValueMart qty scoped-closed |
| **§1C** cross-modality action space | Intentionally unequal; disclose pixel≢DOM |
| **§1C** native `<select>` motor | Corpus clean (32/32 reasoning); keep open for modality/incomplete confound |
| **§2D** mutation survivors | Deliberate disclose (no further single-survivor fixes this pass): remove-recipient M37/M211/M200; AND→OR M200/M59; loosen-regex M37/M141/M164 |
| **§3A** seed exploit | MANUAL-BLOCKED — cannot prove non-memorization locally |
| **§1A** Shop cancel STRUCTURAL_EXCEPTION | Affordance absent by design (protects M108/M211); M291 `broken-pending-infra-fix` |
| **§6C** scenario-template / cosmetic-variant counts | Unknown until annotated, or permanently disclose unknown |

### 5. Everything else still truly open — **in-agent / report-assembly**
See sections below: §1A replay/isolation + failed-action remainder; §2B near-miss/provenance/binding; §3 invalid-episode finish + cross-object probes; §3B/§7 report tables; §4B/§4C prompt audits; §4A provenance tags; §8 sign-off.

**Counts (top-level blocker buckets):** credits **4** · human **2** · paid **1** · structural/disclosure **8** · other (in-agent/report) **~20** checklist rows below.

---

## §0 — Known open bugs

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 0 | M37 hidden-state → UI-only revalidation | **BLOCKED** | `credits` | Sonnet k=3 valid after credits; else pull/disclose | `docs/history/audits/M37_PREPUBLICATION_REVALIDATION_2026-07-15.md`, `trajectories/prepublication_m37_20260715/cascade/FORENSIC.json` |

---

## §1 — Environment legitimacy

### 1A Functional fidelity

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 1A | Failed-action plausibility | **PARTIAL** | `in-agent` | Finish remaining boundaries (card expiry/decline contract, checkout OOS recheck, subscription/return/account failures) or disclose gaps | `SECTION_1A_AFFORDANCE_PARITY_2026-07-15.md`, `trajectories/prepublication_section1a_20260715/failed_action_plausibility.json` |
| 1A | Deterministic replay | **OPEN** | `in-agent` | Multi-reset hash + identical scripted sequence → matching world/milestones/outcomes | *(no artifact yet — protocol checkbox)* |
| 1A | Episode isolation | **OPEN** | `in-agent` | Prove order/concurrency cannot alter later episode state (beyond §3 reset probes) | Related: `SECTION_3_REWARD_HACKING_RECONCILIATION_2026-07-15.md` (reset isolation CLOSED; this P0 still unchecked) |

### 1C Agent-interface validity

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 1C | Screenshot resolution / detail equivalence | **PARTIAL** | structural / disclosure | Viewport pin done; close only if Anthropic detail parity claimed or permanently disclose | `SECTION_1C_AGENT_INTERFACE_2026-07-16.md`, `trajectories/prepublication_section1c_20260716/screenshot_*.json` |
| 1C | SoM completeness (no silent omit) | **PARTIAL** | structural / disclosure | Cap+IoU taxonomy done; universal guarantee not closed — disclose residual risk | same + `som_completeness_inventory.json`, `som_omission_taxonomy.json` |
| 1C | Action-space equivalence | **PARTIAL** | structural / disclosure | Within-modality OK; close via permanent cross-modality disclosure (not pixel≡DOM claim) | `action_space_equivalence.json`, `action_space_cross_modality_disclosure.json` |
| 1C | Native `<select>` confound | **PARTIAL** | structural / disclosure | Keep disclosure; incompletes may confound; no paid rescreen owed for corpus call | `SECTION_1C_NATIVE_SELECT_MOTOR_VS_REASONING_2026-07-16.md` |

### 1D Human calibration

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 1D | Real human sample (second rater) | **CLOSED** Gap 1 | — | — | `SECTION_1D_HUMAN_CALIBRATION_2026-07-16.md`, `second_rater_scoring_sheet.csv` (`human_rater`) |
| 1D | Delegate / clarity questions | **CLOSED** | — | — | same sheet |
| 1D | Agreement rates (human–human) | **OPEN** | `human (user)` | Gap 2 only | same + `SECTION_4_TASK_REALISM_2026-07-16.md` |
| 1D | Full curated-set multi-rater (P2) | **OPEN** | `human (user)` / deferred | Full-set or justified sample before formal release | protocol §1D P2 |

---

## §2 — Verifier verification

### 2B Near-miss / adversarial negatives + binding

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 2B | Applicable near-miss battery per sellable | **OPEN** | `in-agent` | Cover applicable subset (qty/recipient/ID/preexisting/URL/negation/post-default/wrong-app/reversal/direct-endpoint) | Protocol §2B list; four-part CLOSED in `SECTION_2_VERIFIER_VERIFICATION_2026-07-16.md` / `four_part_coverage.json` |
| 2B | Observation provenance | **OPEN** | `in-agent` | Every solution fact visible in UI before decision (not harness-only) | *(protocol checkbox; no dedicated close artifact)* |
| 2B | Entity binding | **OPEN** | `in-agent` | Multi-object milestones must bind same order/product/email/etc. | Related PARTIAL: §3A cross-object |

### 2C Independent review

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 2C | Reviewer B independent expectations | **CLOSED** | — | — | `SECTION_2_INDEPENDENT_REVIEWER_2026-07-16.md`, `reviewer_b/scoring_sheet_template.csv` |
| 2C | B vs verifier reconciliation | **CLOSED** (M348 open design) | design follow-up | Optional design review of M348; no mass-fix done | `reviewer_b/RECONCILIATION_LOG.md` |
| 2C | Reviewer C blind trajectories | **CLOSED** | — | — | `SECTION_2C_REVIEWER_C_2026-07-16.md` (10/14) |
| 2C | P1 initial-report sample | **CLOSED** | — | — | B=85 + C=14 packet |
| 2C | P2 full-set / expanded C | **OPEN** | `human (user)` / deferred | Expand trajectory-blind C if formal release requires | same |

### 2D Mutation testing (open findings only)

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 2D | Remove recipient | **PARTIAL** (findings) | disclosure | Disclose survivors M37, M211, M200 (no further mass-fix this pass) | `SECTION_2D_MUTATION_TESTING_2026-07-16.md`, `mutation_results.json`; hardening: `M271_M252_MUTATION_HARDENING_2026-07-16.md` |
| 2D | AND→OR | **PARTIAL** (findings) | disclosure | Disclose survivors M200, M59 | same |
| 2D | Loosen email regex | **PARTIAL** (findings) | disclosure | Disclose survivors M37, M141, M164 | same |

---

## §3 — Reward hacking / invalid episodes

### 3A Exploit checklist (open only)

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 3A | Seed exploit | **PARTIAL** / **MANUAL-BLOCKED** | manual / disclosure | Manual contamination review or permanent limitation; not automatable CLOSED | `SECTION_3_INVALID_EPISODE_AND_SEED_EXPLOIT_HYGIENE_2026-07-16.md`, `seed_exploit_manual_hygiene.json`, `exploit_matrix.json` (85× PARTIAL) |
| 3A | Cross-object milestone composition | **PARTIAL** | `in-agent` | Dedicated mismatch probes for ~34 multi-object sellables | `SECTION_3_REWARD_HACKING_RECONCILIATION_2026-07-15.md` |
| 3A | Machine-readable invalid episodes | **PARTIAL** | `in-agent` | Emit `invalid_event_delivery` / `invalid_instrumentation`; regenerate §3 matrix to CLOSED | `INVALID_EPISODE_ENUM_DESIGN_2026-07-16.md`, `invalid_episode_enum_hygiene.json`, `harness/invalid_episode.py`, `tests/test_invalid_episode_enum.py` |

### 3B Reporting

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 3B | Separate TCR + HAR per model | **OPEN** | report / `in-agent` | Publish two metrics in living draft tables | Raw k=3: `docs/RAW_THREE_SEED_DISTRIBUTIONS.md` |
| 3B | Full model × outcome table | **OPEN** | report / `in-agent` | Four-way safe/harm/incomplete/invalid table (not just break counts) | same |
| 3B | Optional CHR / SCR (P2) | **OPEN** | deferred | Optional narrative metrics | protocol §3B |

---

## §4 — Task realism

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 4A | Human §4A rubric on 33 | **CLOSED** (one human) | — | — | `SECTION_4_TASK_REALISM_2026-07-16.md`, 1D sheet |
| 4A | Publish human–human aggregate agreement | **OPEN** | `human (user)` | Gap 2 or fresh A/B pair | same |
| 4A | Task provenance categories | **OPEN** | `in-agent` / report | Tag human-authored / adapted / adversarial / synthetic per category | protocol §4A |
| 4B | Discoverable-fact path plausibility | **OPEN** | `in-agent` | Audit sellables with hidden/expired/stale facts | protocol §4B |
| 4C | Non-leading language | **OPEN** | `in-agent` | Re-read prompts; rewrite telegraphing traps | protocol §4C |

---

## §6 — Statistical protocol (open only)

| ID | Title | Status | Owner | Close with | Evidence |
|---|---|---|---|---|---|
| 6C | N / families / templates / variants | **PARTIAL** | `in-agent` / disclosure | Annotate scenario-template + cosmetic-variant counts, or disclose unknown | `SECTION_6_STATISTICAL_PROTOCOL_2026-07-15.md`, `PROJECT_INFO.md` §2B |
| 6D | Select stratified k=10 tasks | **OPEN** | `paid k=10` | Living list: **M271** (priority), M354, M362, M366 | same + `STRONGEST_BREAKER_EXAMPLES.md` |
| 6D | Rerun selected at k=10 | **OPEN** | `paid k=10` | Per-model k=10; M271 first | — |
| 6D | Publish k=10 headline distributions | **OPEN** | `paid k=10` / report | Distinguish from k=3 corpus | — |

---

## §7 — Final artifacts (assembly)

| ID | Title | Status | Owner | Close with | Evidence building blocks |
|---|---|---|---|---|---|
| 7 | Environment validation matrix | **OPEN** | `in-agent` / report | One paste-ready matrix of affordances/events/reset/UI | §1A audits + `affordance_parity.json` / `checkout_parity.json` |
| 7 | Verifier validation matrix | **OPEN** | `in-agent` / report | Per-sellable four-part + near-miss + mutation status | `four_part_coverage.json`, §2D `mutation_results.json` |
| 7 | Reward-hacking audit artifact | **OPEN** | `in-agent` / report | Consolidated §3A results for report | `exploit_matrix.json`, §3 audits |
| 7 | Task realism annotation sheet | **PARTIAL** | `human (user)` | Needs Gap 2 for true inter-rater; one `human_rater` sheet exists | 1D/§4 audits |
| 7 | Taxonomy crosswalk | *(content done in §5 — not listed as open work)* | — | Paste from `docs/TAXONOMY_CROSSWALK.md` | §5 CLOSED |

---

## §8 — Sign-off (meta; remains open until above close)

| Scope | Status | Owner | What’s left |
|---|---|---|---|
| Initial external report | **OPEN** | multi | All P0/P1 closed or tasks removed; regenerate final numbers; headline evidence + manual review; list open P2/P3 in limitations |
| Formal benchmark / paper | **OPEN** | multi / deferred | Full independent + multi-rater review; §6D k=10; external/held-out generalization where claimed |

*(§8 mutation-archetype sample coverage is CLOSED — omitted.)*

---

## Quick resume index (credit / volatile / human)

| Topic | Path |
|---|---|
| Protocol (canonical) | `docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` |
| Living report | `PROJECT_INFO.md` |
| M37 Sonnet block | `docs/history/audits/M37_PREPUBLICATION_REVALIDATION_2026-07-15.md` |
| M252/M271 post-hardening | `docs/history/audits/M271_M252_POST_HARDENING_RESCREEN_2026-07-16.md` |
| M271 restore (volatile) | `docs/history/audits/M271_PROMOTION_RECASCADE_2026-07-16.md` |
| Human 1D / §4A | `SECTION_1D_HUMAN_CALIBRATION_2026-07-16.md`, `SECTION_4_TASK_REALISM_2026-07-16.md` |
| Reviewer B / C | `SECTION_2_INDEPENDENT_REVIEWER_2026-07-16.md`, `SECTION_2C_REVIEWER_C_2026-07-16.md` |
| Invalid-episode vertical slice | `INVALID_EPISODE_ENUM_DESIGN_2026-07-16.md`, `SECTION_3_INVALID_EPISODE_AND_SEED_EXPLOIT_HYGIENE_2026-07-16.md` |
| §6D candidates | `SECTION_6_STATISTICAL_PROTOCOL_2026-07-15.md` |

---

*Updated 2026-07-16 after human B/C/1D/§4A ingest. No Anthropic credit retries performed for this document.*
