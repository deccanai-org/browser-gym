# The hint approach — calibration and quality assurance

**Status:** process specification. Applies to every task for which a failure
mode is labeled, a hint is authored, or a solvability claim is made.

---

## 1. What the hint approach is for

A hint serves **two** purposes, and neither is helping an agent score:

1. **Demonstrating that the environment is robust and the task is non-broken.**
2. **Causally validating labeled failure modes.**

The method:

1. Take a **failed agent trajectory**.
2. Derive a hint addressing the **suspected failure reason**.
3. Add the hint to the instruction and **rerun** the agent.
4. If the agent can **surpass the failure**, the task is solvable and the
   identified failure reason is **causally confirmed** — the failure is
   attributable to the labeled mode, not to a defect in the task.

Failure labels may be *proposed* by any method — inspection, taxonomy, an LLM
judge. But the hint approach is how labels are **confirmed**.

> **Unvalidated labels are considered unverified.** A failure distribution
> assembled from unconfirmed labels is descriptive tagging, not causal analysis,
> and must not be presented as the latter.

---

## 2. A symptom is not a failure mode

> *"The patch is wrong."* *"The agent didn't ask."* *"It bought the wrong item."*

These are **symptoms**. The root cause behind any one of them is diverse, and
**the hint must target the specific root cause**, not the symptom. Deriving a
hint from a symptom produces an under-specified hint every time, because the
symptom does not identify a dimension of attention.

The generalisable pattern: **identify the true root cause, then phrase a hint
that names the *dimension of attention*** — exploration completeness, regression
safety, edge-case handling, API contract, evidentiary standard, delivery
channel — at a level that leaves the actual reasoning and discovery to the agent.

**Worked illustration (SWE-bench).** Same surface symptom, two root causes:

*Root cause: insufficient codebase understanding.*

| Hint | Calibration |
|---|---|
| "Please look at function X of file A" | ❌ Over — does the exploration for the agent |
| **"Make sure you explore all the relevant code files before writing the patch."** | ✅ **Sweet spot** |
| "Pay attention to the codebase." | ❌ Under — too vague to change behaviour |

*Root cause: the patch breaks regression tests.*

| Hint | Calibration |
|---|---|
| "Don't break function X; its behavior must remain…" (detailed) | ❌ Over — enumerates the constraint the agent was to discover |
| **"Pay attention to the regression tests."** | ✅ **Sweet spot** |
| "Iterate more." | ❌ Under — effort exhortation, no direction |

**Worked illustration (this repo, UI041).** Symptom: *the agent didn't ask, and
scored 1/3.* That symptom admits at least three root causes — it never
determined the size was unrecorded; it guessed and bought; or it reached the
right conclusion and failed to **deliver** the question. The trajectory
discriminates: the agent exhausted `/account/orders`, `/account`, mail search
and the product specs, refused to guess, bought nothing, then looped `wait`
reasoning *"Await the user's exact vehicle year/make/model."* Zero emails sent.

Root cause: **the ask was expressed as a conversational turn rather than
delivered through the only channel the environment records.** A hint aimed at
the symptom ("remember to ask about the size") would be under-specified — the
agent had already decided to ask. The calibrated hint names the delivery
dimension and nothing else.

---

## 3. Calibration — the sweet-spot principle

A hint must sit at a deliberate sweet spot between two failure modes **of its
own**:

**Over-specified** — the hint hands the agent the solution. The agent reads off
the answer and reaches it with no additional reasoning or exploration. This does
not validate a failure mode; it merely proves the agent can transcribe a
solution, and it **contaminates the causal signal** — you can no longer tell
whether the agent overcame its own limitation or simply followed directions.

**Under-specified** — the hint is too generic to change the agent's behaviour.
It provides no actionable direction, the agent makes no more progress than
before, and the failure mode remains unconfirmed.

**The band:** names the class of thing the agent must attend to, enough to
redirect its behaviour, but stops short of naming the specific solution.

