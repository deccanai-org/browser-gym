# Industry alignment — modernizing the report's terminology + generalizing beyond shopping
Research 2026-07-10 (two agents: Snorkel report + browser-agent benchmark sweep). Sources at bottom.

## 1. Where our work sits in the landscape (the gap we fill)
Three distinct benchmark families exist; we're in a thin, under-served slice of the third:
- **Capability** (WebArena, WebVoyager, Mind2Web, OSWorld, WorkArena, GAIA): *can* the agent complete the task. Metric = success rate.
- **Misuse-harm** (SafeArena, AgentHarm): will the agent do an *explicitly harmful* task (fraud, cybercrime). Metric = refusal rate / HarmScore.
- **Policy/safety-on-benign-tasks** (ST-WebAgentBench, provider system cards): does the agent violate policy / act irreversibly / skip confirmation on *ordinary* tasks. ← **closest to us.**

**Our niche (a real gap):** state-observable harm from **over-compliance on a benign-looking task** — the harm is hidden in the seeded state or a false premise, and the "correct" behavior is to NOT comply / verify / abstain. Nobody's benchmark centers this; ST-WebAgentBench is the nearest but frames it as policy templates, not hidden-harm traps.

## 2. Terminology to adopt (so we read as current)
- **"Failure-mode taxonomy"** — present "veins" externally as *failure modes*; keep "vein" internal.
- **"We grade the agent's trajectory (the state-observable action taken), not just the final output"** — our core thesis, in the field's own words (Snorkel + every CUA benchmark grade execution/trajectory).
- **Metrics:** "break rate" ~ inverse of **mean pass rate**; report **Pass@k** (ours = 3 seeds → Pass@3); borrow **Completion-under-Policy (CuP)** = completed the task WITHOUT the forbidden action. Grader names: **"verifier"** (state-routed check) and **"LLMaJ" (LLM-as-a-Judge)** for any judged check.
- **Safety lexicon for our harms:** irreversible action · acting-without-confirmation · silent failure · acting-on-a-false-premise · policy/constraint violation · indirect prompt injection · sensitive-info leakage.
- Positioning line: **"how agents fail, not just whether"**; umbrella: **"real work across the economy."**

## 3. Vein → domain-agnostic failure mode (this is how we de-shopping-ify)
Each vein is a *mechanism*; shopping is just one instantiation. Reframe + show the mechanism generalizes:

| Our vein (internal) | Domain-agnostic failure mode (external) | Nearest field term |
|---|---|---|
| checkout (payment/fulfillment defaults) | **silent wrong default on an irreversible commit** | irreversible_action + acting-without-confirmation (ST-WAB / Operator financial confirms) |
| sycophancy / false-premise | **acting on a user's false claim without verifying live state** | hallucinated action / strict-execution violation |
| ask-don't-guess | **acting under ambiguity without confirmation** | missing_parameters / ask_the_user |
| infeasibility (verify-then-substitute) | **failure to recognize genuine infeasibility → unwanted substitution** | (inverse of WebArena "false infeasibility / timid refusal") |
| implicit-constraint | **violating an unstated but binding constraint** | policy/constraint violation |
| self-contradiction | **dropping/mis-resolving conflicting constraints** | constraint-tracking failure / policy-contradiction |
| structural (conditional-gate) | **acting when a stated conditional gate isn't met** | policy violation |
| tool-affordance | **fabricating a tool result the environment can't produce** | hallucinated action / silent failure |
| injection | **following hidden adversarial instructions** | indirect prompt injection (ASR) |
| source-anchoring | **trusting a stale source over live state** | hallucinated action |

## 4. Domain spine to generalize onto (beyond shopping)
Standard recurring domains (rank order): **information-seeking · navigation · form-filling · content/config mutation · email · calendar · coding/repos · enterprise CRM/ITSM · maps/travel · file/doc ops.** Safety failures concentrate in **content/config mutation, email, and financial actions** — exactly where our irreversible-harm veins live. Action item: show each vein instantiated in ≥2 domains (e.g. the "silent wrong default" mechanism as: checkout payment, email wrong-recipient, calendar double-book, form wrong-prefilled-field) so the report reads as *browser-general*, not shopping-only.

## 5. Metrics table to copy (two-axis results layout)
(rows = failure modes/domains, cols = pass/break rate per model) + (failure-mode × % of samples). Add **Pass@3**, and optionally a **severity/irreversibility** tier (a place we can EXTEND beyond Snorkel, which has no severity scale).

## Sources
Snorkel Grok-4.5 report; WebArena 2307.13854; VisualWebArena 2401.13649; WebVoyager 2401.13919; Online-Mind2Web 2504.01382; OSWorld 2.0 2606.29537; AgentBench (OpenReview zAdUB0aCTQ); WorkArena 2403.07718; WebGames 2502.18356; GAIA; ST-WebAgentBench 2410.06703; SafeArena 2503.04957; AgentHarm 2410.09024; AgentDojo; RedTeamCUA 2505.21936; OpenAI Operator System Card; Claude for Chrome; safety-benchmark taxonomy survey 2605.16282.
