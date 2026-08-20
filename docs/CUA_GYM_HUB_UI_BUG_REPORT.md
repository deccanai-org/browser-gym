# CUA-Gym-Hub UI bug report

**Audience:** UI / product builders for the Xmazon, Xmail, Xbay, Xber, and Xoogle mocks.  
**Scope:** Issues that block correct data display or make controls look wired when they are not.  
**Status values:** **already fixed** · **not yet fixed** · **needs product decision**

Brand names below match what the mocks show in the browser chrome (not the folder names under `websites/`).

---

## Xmazon (Amazon-style store)

### 1. Gift message and ship-to on cart / checkout
- **Description:** Cart line gift message, gift wrap, ship-to address, and scheduled delivery now round-trip into the cart and checkout review. Ship-to is a real cart control; checkout address selection updates the default address.
- **Where:** Cart (`Cart.jsx`), Checkout review, cart state normalization.
- **Repro:** Open a session whose cart was seeded with a gift message and a non-default ship-to → Cart textarea and Ship-to select show those values.
- **Status:** **already fixed**

### 2. Express / Standard shipping not available as a product option
- **Description:** Some catalog items are defined with shipping-speed options (e.g. free Standard vs paid Express). The product detail and cart UIs do not show those options, and add-to-cart does not send a selected shipping variant. Users cannot switch off an Express line the way they can in a full catalog.
- **Where:** Product detail, Cart; product payload lacks a variants / shipping-speed control.
- **Repro:** Open a product that should offer Standard vs Express shipping → no shipping-speed selector; cart price ignores Express uplift.
- **Status:** **needs product decision** — may require new Product Detail / Cart UI (not only wiring an existing control).

### 3. Return request does not persist
- **Description:** “Return or Replace Item” opens a form and shows a success state, but submit only flips local UI state. No return is created in backend/session state.
- **Where:** Orders → Return modal (`Orders.jsx` submit handler).
- **Repro:** Your Orders → Return or Replace Item → choose reason → Submit → UI says submitted; reload / re-fetch orders → no return recorded.
- **Status:** **not yet fixed**

### 4. Subscriptions have no storefront surface
- **Description:** Subscription objects can exist in session state but there is no Xmazon page to view, pause, or cancel subscriptions.
- **Where:** Account / orders navigation — no subscriptions route or components.
- **Status:** **needs product decision** — add a subscriptions area, or formally mark out of scope for this mock.

---

## Xmail (Gmail-style)

### 1. Multi-message conversations split into single-message threads
- **Description:** Each message is given its own `threadId` (`thread_<messageId>`). Related replies (same subject, conversational chain) appear as separate inbox rows. Opening one shows only that message, not the full conversation. **Confirmed via live reproduction (M338)**, not only code inspection.
- **Where:** Inbox list + thread view (`EmailList` / `ThreadView`); seed → mail state transform.
- **Repro:** Load M338 (or any mailbox with several “Re: dinner tonight” messages from different people) → inbox shows one row per message; open any row → only that sender’s body appears (other people in the conversation are missing from the thread).
- **Status:** **not yet fixed**

### 2. Archive, delete, and star are local-only
- **Description:** Archive / delete / star update the on-screen mailbox, but do not call the shared mail backend actions (unlike Send and Open, which are wired).
- **Where:** Inbox toolbar / thread actions in `StoreContext`.
- **Repro:** Star or archive a message → UI updates; refresh from authoritative session state (or open in another tab on the same sid without localStorage) → change may not persist.
- **Status:** **not yet fixed**

### 3. Starred / Important always empty after seed
- **Description:** Seeded mail forces `starred: false`, `important: false`, empty labels, and category `primary`. Starred and Important folders therefore never show seeded content.
- **Where:** Mail seed transform → folder filters.
- **Status:** **not yet fixed** (or **needs product decision** if those folders are demo-only).

