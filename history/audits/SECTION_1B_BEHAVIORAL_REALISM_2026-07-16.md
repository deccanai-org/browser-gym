# Section 1B behavioral realism — 2026-07-16

## Scope

Answers the five protocol questions from
`docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` §1B for each flagged mechanic.
For every mechanic, classification is explicit:

- **Realistic workflow simulation** — behavior a human could meet on a
  production-like commerce UI without gym-only quirks.
- **Controlled adversarial perturbation** — intentional asymmetry or omission
  engineered to probe agent failure modes; defensible for the benchmark claim
  only when disclosed as such.

No production code was changed for this analysis. Claims cite current handlers,
templates, and mutations.

---

## 1. Cancellation silently no-ops for shipped orders

**Code paths:** `server/mutations.py::cancel_order` (rejects
`shipped` / `out_for_delivery` / `delivered` with flash + `{ok:False}`; does
**not** log a failed cancel); `ui/pages/account_order_detail.html` (Initiate
return + tracking only — no cancel control); no FastAPI
`/api/orders/*/cancel` route (`server/main.py`). Tasks: M108, M211.

### Five questions

1. **Could this occur in a real product?**  
   Partially. Real retailers often refuse cancel once shipped and leave status
   unchanged. A completely missing cancel control for *all* statuses (including
   confirmed/unshipped) is less universal — many sites expose Cancel until
   ship. The shipped refusal itself is realistic; the total absence of a cancel
   surface is stronger.

2. **Is the information placement plausible?**  
   Order detail correctly shows status (`shipped` / `out_for_delivery`) and
   tracking. That placement is plausible. There is no cancel failure message in
   the UI because there is no cancel control to fail.

3. **Would a human reasonably encounter this ambiguity?**  
   A human told “cancel my shipped order” can see status/tracking and infer it
   is too late. Ambiguity for agents often comes from briefs that assert
   “hasn’t shipped” (false premise) plus no cancel button — the human would
   usually not invent a successful cancel.

4. **Is the correct action available through the interface?**  
   Yes for the intended safe behavior: inspect order status/tracking, do not
   claim cancellation, optionally initiate return once delivered, email the
   truth. No for “actually cancel a shipped order” — by design impossible via
   UI and rejected by mutation.

5. **Is the trap independent of implementation quirks unique to us?**  
   Mixed. Shipped-order non-cancellability is industry-standard. The
   combination of (a) no cancel button even for unshipped orders, (b) mutation
   that refuses without a failed-action log entry, and (c) tasks that reward
   false “I cancelled it” emails is a **controlled adversarial** package. The
   mutation is not a true silent no-op (`ok:False` + flash); the “silent”
   framing refers to unchanged order status and the lack of a browser path.

### Classification

**Controlled adversarial perturbation** (primary), built on a **realistic
workflow fragment** (shipped orders cannot be cancelled). Disclose: browser
agents have no cancel affordance at all; sold tasks test false confirmation
after inspecting a non-cancellable shipped order, not cancel UX fidelity.

---

## 2. `update_event` has no overlap guard

**Code paths:** `server/apps/calendar/mutations.py` — `create_event` rejects
overlapping slots and names the conflict; `update_event` mutates start/end/title
in place with **no** overlap check (explicit comment referencing M22 move-then-
delete sequences). UI: `ui/pages/calendar/edit_event.html` →
`POST /calendar/update`.

### Five questions

1. **Could this occur in a real product?**  
   Yes. Many calendar UIs warn on create/invite but allow drag-reschedule into
   overlap, or only soft-warn. Hard block on create + soft/no block on update
   is a known product pattern (asymmetric validation).

2. **Is the information placement plausible?**  
   Create surfaces “Slot already booked …” naming the conflicting event.
   Update offers no such feedback. That asymmetry is noticeable but not
   physically impossible — it looks like incomplete validation, not a hidden
   harness flag.

3. **Would a human reasonably encounter this ambiguity?**  
   A careful human moving an event into a taken slot might expect a warning;
   some would still proceed if the UI allows it. The ambiguity is moderate:
   double-booking via edit is discoverable after the fact on the day view.

4. **Is the correct action available through the interface?**  
   For tasks that require avoiding double-book: yes — choose a free window,
   delete conflicting events first, or leave the event alone. The interface
   does not force the bad overlap; it merely fails to prevent it on update.

5. **Is the trap independent of implementation quirks unique to us?**  
   Largely yes as a *class* (asymmetric create vs update validation). The
   intentional comment tying the gap to specific move-then-delete task
   sequences marks it as deliberate benchmark design, not an accidental bug.

### Classification

**Realistic workflow simulation** of asymmetric calendar validation, used as a
**controlled adversarial** lever for reschedule/double-book tasks. Disclose the
create/update asymmetry rather than claiming full calendar realism.

---

## 3. Subscription controls omit pause/skip

**Code paths:** `server/mutations.py` exposes `create_subscription` /
`cancel_subscription` only (no pause/skip); `ui/pages/account_subscriptions.html`
renders Cancel for active subs only; `POST /api/subscriptions/{id}/cancel` in
`server/main.py`. Product Subscribe & Save form creates; no pause/skip controls
on `ui/pages/product.html`.

### Five questions

1. **Could this occur in a real product?**  
   Yes. Some merchants offer cancel-only subscription management; pause/skip
   are common extras, not universal. A cancel-only surface is a credible
   minimal product.

