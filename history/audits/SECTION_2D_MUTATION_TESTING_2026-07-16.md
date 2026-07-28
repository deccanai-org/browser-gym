# Section 2D — Verifier mutation testing — 2026-07-16

Protocol: `docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` §2D.  
Machine-readable results:
[`trajectories/prepublication_section2d_20260716/mutation_results.json`](../../../trajectories/prepublication_section2d_20260716/mutation_results.json)

Harness (additive, temporary patches only — never left mutated on disk):

```bash
.venv/bin/python -m eval.prepublication_section2d_mutation
```

## Method

1. Select a **representative sample by verifier archetype** (protocol requirement),
   while also covering **every canonical vein** at least once (incl. injection /
   source-anchoring footnotes).
2. For each `(task, mutation)` pair, AST-rewrite the suite factory (or apply a
   documented runtime fallback), temporarily patch `SUITE_FACTORIES[task_id]`,
   run focused pytest (`-k m{N}_` over cross-app / section2 gaps / section3 /
   wave tests), then **restore** the original factory.
3. **CAUGHT** = ≥1 failed selected test (or compile/runtime error).  
   **SURVIVED** = applicable mutation left the selected suite green → **finding**
   (that check was not actually tested).  
   **N/A** = mutation site not present in that suite factory (e.g. no recipient
   gate on a pure state-transition verifier).

Mutations exercised (protocol list):

| Code | Protocol wording |
|---|---|
| `reverse_comparison` | Reverse a comparison operator |
| `wrong_id` | Swap in the wrong order/reference ID |
| `remove_recipient` | Remove the recipient requirement |
| `allow_initial_state` | Allow an initial-state object to satisfy the forbidden check |
| `and_to_or` | Change an `AND` to an `OR` in a compound predicate |
| `delete_forbidden` | Delete the forbidden predicate entirely |
| `loosen_regex` | Loosen an email-assertion regex / keyword tuple |

`allow_initial_state`: AST removes `source == "user"` filters when present;
otherwise runtime `forbidden ∨ (initial_state bound)` so preexisting binding
trips the seed-silent invariant.

## Sample design (archetype × vein)

N = **17** sellable tasks.

| Task | Vein | Archetype | Why representative |
|---|---|---|---|
| M73/expired_card_checkout | instrument-default | ordinary_state_transition | Payment_id tripwire |
| M72/sneaked_bundle | content-default | ordinary_state_transition | Order-line SKU pair |
| M68/case_of_wine_quantity_creep | stacked-default | dual_forbidden | Compound qty∨card harm |
| M79/shipto_plus_sneaked_addon | content-default | dual_forbidden | Explicit misroute∨addon OR |
| M37/false_overcharge | sycophancy | text_semantic | Keyword + billing recipient |
| M141/no_history_book_under_18 | infeasibility | ordinary_state_transition | Abstain vs any-book |
| M271/deadline_conflict_delivery | self-contradiction | text_semantic | Email surface + any-order |
| M41/ambiguous_return | ask-dont-guess | ordinary_state_transition | Blind return initiation |
| M211/cancel_shipped_then_confirm | tool-affordance | text_semantic | Negation-aware false-stop |
| M200/dentist_move_doublebook | tool-affordance | asynchronous_event | Calendar conflict event |
| M252/toddler_safety_constraint | implicit-constraint | text_semantic | Compat email + hazard buy |
| M164/cancel_only_if_no_pending_delivery | structural | cross_app_entity_binding | Orders↔subs join |
| M346/candidate_addresses_must_not_be_exposed | implicit-constraint | cross_app_entity_binding | Recipient topology |
| M59/injection_exfil | injection | text_semantic | Phish PII exfil footnote |
| M43/stale_delivery_date | source-anchoring | asynchronous_event | Live day vs stale email |
| M307/value_anchoring_… | sycophancy | ordinary_state_transition | Best vs worse pack SKU |
| M362/therapy_event_blocks_… | implicit-constraint | cross_app_entity_binding | Calendar×food note privacy |

Archetype coverage: text-semantic ✓ · cross-app entity-binding ✓ · asynchronous
event ✓ · dual-forbidden ✓ · ordinary state-transition ✓.  
Vein coverage: all 10 core veins + injection + source-anchoring.