### 4. Inbox row open/select is unreliable for pixel / SoM agents
- **Description:** Opening a clearly visible inbox message often fails under mark-id click + keyboard (Enter / `o` / Tab / `j`). Agents loop on search → select checkbox → More options → wrong thread (e.g. Alex) without durable `read=true` on the target message. Burns an entire 50-step episode before any shop action.
- **Where:** Inbox list / thread open path (`EmailList` row click target vs checkbox / SoM marks); bridged Gmail mock.
- **Repro:** Bridged `lh_004/mom_watch_email_mismatch` on isolated Amazon+Gmail stack (no port contention) → Sol (`openai_pixel[gpt-5.6-sol]`) seed 0 spends steps 0–49 on Mail open/select; harness `read_mom_email` never fires; cart unchanged. Evidence: `trajectories/lh_004_isolated_3seed/lh_004_mom_watch_email_mismatch__0__2fe6acc6.jsonl`, prior contended pass `LH004_BRIDGED_E2E.md`.
- **Root cause:** Same class as Xber §6 — openable inbox rows were plain `<div onClick>` with no `role` / `data-test-id="mail-item-<id>"`, so SoM only marked nested Select / Star / Important buttons. Keyboard `j`/`o`/`Enter` also used an unfiltered `visibleEmails` list (ignored search + inbox category), so focus opened the wrong thread (e.g. Alex).
- **Status:** **already fixed** — `gmail_mock` `EmailList` rows are `role="button"` with `data-test-id="mail-item-<id>"` + aria-label; Select/Star stopPropagation; keyboard focus list mirrors EmailList search/category. Rebuild `dist` after source change. Smoke: `trajectories/lh_004_shopmail_fix_smoke/`. Sol re-run: `docs/history/audits/LH004_SHOPMAIL_FIX_RERUN.md`.

---

## Xbay (eBay-style)

### 1. Coupon “applied” banner does not change the total
- **Description:** Cart has Apply coupon / Remove coupon. After applying a valid code (e.g. `VALUE10`), the green “Coupon … applied” banner appears, but Order Summary **Total stays at the undiscounted subtotal** — the banner is not tied to a discounted price.
- **Where:** Cart page (`Cart.jsx` summary).
- **Repro:** Add a $109.99 item → Cart → enter `VALUE10` → Apply → banner shows applied; Total still $109.99 (live-confirmed on a seeded keyboard cart).
- **Status:** **not yet fixed** — bridged 2026-07-30: engine `market.apply_coupon` sets `applied_coupon`, but re-project omits `state.coupon` so the banner does not stick; Total still list price (`BRIDGED_INTERACTION_INTEGRITY_GMAIL_EBAY_UBER.md`).

### 2. Seeded / catalog coupons not shown as selectable offers
- **Description:** Session state can include coupon definitions (and optionally an already-applied code), but the cart only offers a free-text field. Available codes are not listed as selectable offers, and an already-applied coupon on the cart is not projected into the banner unless the client sets `state.coupon`.
- **Where:** Cart coupon panel; market → Xbay state transform (`coupon` vs hidden `_gym_coupons`).
- **Repro:** Seed a cart with a known coupon catalog → Cart shows input only, no offer list; applied flag from seed does not appear until the user types a code.
- **Status:** **needs product decision** — list available coupons vs keep code-entry only; also wire seed `applied_coupon` → banner + discounted total.

### 3. Major browse surfaces are consistent
- **Description:** Home, Search, Dashboard (“My Xbay”), Sell, and Cart all share the same listings/cart state; Buy It Now confirm is a modal on the listing, not a second empty page.
- **Status:** **already fixed** / no bug (baseline OK for listing ↔ cart).

### 4. Active Buy-It-Now listing detail shows “ended” (masks purchase)
- **Description:** Search/home cards show active fixed-price listings (e.g. Plain Welcome Sign $9, `eb_lh001_plain_sign`) with **Buy It Now**, but opening the listing detail replaces purchase controls with **“This listing has ended.”** Agents (Sol + GPT-5.5 on lh_001) correctly open the cheap Plain path, then abandon it as unpurchasable and often chase Deluxe. **Distinct from §1–§2** (coupon UI) and from Xbay §3 (browse consistency). Same class as Xber §6: UI chrome masking a correct, wired purchase path.
- **Where:** `ebay_mock` `ProductDetails.jsx` (`isEnded = status !== 'active' || endTime < Date.now()`); bridged projection `tools/seed_to_cuagym.py` `transform_market` previously stamped every listing `endTime` to sim-world **2026-05-28**, which is already past evaluation wall-clock (2026-07+). Search only filters `status === 'active'`, so cards stay visible while detail hides Buy It Now / Add to cart.
- **Repro:** Bridged lh_001 → eBay search “Welcome Sign” → open Plain $9 → detail says listing ended; engine `market.products.eb_lh001_plain_sign.in_stock=true` and listing `status=active`. Evidence: `docs/history/audits/LH001_GPT55_3SEED.md`, `LH001_SOL_RERUN_AFTER_GYMEATS_FIX.md`, trajs under `trajectories/lh_001_gpt55_3seed/` / `lh_001_sol_rerun_gymeats_fix/`.
- **Status:** **already fixed** — fixed-price / Buy It Now listings use `status` as purchasability source of truth (wall-clock `endTime` only ends auctions); SoM `data-test-id`s on Buy It Now / Add to cart / Confirm Purchase; bridge `transform_market` endTime = now+30d. Rebuild `ebay_mock` `dist` after source change.

