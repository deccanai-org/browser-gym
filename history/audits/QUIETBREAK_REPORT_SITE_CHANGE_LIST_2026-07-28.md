# QuietBreak report-site change list — 2026-07-28

Planning + Section 4 lock. **§1 funnel numbers are locked: ~250 → Qwen 85 / GPT-5.1 78 / GPT-5.5 70 / Sonnet 65** (customer-facing; 85 = sellable/Qwen-break story). Retracts prior “drop Qwen” ship and incoherent 112/82/65 mix. Remaining items (Sol/Opus move, Task Explorer cuts, sanitize) are not yet implemented. Sources: `docs/report-site/Report.dc.html`, `Task Explorer.dc.html`, `data/tasks6.json`, `trajectories/sellable_breakers_v2.csv`, `TABLE1_STRONGEST_TIER_RECOMPUTE_20260721.json`, `docs/history/plans/CURRENT_WORK_2026-07-21.md`, `PROJECT_INFO.md`, `docs/history/forensics/sol_opus/*`, and the 2026-07-28 best-effort 312-task break census.

---

## Current page order (grounding)

| # | `id` | What it is today |
|---|---|---|
| 01 | `#top` | Hero + 312 / 85 stats |
| 02 | `#why` | Why QuietBreak |
| 03 | `#environment` + apps | Multi-app world |
| 03b | `#taxonomy` | Mechanism families on 83+2 |
| **04** | `#leaderboard` | **LOCKED: ~250 → 85 / 78 / 70 / 65 with Qwen** (see §1) |
| **05** | `#comparison` | **Sol vs Opus N=75** (after screening) |
| 06 | `#methodology` | Reset → classify + gates |
| — | (cta) | Task explorer promo (six samples) |
| 07 | `#scope` | Scope / interpretation |

Task Explorer: six episodes in `data/tasks6.json` — M95, M312, M213 (Sonnet 4.6) and M47, M76, M142 (GPT-5.5).

---

## 1. Section 4 funnel — **LOCKED** (2026-07-28 stakeholder decision; Qwen restored)

### Locked graphic (ship these)

**Customer strip:** out of **~250** adversarially screened tasks → **Qwen 85 · GPT-5.1 78 · GPT-5.5 70 · Sonnet 65**.

| Bar | Number | Customer meaning |
|---|---:|---|
| Denom | **~250** | Adversarially screened tasks (graphic round of exact **N=269**) |
| Qwen | **85** | Broke Qwen (= sellable / release ledger count — accepted clean story) |
| GPT-5.1 | **78** | Broke GPT-5.1 |
| GPT-5.5 | **70** | Broke GPT-5.5 |
| Sonnet | **65** | Broke Sonnet 4.6 — **never use census 83** |

**What `Report.dc.html` ships:** bars **85 / 78 / 70 / 65** (Qwen first) + one-liner caption *“Out of ~250 adversarially screened tasks.”* Keep copy short — **no** long TABLE1 / nested-universe / “No Qwen” footnote.

### Author note (not for the page)

85 is the sellable/Qwen-break story: best clean customer framing from messy evidence. Mid-bars 78 / 70 / 65 remain the TABLE1 independent counts among the 85. Do not paste methodology essays onto the graphic.

### RETRACTED — prior locks

- **Drop-Qwen ship** (bars 78 / 70 / 65 only, “of 85 sellable”) — superseded; Qwen bar restored at **85**.
- **112 / 82 / 65** mix (312 best-effort GPT paired with sellable Sonnet) — incoherent; must not ship.
- Strongest-or-deeper **85 / 84 / 72 / 65** as the §4 claim set — retired as primary framing (numbers may appear as bar heights only under the ~250 story).

**Do not revive 112 / 82 / 65.** Keep 71 / 112 / 82 / 83 only in methods/appendix census tables.

### Nested / source crib (authors)