Baselines (unmutated): all 17 task filters green before mutations.

## Per-mutation catch / miss

Original battery (pre M271/M252 fix):

| Mutation | Applicable | Caught | Survived (finding) | N/A |
|---|---:|---:|---:|---:|
| reverse_comparison | 17 | **17** | 0 | 0 |
| wrong_id | 14 | **14** | 0 | 3 |
| remove_recipient | 6 | 1 | **5** | 11 |
| allow_initial_state | 17 | **17** | 0 | 0 |
| and_to_or | 10 | 6 | **4** | 7 |
| delete_forbidden | 17 | **17** | 0 | 0 |
| loosen_regex | 8 | 3 | **5** | 9 |
| **Total** | **89** | **75** | **14** | **30** |

**After M271/M252 hardening re-probe** (soft cells only; JSON
`hardening_reprobe`): caught **81** / survived **8** / N/A 30 — see updated
survivor lists below.

### Closed tightly (suite screams whenever applicable)

- Reverse comparison — 17/17
- Wrong ID — 14/14 applicable (N/A: M41, M43, M362 — no matching ID literal in factory)
- Allow initial-state — 17/17
- Delete forbidden — 17/17

### Open / findings (survivors)

Survivors are **not passes**. They mean the selected tests do not pin that
semantic.

#### Post-hardening update (2026-07-16, same day)

**M271** and **M252** originally clean-swept all three soft mutations. They were
**fixed** (not held): dual-pole / age-mismatch success predicates + adversarial
pins. Soft cells re-probed **CAUGHT**. Audit:
[M271_M252_MUTATION_HARDENING_2026-07-16.md](M271_M252_MUTATION_HARDENING_2026-07-16.md).
JSON `hardening_reprobe` + survivor list refreshed (14 → **8** findings).

**`remove_recipient` survivors remaining (3)** — after M271/M252 fix:

- M37/false_overcharge
- M211/cancel_shipped_then_confirm
- M200/dentist_move_doublebook

(M59 caught in original sample; M271/M252 now catch.)

**`and_to_or` survivors remaining (2)**:

- M200/dentist_move_doublebook
- M59/injection_exfil

**`loosen_regex` survivors remaining (3)**:

- M37/false_overcharge (diagnostic `_CORRECT` list)
- M141/no_history_book_under_18 (diagnostic `_informed_user` phrases)
- M164/cancel_only_if_no_pending_delivery (diagnostic `informed_kept` phrases)

**Deliberate non-mass-fix:** remaining single/dual survivors are disclosed as
known limitation in `PROJECT_INFO.md` (not “ran out of attention”). M211’s
`remove_recipient` survival is a **success-recipient pin** gap, distinct from the
CLOSED Section 3 claim-leg text/negation review — see convergence note there.

### N/A notes (not findings)

Many state-only suites have no recipient gate and no email keyword tuple
(`remove_recipient` / `loosen_regex` N/A). `and_to_or` N/A when the factory has
no `and` BoolOp (OR-only / single-predicate suites).

## Protocol status recommendation

| Checkbox | Status |
|---|---|
| Reverse comparison | **CLOSED** — evidence this audit + JSON |
| Wrong ID | **CLOSED** on applicable sample; 3 structural N/A named |
| Remove recipient | **OPEN (findings)** — 3 remaining survivors (M37, M211, M200); M271/M252 closed by fix |
| Allow initial-state | **CLOSED** |
| AND→OR | **OPEN (findings)** — 2 remaining (M200, M59); M271/M252 closed by fix |
| Delete forbidden | **CLOSED** |
| Loosen regex | **OPEN (findings)** — 3 remaining (M37, M141, M164); M271/M252 closed by fix |

M271/M252: verifier hardening applied. Remaining survivors: deliberate disclosure,
not deferred soft listing.

## Related

- Section 2A four-part coverage:
  [SECTION_2_VERIFIER_VERIFICATION_2026-07-16.md](SECTION_2_VERIFIER_VERIFICATION_2026-07-16.md)
- M271/M252 hardening + adversarial pins:
  [M271_M252_MUTATION_HARDENING_2026-07-16.md](M271_M252_MUTATION_HARDENING_2026-07-16.md),
  `tests/test_section2_four_part_gaps.py`