---

## Xber (Uber Eats-style)

### 1. Seeded cart lines lack stable line ids
- **Description:** Cart items added by the user get an `id`. Items loaded from seed often have only `menuItemId` / name / qty — no `id` or `cartItemId`. Quantity buttons key off `item.id`, so seeded multi-item carts mis-update (every line with a missing id can change together).
- **Where:** Cart panel (`CartPanel.jsx` + `AppContext`); food → Xber seed transform.
- **Repro:** Seed a cart with two dishes → open Cart → press + on one line → quantities for multiple lines can jump together; remove may no-op or clear the wrong set.
- **Status:** **not yet fixed**

### 2. Cart quantity / remove do not call the food backend
- **Description:** Plus/minus and remove update React state only. They are not wired to shared food cart mutations (add-to-cart and checkout are wired).
- **Where:** `AppContext.removeFromCart` / `updateCartItemQuantity`.
- **Status:** **not yet fixed**

### 3. Orders list route shows “Order not found”
- **Description:** Navigating to `/orders` (Account → Orders) renders the tracking page without an order id, which displays **Order not found** (or equivalent empty/error copy). A separate orders-list page exists in the codebase but is not mounted on that route.
- **Where:** `App.jsx` routes; `OrderTracking.jsx` vs unused `Orders.jsx`.
- **Repro:** Account → Orders, or open `/orders` → “Order not found” even when orders exist in session state. Direct `/orders/<id>` can still open a detail view.
- **Status:** **not yet fixed**

### 4. Order tracking missing delivery address and courier
- **Description:** Seeded (and transformed) orders omit `deliveryAddress` and `deliveryPerson`. Tracking therefore skips the driver card and cannot show a real delivery label (active map copy falls back to “delivery address”).
- **Where:** Order tracking detail; food → Xber order transform / seed shape.
- **Repro:** Open `/orders/<seededOrderId>` for a delivered order → restaurant and line items show; no courier block; no concrete address label.
- **Status:** **not yet fixed**

### 5. Seeded order receipt shows `$NaN` for Service Fee / Tax
- **Description:** On seeded order detail, **Service Fee** and **Tax** render as `$NaN` when those fields were not populated on the order object.
- **Where:** Order tracking / receipt section.
- **Repro:** Open a seeded delivered order → Service Fee `$NaN`, Tax `$NaN`, while Subtotal / Delivery Fee / Total may still show numbers.
- **Status:** **not yet fixed**

### 6. Menu add never lands (empty cart after card / “+” clicks)
- **Description:** On an empty (agent-built) cart, clicking a store menu card — or the visible circular **+** on the dish image — does not put a line in the cart. The **+** was a decorative CSS `::after` (not a control), and the item modal used Tailwind utility classes in a plain-CSS mock, so the modal never appeared as an overlay after card click. Agents (and humans using the marked UI) stay stuck with `food.cart.items=[]`. **Distinct from §1–§2** (those assume a seeded cart and leave add-to-cart “wired”).
- **Where:** `StorePage.jsx` menu cards; `ItemModal.jsx` (must use `ItemModal.css`); bridged `AppContext.addToCart` → `food.add_to_cart`.
- **Repro:** Bridged lh_001 / Bean There Cafe → click Vegetarian Welcome Lunch Box card or its **+** → open Cart → “Your cart is empty.” (Sol traj `9dbfa63f` steps 40–49). Evidence: `docs/history/audits/LH001_GYMEATS_ADD_VS_KNOWN_BUGS.md`.
- **Status:** **already fixed** — real SoM-markable quick-add `+` button; ItemModal rewritten onto plain CSS; `data-test-id="btn-add-to-cart"` on modal submit.

---

## Xoogle (Google Calendar-style)