| Model | N | Source |
|---|---:|---|
| Qwen (graphic) | **85** | Sellable ledger count — customer “broke Qwen” |
| GPT-5.1 | **78** | TABLE1 independent `g51` among 85 |
| GPT-5.5 | **70** | independent `g55` |
| Sonnet | **65** | independent `gson` / Table 1 Sonnet-break |
| Qwen (measured panels) | **31 broke / 34 with evidence** | CSV — sparse; **do not** put “31” on the customer strip |

### ~250 denominator

| Exact N | Label | Source |
|---:|---|---|
| **269** | Adversarially break-screened (strict) | `CURRENT_WORK_2026-07-21.md` / Table 1 denom crib |
| **203** | cascade_v2 latest-wins matrix bookkeeping | same |
| **312** | Live registry (pre-Sheets) | `server.tasks.TASKS` / PROJECT_INFO |
| **~250** | **Graphic round** of **269** | Customer-facing “adversarially screened” denom |

### Best-effort independent breaks on all 312 (appendix only — **not** §4)

| Model | Broke ≥2/3 | Have evidence | No evidence |
|---|---:|---:|---:|
| Qwen | **71** | 216 | 96 |
| GPT-5.1 | **112** | 191 | 121 |
| GPT-5.5 | **82** | 129 | 183 |
| Sonnet | **83** | 124 | 188 |

These **do not descend** (5.1 > Qwen) and **Sonnet ≠ 65**. Unfit as the §4 funnel.

### Evidence gaps (authors only; stay off the customer page)

- Qwen panels sparse on sellables (~51/85 missing) — graphic still uses **85** as the accepted sellable/Qwen-break story.
- 65 Sonnet-break ≠ 83 Sonnet≥2/3 across all 312.
- cascade_v2 alone only shows **30** Sonnet≥2/3 in the 203-row stop table; most of the 65 live in **v1-heavy** ledger history.
- Do not revive “~1/3 survive to strongest” for 65/85 (that is 76.5%). The ~1/3 figure is **85/269 ≈ 31.6%** (sellables among adversarially screened).

---

## 2. Task Explorer — keep ~4 / cut 2

### Current six

| Task | Model | Vein | Demo notes |
|---|---|---|---|
| **M95** | Sonnet | content-default | 4 steps; crisp; gift-message leak |
| **M312** | Sonnet | implicit-constraint | 16 steps; fluent shopping; Bucket B fairness callout |
| **M213** | Sonnet | tool-affordance | False card-swap confirmation; clear product story |
| **M47** | GPT-5.5 | sycophancy | Strong premise story; **21 steps of native `<select>` ArrowDown fumbling** |
| **M76** | GPT-5.5 | ask-dont-guess | 4 steps; ambiguity → irreversible cancel |
| **M142** | GPT-5.5 | infeasibility | Catalog rating/stock trap; grid looks odd (5.5 1/3 vs Sonnet 3/3) |

### Recommended keep (4)

| Keep | Why |
|---|---|
| **M95** | Shortest Sonnet demo; customer-safe; content-default |
| **M213** | Distinct mechanism (tool-outcome / false confirmation); multi-app Mail |
| **M76** | Short GPT-5.5 demo; ask-don’t-guess; high clarity |
| **M312** | Implicit-constraint × deference; shows ordinary shopping still fails |

Model mix: **3 Sonnet + 1 GPT-5.5**. Acceptable for v1 demos; optional follow-up: swap M312→M47 only if a cleaned GPT sycophancy video without select thrash exists.

### Recommended cut (2)

| Cut | Why |
|---|---|
| **M47** | Video/trajectory is dominated by **native dropdown motor struggle** (ArrowDown / Alt+ArrowDown / letter keys). Reads as “agents can’t use our UI,” not “agents defer to a false premise.” Highest customer-risk sample. |
| **M142** | Infeasibility + rating floor looks like a **catalog/UI setup trick**; weaker sell vs other veins; odd mid-cascade grid for a customer page. |

### Editorial / data follow-ups when cutting to 4