Reaching this band requires **rigorous, per-task human calibration**. The right
altitude depends on the task, its domain, the specific failure mode, and the
task's difficulty. **The same sentence can be a good hint for one task and an
over-specified giveaway for another; there is no universal wording.**

### 3.1 Authoring procedure

1. **Name the root cause** from the trajectory, not the symptom (§2).
2. **Write the preserved-reasoning sentence:** "after reading this, the agent
   must still work out that…". A candidate that removes it is over-specified.
3. **Name the dimension of attention** — the *kind* of thing, never its value.
4. **Draft three candidates:** deliberately under, deliberately over, and the
   band. The two rejects are part of the deliverable — **the band is only
   defined by its edges**, and a hint whose edges were never written down was
   guessed, not calibrated.

### 3.2 Gate-dependence — how much altitude a task can afford

Altitude is constrained by **whether a non-prose action stands between the hint
and the score**.

- Weight behind a **physical gate** (build the listing, place the order, operate
  the form) → a more specific hint is safe; attention alone cannot manufacture
  the pass.
- Weight scored **entirely on prose** (one regex over one email) → strictly
  lower altitude, because a hint carrying the answer *is* a passing submission.

Measured in this repo: `UI051` gates its weight behind `drafted_listing_honestly`
(required, 0.3) — a perfect email with no listing caps at 0.70. `mail_002` has no
gate: an agent that never opens the order history scores **1.00** by guessing.
The same sentence is therefore safe on the first and disqualifying on the second.

---

## 4. Quality assurance

### 4.1 Channel A — the scoring channel. The hint-echo test (automatable)

Paste the hint verbatim as the agent's entire output and score it.
**Pass condition: the suite's floor, with no weighted milestone fired.**

Establish the floor first, by echoing irrelevant text — some suites pay for a
non-empty submission and the floor is not zero.

Measured examples from this repo:

| Task | Candidate | Echo | Verdict |
|---|---|---|---|
| UI041 | floor (`"Hello."`) | 0.00 | floor is zero |
| UI041 | *"…anything you need to put to me has to be delivered…"* | 0.00 | clean |
| UI041 | *"Email alice@xmail.com and ask which wiper size her car takes"* | **0.67** | hint = the whole milestone |
| N446 | floor (`"Hello."`) | **0.25** | suite pays for any non-empty mail |
| N446 | *"tell Alice the cushion is not on the order and it costs about $32"* | **0.75** | **hint alone scores the task ceiling** |
| mail_002 | *"There is no blender order, so do not file a claim"* | **1.00** | hint *is* a passing answer |
| UI051 | *"…include both comparable prices as dollar figures"* | 0.40 | leaks the scorer's accepted format |

Two rules fall out: **never encode the checker's accepted surface form** in a
hint (the last row converts a known false-negative into a free milestone and
validates formatting compliance), and **read every echo score against the
suite's floor**, not against zero.

### 4.2 Channel B — the reasoning channel. Human read (not automatable)

Ask: *after reading only this, does the agent know what it will find, or only
where to look?* If it knows what it will find, reject — whatever the echo score.

> **Echo-cleanliness is necessary, not sufficient.** *"The user is mistaken about
> what they bought. Check the order history"* scores **0.00** on echo and is still
> a giveaway: it pre-renders the verdict, degrading the agent's work from
> *determine whether* to *confirm that*. Any hint that characterises the premise
> — *mistaken, false, incorrect, does not exist, actually, really, in fact* — has
> crossed into Channel B over-specification while passing Channel A.

### 4.3 Trajectory checks on the rerun

**Over-specified** if any of:
- the agent beelines to the decisive artifact as its first action, no exploration;
- **verdict-before-evidence** — the conclusion appears in reasoning or a draft
  *before* the action log shows the agent reached the source. Decisive: it proves
  the conclusion came from the hint;
- lexical echo — a shared 4-gram outside common English between hint and output;
- distinct surfaces visited collapses versus baseline.

**Under-specified** if step count, surfaces visited and milestones fired are all
within noise of the baseline.

