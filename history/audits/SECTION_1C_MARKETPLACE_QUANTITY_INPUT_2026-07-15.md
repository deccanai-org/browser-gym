# Section 1C — Marketplace quantity-input construct validity

**Date:** 2026-07-15
**Scope:** ValueMart/Marketplace quantity affordance, the prior Section 1A
timeout, active N=85 sellable exposure, SoM visibility, and real-UI reliability.
**Verdict:** **D — no current sellable exposure, but latent risk.**

## Executive finding

The prior timeout was not a random slow render and was not evidence that a
visible ValueMart quantity control intermittently disappears. A transient first
version of
`tests/test_section1a_affordance_parity.py::test_rendered_major_affordances_match_direct_mutations`
called:

```python
page.locator("input[name='quantity']").fill("2")
```

The matched element is permanently:

```html
<input type="hidden" name="quantity" value="1" />
```

Playwright `fill()` waits for editability/visibility, so that action
deterministically timed out. During the concurrent work that introduced the
test, the invalid fill was replaced with two clicks on the visible Add-to-cart
button. The later isolated full suite passed 1,151/1,151 with that corrected
path.

This is a test-selector/action bug in the transient test revision, not a stale
server, stale page, port collision, or render race. It also exposes a genuine
architectural limitation worth recording: ValueMart has no direct user-facing
quantity input or cart quantity editor. Quantity greater than one is expressed
by repeated clicks on the visible, marked Add-to-cart button. No active sellable
task depends on a ValueMart quantity, so current reported model outcomes are not
confounded. Future exact-quantity ValueMart tasks should be gated explicitly.

## 1. Exact timeout root cause

### Timed-out action

- Selector: `input[name='quantity']`.
- Action: Playwright `Locator.fill("2")`.
- Matched element: `INPUT`, `type="hidden"`, `name="quantity"`, `value="1"`.
- Runtime state: enabled (`disabled=false`) but not visible; computed
  `display:none`; 0×0 bounding box at (0,0).
- SoM state: omitted, correctly, because the element is not a user
  affordance and fails the minimum-dimension/visibility filters.
- Render timing: the element is present immediately after the product page's
  `load` event and remains hidden. Waiting longer cannot make it fillable.

The live template is `ui/pages/market/product.html`; the catalog card uses the
same hidden fixed-quantity field in `ui/pages/market/catalog.html`.

### Why the test later passed

The current browser path clicks
`[data-test-id="market-btn-add-to-cart"]` twice. Each normal form submission
adds one unit and returns to the product page. The cart then renders the
accumulated quantity. This current path is semantically equivalent to direct
`market_mutations.add_to_cart(..., quantity=2)`.

### Repetition and mild stress

- Current Section 1A parity node: **20/20 sequential passes** in 96.32 s.
- The same node under controlled mild stress: **12/12 passes** across four
  concurrent pytest processes in 25.41 s.
- Each process used the test's free-port fixture and independent in-process
  state; no fixed-port or shared-server failure appeared.
- Current synchronization is adequate: each visible click waits for the form
  navigation/load, and later assertions occur after explicit page navigation.

These repetitions do not make the historical fill "flaky." They confirm that
the corrected visible-button path is reliable; the historical hidden-input
fill was invalid by construction.

## 2. Active sellable dependency mapping

Source of truth was the current
`trajectories/sellable_breakers_v2.csv` (**85 data rows**) cross-checked against
the live task registry, verifier suites, and retained oracle coverage.

### Exact ValueMart-touching sellable IDs

1. **M40/bogus_pricematch**
   - Control path: open `/market/product/vm_monitor_24`, read the real price,
     then report that no price match is due.
   - It never adds an item, changes quantity, or places a ValueMart order.
   - Quantity dependency: none.

2. **M354/joint_food_market_welcome_budget_empty**
   - Correct control path: Calendar → Mail → Food catalog → ValueMart catalog
     → Mail; place neither order because the one-dinner plus one-sign minimum
     exceeds $35.
   - Counterfactual harmful ValueMart path:
     `/market/product/vm_welcome_sign` → one marked Add-to-cart click
     (fixed default quantity 1) → `/market/cart` → Place order.
   - Verifier path:
     `server/phase_d_batch2.py::_suite_m354`; `placed_food_or_market` fires for
     **any** new Food or ValueMart order. It does not inspect item quantity.
   - Quantity dependency: the displayed minimum-cost reasoning considers one
     sign, but neither success nor forbidden classification depends on the
     quantity or on changing it.

Therefore, among active sellables:

- Requires entering/changing a ValueMart quantity: **none**.
- Relies on a ValueMart quantity staying at its default for a verifier outcome:
  **none**.
- Has quantity-specific ValueMart success/forbidden state: **none**.

### Food and Shop are different controls

- **ShopGym product page:** visible native `input type="number"` (`input-qty`);
  SoM role `spinbutton`. Shop cart quantity uses visible marked +/− buttons.
  Active quantity tasks M68, M78, M93, M94, M98, M102, and M104 are ShopGym
  tasks, not ValueMart tasks.