- Shrink `data/tasks6.json` → `tasks4.json` (or filter in JS); update uploads list if unused assets should leave the public tree.
- Report CTA + Task Explorer hero: “six” → “four”; retab grid `repeat(6)` → `repeat(4)`.
- Fix M76 editorial if kept: the sample episode **cancels both** subscriptions after the first cancel — copy currently says “cancels one.” Soften to “cancels under ambiguity” or pick a seed that stops at one.
- Drop or rewrite M312 “Bucket B” fairness jargon for external readers.

---

## 3. Revealing / bad-info cut list (external customers)

### Cut or rewrite (high priority)

| Location | Issue | Action |
|---|---|---|
| Report `#environment` / Shared state | Names internal `WorldState` | Say “one shared application state” — no code identifier |
| Report apps blurb | `update_event` has no overlap guard vs `create_event` | **Cut** — gym implementation quirk, not a customer selling point |
| Report methodology | “The harness resets…” / Set-of-Mark / mark language in explorer steps | Soften to “evaluation driver” / “annotated screenshots”; strip `mark N` from step headlines in public explorer |
| Task Explorer provenance | “taken from the harness rather than the agent's report” | Soften: “from ground-truth application state” |
| Task Explorer M312 fairness | “Ledger records this as Bucket B” | Rewrite without internal fairness buckets |
| Task Explorer M95 seed/failure | Emphasizes message **hidden from review screen** / collapsed panel | Soften so it doesn’t read as “we hid the evidence off the review page”; stress that it was **visible on the agent’s cart path** |
| Task Explorer M47 | Native-select thrash in step list + thinking | **Cut episode** (above) or heavily truncate step reasoning |
| Report Sol/Opus footer | “2 were rejected on fairness grounds”; “no significance claim”; “breaker-enriched subset” | Soften: keep “controlled comparison set” without advertising rejects in the hero strip; move fairness rejects to a one-line methods note or omit |
| Report taxonomy footnotes | Injection + source-anchoring gray bars | Keep only if customers need taxonomy completeness; else fold into methods (“two specialized footnotes”) |
| JSONL downloads | `localhost:8000`, screenshot paths under `screenshots/_demo_*`, raw thinking | Prefer scrubbed exports for public; or gate download behind “research dump” |
| Scope cards | Fine overall; “operational screening rule” is ok | Keep; avoid adding verifier-bug / incomplete / credit-BLOCKED language |

### Soften (medium)

| Item | Note |
|---|---|
| Full agent chain-of-thought in the step panel | High value for researchers; for customers, default collapsed “show reasoning” or show only the break step |
| Token counts / episode IDs / seed badges | Looks operational; optional hide |
| “~750 verifier tests” | Fine if true; don’t add “four live tasks fail no-op” style audit leftovers |
| Oracle gate copy | “hand-coded UI-only oracle” → “safe completion path verified before screening” |

### Do **not** surface on the public site

- Verifier bug forensics, M271 volatility / seed-0 hinge, M56 hold, M297/M298 rejects (except maybe a single anonymized “two comparison tasks excluded”)
- Credit-BLOCKED / incomplete mid-cascade counts
- Motor-vs-reasoning Section 1C internals
- Sellable CSV paths, shard logs, GCP/Gemini census

---

## 4. Sol / Opus — move up + rewrite notes

### What the N=75 story is (from PROJECT_INFO + SOL_OPUS docs)

- **Track:** closed **comparison**, not the sellable promotion path.
- **Set:** flagship20 ∪ xmodel37 ∪ xmodel18 = **75** (thin-vein M342–M350 **discarded**).
- **Raw ≥2/3:** Sol **40/75**, Opus **30/75**, overlap **25**, Sol-only **15**, Opus-only **5**, union **45**.
- **Forensic:** **43** confirmed genuine; **2** rejected (M297 Bucket C; M298 seed-satisfied gate).
- **Venn vs sellables:** 75 is **neither subset nor superset** of the 85 (`|A ∩ B| = 63`).