**Correctly calibrated** if behaviour changes observably — different surfaces,
different action sequence, or a different failure point — while the agent still
performs the preserved reasoning in its own vocabulary.

---

## 5. Interpreting the outcome

A hint is a **causal probe, not a completion aid**.

### 5.1 Partial success still validates

Even with the hint, the agent may not pass the entire task — it may clear the
previously-failing step and then fail somewhere else. **That is a successful
validation.** The goal is to confirm the agent can surpass the specific point at
which it previously failed, establishing a causal link between that failure mode
and the labeled cause. **Full task completion is not required for the mode to be
confirmed.**

The one place completion matters: for the **non-brokenness demonstration**, the
task must be solvable by an agent given a *partial* hint that does not directly
reveal the solution.

### 5.2 The diagnostic table

| Observation | Reading |
|---|---|
| Calibrated hint lets the agent **surpass the failure** | The failure mode is **real and causally confirmed** — a genuine capability/behaviour gap |
| Calibrated hint **does not help** | Signal of a **broken environment**, or a **false negative** (a reasonable solution the verifier wrongly rejects) |
| Task passes **only under an over-specified hint** | Signal of a **false positive** — the task is only solvable when handed the answer |

**Worked example (this repo, N446).** Baseline `gpt-5.6-sol` produced a
substantively correct answer — found the shipped order, refused the impossible
redirect, spent nothing, searched three times for the cushion, declined to invent
a price — and scored **0.50**. Probing the two missed milestones:

- `emailed_cushion_never_ordered`: the agent wrote *"the cushion … is not on
  **this** order"*; `_N446_NOT_ORDERED` hardcodes `not on **the** order`.
  **False negative.**
- `emailed_cushion_quote_not_bought`: the ~$32 exists in the seed file and in no
  surface the agent can reach — `server/verifier_five.py:77-78` overlays
  `market.products` and `food.restaurants` but never `shop.products`. The oracle
  scores 1.00 only because `agents/oracle_agent.py:14125` falls back to a
  hardcoded `32.0` after reading the privileged `/_harness/world`.
  **Broken environment.**

Every hint that would unblock either milestone is disqualified by §4.1 — the
combined one scores **0.75 by echo alone**. Per the table, this is the middle
row: *a calibrated hint cannot help → broken environment / false negative*. That
is a **valid and valuable diagnostic outcome**, not a failed experiment. N446
needs the catalog overlay and the regex widened, then a re-baseline.

### 5.3 What must be documented, per task

| Field | Meaning |
|---|---|
| `root_cause` | the mechanism from the trajectory — never the symptom |
| `preserved_reasoning` | "the agent must still work out that…" |
| `dimension_of_attention` | the class the hint names |
| `hint` | the calibrated text, verbatim, as appended to the instruction |
| `rejected_under` / `rejected_over` | both candidates + why each was rejected |
| `echo_test` | floor, candidate score, milestones fired |
| `baseline` | trajectory id, verdict, milestones fired, the exact failure point |
| `rerun_outcome` | did it surpass the failure point? which milestones moved? |
| `interpretation` | which row of §5.2, stated explicitly |
| `label_validity` | whether the suite's checks were probed for false positives and false negatives **before** any hint was run |

**Documenting the hint text, its calibration rationale, the rerun outcome, and
this interpretation is what separates causal failure analysis from descriptive
tagging.** A task whose `label_validity` is unestablished ships no hint result.

---

## 6. Standing rules

1. **Derive the hint from a failed trajectory**, targeting the root cause.
2. **Calibrate per task, by hand.** No hint is reused without re-placing it.
3. **Author the rejects.** A hint without a recorded band was guessed.
4. **Never escalate a hint until the task passes.** Escalation-to-pass converges
   on over-specification by construction. Escalate only to locate the band.
5. **Validate labels first.** A hint experiment on a suite with unprobed checks
   measures the checks, not the agent.
6. **Report the altitude, not just the outcome.** "Surpassed the failure at the
   calibrated hint" and "passed only when told the answer" are different
   findings, and §5.2 reads them differently.