2. **Is the information placement plausible?**  
   Status, cadence, deliveries remaining, and Cancel are clear. Omitting
   pause/skip without advertising those features is coherent (no false
   “Pause” button).

3. **Would a human reasonably encounter this ambiguity?**  
   Only if the brief asks to “pause” or “skip a delivery.” A human would see
   Cancel as the only control and either cancel, refuse, or ask. Agents that
   invent pause semantics or cancel when told to pause are the failure mode.

4. **Is the correct action available through the interface?**  
   When the correct policy is cancel (or leave active): yes. When the brief
   wants pause/skip specifically: no — those actions are unavailable; correct
   behavior is to disclose the limitation / ask, not fake a pause.

5. **Is the trap independent of implementation quirks unique to us?**  
   Yes as a limited feature set. Not a harness quirk — the UI and mutations
   agree. Adversarial value comes from prompts that imply richer subscription
   controls than exist.

### Classification

**Realistic workflow simulation** of a cancel-only subscription product.
Adversarial only when prompts imply pause/skip; disclose the limited control
set in the report.

---

## 4. Checkout hides payment-expiry info

**Code paths:** `ui/pages/checkout_payment.html` and
`ui/pages/account_payments.html` show `exp {{ pm.expires }}`;
`ui/pages/checkout_review.html` payment `<select>` shows **label only** (no
expiry); `server/mutations.py::place_order` accepts any saved `payment_id`
without expiry/decline checks.

### Five questions

1. **Could this occur in a real product?**  
   Partially. Review-step payment pickers often show nickname/last4 without
   repeating expiry; processors still decline expired cards at authorize.
   Hiding expiry on review while also never validating expiry at place is
   stronger than typical production.

2. **Is the information placement plausible?**  
   Expiry is visible one step earlier (payment page / account payments) and
   dropped on the final review select. That is a plausible UI simplification,
   but it concentrates the trap at the commit step.

3. **Would a human reasonably encounter this ambiguity?**  
   A human who saw expiry on the payment page may still miss it on review.
   Tasks that seed expired cards while review omits the date create more
   agent-facing ambiguity than everyday checkout.

4. **Is the correct action available through the interface?**  
   Inspecting `/account/payments` or `/checkout/payment` surfaces expiry.
   Switching to a non-expired saved method is available when one exists.
   Stopping checkout / telling the user the card is expired is available as
   communication. Authorizing an expired card “successfully” should not be
   treated as realistic payment behavior — the gym will still place the order.

5. **Is the trap independent of implementation quirks unique to us?**  
   The review-label omission is mild and real-world-ish. The missing
   place-order expiry gate is a **controlled adversarial / simplified
   commerce** choice unique to this gym’s payment model.

### Classification

**Controlled adversarial perturbation** layered on a **realistic review-UI
simplification**. Disclose: expiry is inspectable earlier, but checkout commit
does not decline expired cards.

---

## 5. Promo validity follows custom rules

**Code paths:** `server/mutations.py::apply_promo` / `_promo_discount_on_eligible`
— rejects unknown codes, `expired`, `min_purchase`, and category/product
eligibility; flashes concrete errors; ValueMart has a parallel coupon path
(`server/apps/market/mutations.py`). Review form:
`ui/pages/checkout_review.html` promo apply/remove. Fine print may appear when
a promo is applied (`description_fineprint`).

### Five questions

1. **Could this occur in a real product?**  
   Yes. Expired codes, minimum spend, and category/SKU restrictions are
   standard ecommerce promo engines.

2. **Is the information placement plausible?**  
   Mostly. Apply failure flashes name the reason (expired / min purchase /
   not found). Eligibility restrictions may be less obvious before apply;
   fine print appears after successful apply. That matches many real checkouts
   (learn by attempting).

3. **Would a human reasonably encounter this ambiguity?**  
   Yes — marketing emails often push expired or restricted codes. Humans
   routinely try a code, read the rejection, and fall back.

4. **Is the correct action available through the interface?**  
   Yes: apply, read the error or fine print, remove, try another code, or
   proceed without discount. Tasks that require discovering a valid inbox code
   after rejecting an expired decoy exercise this path.

5. **Is the trap independent of implementation quirks unique to us?**  
   Core rules are industry-standard. Task-local fortification (e.g. expired +
   extreme `min_purchase` double locks) is **controlled adversarial** tuning
   of otherwise realistic promo semantics — not a harness-only API.

### Classification

**Realistic workflow simulation** of promo engines, with **controlled
adversarial** task seeding (decoy expired codes, load-bearing restrictions).
Disclose custom task seeding; do not claim promo catalogs match any live
retailer.

---

## Summary table

| Mechanic | Primary class | One-line verdict |
|---|---|---|
| Shipped-order cancel “no-op” | Controlled adversarial (+ realistic refusal) | No UI cancel; mutation refuses shipped; tests false confirmation |
| `update_event` no overlap guard | Realistic asymmetry + adversarial use | Create blocks overlap; update does not |
| Subscription omit pause/skip | Realistic limited product | Cancel-only surface; pause/skip absent by design |
| Checkout hides payment expiry | Controlled adversarial | Review select omits expiry; place_order never declines |
| Promo custom rules | Realistic + adversarial seeding | Standard expired/min/eligibility rules; tasks fortify decoys |

## Protocol impact

Section 1B P1 (“Document each mechanic’s answers…”) is **CLOSED** by this
audit. No code/product changes recommended solely for checkbox completion;
disclosure of the controlled-adversarial mechanics is the honest report
stance.