### Placement

**Move `#comparison` (current 05) to immediately before `#leaderboard` (current 04).**

Suggested new numbering:

1. … taxonomy …
2. **Controlled comparison — Sol vs Opus (N=75)** ← first model results readers see
3. **Cascade screening funnel (~250 → 85 / 78 / 70 / 65 with Qwen)**
4. Methodology …
5. Task explorer CTA …

Nav + section index digits must renumber accordingly.

### Copy direction (more appealing, less negative)

**Lead with:**

- Same fixed 75 tasks, same protocol → **directly comparable**.
- Sol **40** vs Opus **30** verifier-confirmed breaks; **25** shared failures (substantial overlap).
- Frames QuietBreak as already stressing **newest** flagship systems, not only the cascade ladder.

**Reduce / relocate:**

| Current tone | Prefer |
|---|---|
| “enriched for difficult cases” as apology | “mechanism-diverse fixed set drawn from the registry” |
| Hero-adjacent “2 rejected on fairness” | Methods footnote or omit on v1.0 page |
| “no significance claim is made” | Optional one clause under methods; don’t dominate the strip |
| “Reported apart from the cascade because the protocol differs” | Keep, but as a **badge of rigor**, not a disclaimer dump |

**Do not claim:** Sol/Opus raw breaks ⊆ sellable 85; population-wide ranking; statistical significance.

---

## 5. Ordered implementation checklist

1. **Lock funnel numbers** — **DONE:** ship **~250 → Qwen 85 / GPT-5.1 78 / GPT-5.5 70 / Sonnet 65**. **Retracted** drop-Qwen-only strip and incoherent 112/82/65 mix. Exact denom 269 stays methods-only.
2. **Rewrite Section 04** bars + caption — **DONE:** bars Qwen 85 · GPT-5.1 78 · GPT-5.5 70 · Sonnet 65; short ~250 caption; long TABLE1 footnote removed.
3. **Move Sol/Opus block above Section 04**; renumber section labels / sticky nav.
4. **Rewrite Sol/Opus copy** per §4 (appeal first; fairness rejects demoted).
5. **Cut Task Explorer to 4:** keep M95, M213, M76, M312; cut M47, M142 (or swap if a clean GPT sycophancy asset appears).
6. **Update** Report CTA, explorer hero stats, tab grid, `data/tasks*.json`, and orphaned uploads references.
7. **Sanitize revealing copy:** `WorldState`, overlap-guard quirk, Bucket B, harness/mark_id, M95 “hidden from review” framing.
8. **Optional:** collapse long CoT by default; scrub JSONL downloads for localhost / internal paths.
9. **QA pass:** numbers match TABLE1 + CURRENT_WORK denom crib; Sol/Opus still 40/30/25/15/5; no sellable CSV edits.
10. **Ship** report-site HTML only after checklist 1–8 signed off — this audit doc is not the ship.

---

## Appendix — quick source map

| Claim | Where |
|---|---|
| 65 / 7 / 12 / 1 strongest tiers | `sellable_breakers_v2.csv` + TABLE1 audit |
| 78 / 70 / 65 independent among 85 | TABLE1 JSON `g51` / `g55` / `gson` |
| 269 adversarially screened; 203 v2 | `CURRENT_WORK_2026-07-21.md` §B |
| 312 registry; 85 ledger | `PROJECT_INFO.md` |
| Sol/Opus 40/30/25/15/5 on 75 | `PROJECT_INFO.md` §2A; `SOL_OPUS_SELLABLE_VENN.md` |
| Qwen sparse on sellables | CSV `models_broken` (34 present / 31 ≥2/3); graphic still uses **85** |
| 312 best-effort 71/112/82/83 | 2026-07-28 census; **archived — not §4**. §4 locks **85/78/70/65 with Qwen** |
| Current §4 / §5 order | `docs/report-site/Report.dc.html` `#leaderboard` then `#comparison` |

*End of change list.*
