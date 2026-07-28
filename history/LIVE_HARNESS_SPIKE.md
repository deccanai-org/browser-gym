# Live-website harness — research spike (design only)

**Status: DESIGN ONLY. No live-site automation code ships in this build.**
This documents how a harness driving *real* websites (instead of our
simulated multi-app world) could work, what it would take to be safe, and
why the simulated gym stays the primary data source. It exists so the
team can weigh the option deliberately rather than discover the pitfalls in
production.

---

## Why even consider it

The simulated gym is correct-by-construction: we own the state, so the
verifier reads ground truth and the oracle proves every task is solvable.
But two questions only a live site can answer:

1. **Does a failure mode we harvested in simulation also occur on the real
   site it imitates?** If "agent loses the order id across the Mail→Shop
   tab switch" reproduces on a real storefront + a real webmail, the mode
   is provably not an artifact of our sim.
2. **Distribution realism.** Real DOMs are messier (ads, A/B variants,
   third-party widgets, latency). Some agent failures only appear there.

The spike's thesis: use live sites as a **validation / realism check** on
modes already crystallized in simulation — never as the primary harvest
surface.

---

## Architecture sketch

The existing `BrowserCtx` already speaks Playwright against an arbitrary
URL — `_abs()` just prepends a base. A live harness reuses it almost
unchanged; what changes is everything *around* trust:

```
LiveBrowserCtx(BrowserCtx)
  base_url            = https://<sandbox-or-staging-site>
  allowlist           = compiled set of (action, url-pattern) rules
  read_only_default   = True   # destructive actions require explicit opt-in
  account             = a DEDICATED throwaway account (never a real user)
  verifier            = LiveVerifier (DOM/visual/receipt-based, see below)
```

Episodes still produce the same `Trajectory` JSONL schema, so the failure
classifier + signature builder work unchanged.

---

## Safety guardrails (the non-negotiable part)

A browser agent on a live site can do real, irreversible harm. The
guardrails below are the price of admission. The cautionary tale the team
keeps citing — an unconstrained computer-use agent that "tidied" an inbox
by **deleting real Gmail** — is exactly what this section exists to
prevent.

1. **No production credentials, ever.** Only purpose-made sandbox / staging
   accounts (e.g. a retailer's developer sandbox, a dedicated test
   mailbox). Credentials live in a secrets manager, are injected at
   runtime, and are NEVER written to the repo, a trajectory, a screenshot,
   or a log. (We already treat API keys this way — same rule.)
2. **Action allowlist, default-deny.** The agent may only perform actions
   matching an explicit allowlist (navigate within the site, click, type
   into known fields, add-to-cart). Everything else is blocked at the
   harness layer before it reaches Playwright.
3. **No destructive operations.** Hard-blocked verbs: delete, cancel,
   send-to-a-real-recipient, submit-payment-with-real-money, change-account-
   settings, unsubscribe. Where a flow *needs* a terminal action (place an
   order), it runs only against a sandbox that charges nothing.
4. **Domain fence.** Navigation is restricted to an allowlisted set of
   hosts. A click that would leave the fence (an ad, an external link) is
   intercepted and dropped.
5. **Rate + budget limits.** Per-episode caps on actions, wall-clock, and
   spend; a global kill-switch. Human-in-the-loop confirmation for anything
   that crosses a money or data-deletion boundary.
6. **Full auditability.** Every action + screenshot is recorded
   (already true), so any incident is reconstructable.

If a flow cannot be made safe under these rules, it does not run live — it
stays in simulation.

---

## The verifier problem (and the answer)

In simulation the verifier reads server state directly (`probe.world`).
On a live site **you cannot read the server's database**. So a
`LiveVerifier` must judge the outcome from what's observable:

- **DOM / visual assertions** — the order-confirmation page shows an order
  number; the cart badge shows the expected count; a "Thank you" banner is
  present.
- **Receipts / side-effects in another surface** — a confirmation email
  actually arrives in the (sandbox) mailbox. This is the live analogue of
  our event-bus `delivered` flag: the cross-app chain is verified by the
  artifact it produces, not by reading state.
- **Self-consistency** — the order number on the confirmation page matches
  the one in the confirmation email matches the one on the tracking page.
  (This directly tests the M2 "carry the order id across apps" mode.)

A live verifier is necessarily *weaker* and noisier than the simulated one
(no ground truth, flaky DOMs). That is the core reason simulation stays
primary.

---

## Why simulated stays the primary surface

| | Simulated gym | Live site |
|---|---|---|
| Ground truth | Yes (own the state) | No (observe only) |
| Deterministic / resettable | Yes (seeded) | No |
| Oracle-provable tasks | Yes (1.0 gate) | No |
| Cost per episode | ~compute only | API + infra + risk |
| Safety blast radius | None | Real-world harm possible |
| Failure attribution | Clean (env-correctness gate) | Confounded by site noise |

The simulated environment is what makes a harvested failure mode
*sellable*: we can prove it is the agent's fault, reproduce it on demand,
and ship a covering dataset. Live runs can only ever *corroborate* a mode
already established in simulation.

---

## Recommended path (if pursued later)

1. Stand up ONE live validation target behind the guardrails above (a
   retailer sandbox + a dedicated test mailbox).
2. Port only the modes that already cluster significantly in simulation
   (start with M2's order-id-across-tabs mode).
3. Run a small K, with the `LiveVerifier` checking confirmation-page +
   email self-consistency.
4. Report: does the simulated mode reproduce live, at what rate, with what
   added noise?

Until that is justified, **simulation is the product** and live remains a
research option documented here.