### 1. Day view does not show events that appear in Week / Month
- **Description:** Seeded events appear on Week (and Month) for the intended calendar day, but Day view is empty or pinned to the wrong local calendar day. Root cause: `currentDate` / event starts are encoded as UTC midnight / wall-clock-as-Zulu, then compared with local `isSameDay`.
- **Where:** Week/Day grid (`WeekView.jsx`); calendar seed timestamps.
- **Repro:** Load a May 21 week with “Gym session” → switch to Day → event missing / view on wrong date (e.g. local TZ behind UTC).
- **Status:** **root cause not yet fixed** — **entry path mitigated** (2026-08-02): Day removed from view menu + Settings default-view options; `SET_VIEW` / `LOAD_STATE` / `initializeData` coerce `day` → `week`. Bridged default remains `view: "week"`. Evidence: `docs/history/audits/CAL001_DAY_VIEW_ROUTING.md` (cal_001 Sol entered Day via Header Week→Day and burned the step cap).

### 2. Single click on the day/week time grid does not open create
- **Description:** Comment in the grid handler says a simple click should open quick-create; the mouseup path returns without calling `onDateClick`. Drag-to-create, sidebar **Create**, and month-cell click still work.
- **Where:** `WeekView.jsx` `handleGridMouseDown` → `onMouseUp`.
- **Repro:** In Week or Day, click an empty time slot (no drag) → no create modal.
- **Status:** **not yet fixed**

### 3. “Today” navigation lands on wall-clock date (not seeded gym today)
- **Description:** Header **Today** (and “is today” blue highlights) used `new Date()` / `Date.now()`, so under evaluation wall-clock (e.g. Aug 2026) the view jumped to a blank real-world week/month while seeded events remain on the frozen gym day (**2026-05-21**). Agents (cal_002 Sol cap-80) clicked Today → saw empty August → falsely concluded the Client lunch hold was already gone and `finish`ed in 1 step.
- **Where:** `google_calendar_mock` `Header.jsx` `handleToday`; Week/Month/Sidebar/Agenda `isSameDay(..., new Date())`; bridge `transform_calendar` now stamps `referenceToday`.
- **Repro:** Bridged cal_002 (hold on Thu May 21) → open Calendar → click **Today** → before fix: August 2026 blank week; after fix: May 2026 week with Client lunch visible.
- **Root cause:** Same class as Xoogle §1 / Xbay wall-clock `endTime` — UI clock not bound to gym seeded today (`_gym_meta.today` / `referenceToday`).
- **Status:** **already fixed** — `referenceToday` locked from bridge/`_gym_meta.today`; Today button + isToday highlights use `getReferenceTodayISO` / `getReferenceTodayDate`. Rebuild `google_calendar_mock` `dist` after source change. Evidence: `docs/history/audits/CAL002_TODAY_SEED_DATE_FIX.md`.

---

## Quick status matrix

| App | Issue | Status |
|---|---|---|
| Xmazon | Gift / ship-to on cart & checkout | already fixed |
| Xmazon | Express / Standard shipping options | needs product decision |
| Xmazon | Return submit local-only | not yet fixed |
| Xmazon | Subscriptions UI missing | needs product decision |
| Xmail | Flattened conversation threads | not yet fixed |
| Xmail | Inbox row open/select unreliable for SoM agents | already fixed |
| Xmail | Archive / delete / star local-only | not yet fixed |
| Xmail | Starred / Important empty after seed | not yet fixed |
| Xbay | Coupon banner without discounted total | not yet fixed (bridged: engine applies; banner cleared on re-project) |
| Xbay | Coupon catalog / seeded applied state | needs product decision |
| Xbay | Active BIN detail shows “ended” (masks buy) | already fixed |
| Xber | Seeded cart missing line ids | not yet fixed |
| Xber | Qty/remove not backend-wired | not yet fixed |
| Xber | `/orders` list → “Order not found” | not yet fixed |
| Xber | Missing delivery address / courier on orders | not yet fixed |
| Xber | Service Fee / Tax `$NaN` on seeded orders | not yet fixed |
| Xber | Menu add never lands (modal/Tailwind + decorative +) | already fixed |
| Xoogle | Day view empty / TZ mismatch | root cause open; entry path mitigated |
| Xoogle | Click-to-create on grid broken | not yet fixed |
| Xoogle | Today → wall-clock date (not seeded) | already fixed |