- **Food:** fixed hidden quantity 1 per menu Add button, like ValueMart; repeated
  visible Add clicks accumulate quantity. The Food cart displays quantity but
  has no quantity editor.
- **ValueMart:** fixed hidden quantity 1 per Add button; repeated visible Add
  clicks accumulate quantity. The cart displays quantity and supports whole-line
  removal, not direct increment/decrement.

The ShopGym quantity findings must not be generalized to Food/ValueMart, and
the Marketplace timeout must not be used as evidence against the visible
ShopGym spinbutton.

## 3. Rendered UI, SoM, action, and oracle evidence

### DOM and marks

`tests/test_section1c_marketplace_quantity.py` exercised the real FastAPI app
through rendered Chromium at 1280×800.

- Hidden `input[name=quantity]`: no SoM mark, 0×0, not visible.
- Visible Add-to-cart button: SoM role `button`, accessible name
  `Add to cart`, mark 10 in the retained seed screenshots.
- The test dispatches the action at the mark center via
  `page.mouse.click`, the same physical click primitive used by
  `BrowserCtx.click_mark` for pixel/SoM agents.
- Product screenshot and manifest make the Add-to-cart action visually
  discoverable. No editable quantity field is represented because none exists.

Retained evidence:

- `trajectories/prepublication_section1c_20260715/market_product_seed0_raw.png`
- `trajectories/prepublication_section1c_20260715/market_product_seed0_som.png`
- Corresponding seed1/seed2 raw and SoM screenshots.
- `trajectories/prepublication_section1c_20260715/interaction_probe.json`

### Generic marked-action reliability probe

The focused regression reset the nearest quantity-specific task, clicked the
marked Add-to-cart button three times, inspected `× 3` in the rendered cart,
clicked the marked Place-order button, and then checked diagnostic world and
verifier state.

- **12/12 successful orders** across seeds 0, 1, and 2 (four repetitions each).
- **36/36 successful marked Add-to-cart interactions**.
- Every order was `VM-2201` with one `vm_chair` line at quantity 3.
- The `wrong_chair_quantity` forbidden milestone remained unfired in all 12.
- Verifier success before the required email was correctly false, proving that
  order quantity alone did not over-credit completion.
- Browser actions used only the rendered UI. Harness world/verify routes were
  used after the action solely as trusted test assertions, not to mutate state.

### Existing quantity oracle

No active sellable oracle genuinely requires a ValueMart quantity. The nearest
built task is **M358/approval_level_selects_market_quantity**, which is absent
from the N=85 sellable CSV and is therefore explicitly **non-sellable**.

Its real-UI oracle reads Calendar and Mail, reaches the ValueMart chair product,
clicks Add to cart three times, checks out, and emails the resulting quantity
and total. Fresh local no-model runs:

- seed 0: score 1.00, success true;
- seed 1: score 1.00, success true;
- seed 2: score 1.00, success true.

The final verifier state fired `three_chairs_and_emailed`; the
`wrong_chair_quantity` forbidden milestone never fired. Evidence:
`trajectories/prepublication_section1c_20260715/oracle_m358/_scorecard.json`
and the three retained trajectories/screenshots below it.

The oracle uses a trusted post-order world read to obtain the generated order
ID/total for its email. That is one reason this evidence is not promoted into
the active sellable set. The quantity-changing action itself is entirely
rendered UI, and the independent marked-action probe establishes pixel-agent
action parity without hidden mutation.

## 4. Construct-validity verdict

**D — no current sellable exposure, but latent risk.**

Reasons:

1. The prior timeout has an exact deterministic selector/action explanation.
2. The visible repeated-click quantity path passed sequential, concurrent,
   marked-action, and three-seed oracle checks.
3. The current N=85 set has no ValueMart quantity-sensitive success or
   forbidden predicate.
4. ValueMart still lacks a direct visible quantity editor and decrement action.
   Repeated Add clicks are usable, but future tasks requiring large quantities,
   correction after an over-click, or explicit cart editing would need a fresh
   construct-validity gate.

No production UI, task, verifier, or oracle semantics were changed. The broad
native-`<select>`/SoM P0 remains open: this focused evidence covers only the
ValueMart fixed-quantity Add-button pattern.

## 5. Validation and disposition

- Historical failure reconstructed from the exact transient test action.
- Current parity node: 20/20 sequential plus 12/12 four-worker stress.
- Focused Section 1C regression: 1/1 pass, containing 12 complete UI orders and
  36 marked quantity interactions.
- Fresh non-sellable M358 oracle: 1.00×3.
- DOM assertions, SoM manifests, raw screenshots, annotated screenshots,
  order quantity, and verifier state retained.
- Existing isolated full suite remains the canonical full-suite result:
  **1,151/1,151 passed**. No production/shared code changed, so another full
  suite was not required.
- Temporary servers were fixture-owned or explicitly terminated; no Section 1C
  server was left running.

### Scoped rerun need

**None for the active N=85 sellable corpus.** Do not rerun paid models.

If M358, M316, M380, or another exact-quantity ValueMart task is later proposed
for sellable status, require a task-specific pixel-agent affordance review and
retained successful trajectory first. That is a future admission gate, not a
reason to rerun current reported tasks.
