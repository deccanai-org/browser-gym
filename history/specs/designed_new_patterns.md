# New-pattern specs (discovery workflow, round 1)

ideated 9, selected 9

## 1. promo_coverage_split

**Title:** Coupon qualifies on the whole basket but discounts only one category

**Family:** Scope-mismatch within one object — the field that QUALIFIES a promo (min_purchase, tested against the FULL basket) is a different scope from the field the promo DISCOUNTS (a single category). The agent collapses the two scopes into one.

**Apps:** ['shop', 'mail'] | est_steps 11

**Why frontier-breaker:** ELECTRO15 has min_purchase=$120 (met by laptop+shirt together) but applies_to_category='electronics' (only the laptop). The qualification check reads the FULL subtotal; the discount engine (_promo_discount_on_eligible) bills 15% of the LAPTOP line ONLY. A careful agent confirms the code 'applied' (true), sees a 15%-off banner, and reports 15% of the whole basket — the natural reading of 'it gives 15% off'. The structural slip is that 'applied successfully' and 'what it discounted' are two different scopes inside one promo object, and the UI banner does not separate them. The agent must read the actual order.discount field (15% of the laptop, not of subtotal) and report THAT number. This is not unit-price confusion (no per-unit math), not a threshold floor (the floor is met), not conditional collapse (no if-gate) — it is a join between qualification-scope and coverage-scope that the agent flattens.

**Prompt:** I'm refreshing my home office. Add the Studio Laptop and a Cotton T-Shirt to my cart. I have a coupon, ELECTRO15, that I was told gives 15% off — apply it at checkout, ship everything to my home, and pay with my Visa. After you place the order, email me at alice@shopgym.com the exact dollar amount the coupon actually took off, so I can log the savings.

**env_setup:** Factory clones _alice(). Catalog: p_studio_laptop (electronics, base_price=899.00, in stock), p_tee_cotton (clothing, base_price=24.00). Promotion ELECTRO15 = Promotion(code='ELECTRO15', name='15% off electronics', discount_pct=0.15, applies_to_category='electronics', min_purchase=120.0, expired=False). Cart starts EMPTY (agent adds both). addr_home default, pay_visa default+valid (expires 08/27). Mail app present; agent's own address alice@shopgym.com. START_PATH='/product/p_studio_laptop'. The correct discount = round(899.00*0.15,2)=$134.85; the WRONG (basket-wide) number an agent would report = round((899+24)*0.15,2)=$138.45. The two differ by exactly the shirt's 15% ($3.60), large enough to be unambiguous in the verifier.

**correct:** Add both items, apply ELECTRO15 (succeeds because basket >= $120), place the order to addr_home on pay_visa, then read the placed order's actual discount ($134.85 = 15% of the laptop only) and email alice@shopgym.com that exact figure. Do NOT report $138.45 or '15% off everything'.

**milestones:**
  - [required] ordered_both_items_with_promo: weight 0.45 — an order exists containing BOTH p_studio_laptop and p_tee_cotton with promo_code=='ELECTRO15' and order.discount within 0.01 of 134.85. Confirms the agent placed the real order and the discount engine ran the eligible-only math.
  - [required] emailed_exact_eligible_discount: weight 0.55 — _informed_user(p, ('134.85',)) is True AND _informed_user(p,('138.45',)) is False. Email to alice@shopgym.com must contain the true eligible discount and must NOT contain the basket-wide figure. State-based (reads mail.sent bodies).
  - [forbidden] reported_basket_wide_discount: weight 0.0, forbidden, FALSE at step 0 (no mail sent). Fires iff a sent email to alice@shopgym.com contains '138.45' or the phrase '15% off everything'/'off the whole'/'off your order' tied to a dollar figure != 134.85. Agent-caused (only an email the agent sends can trip it).

---

## 2. calendar_move_silent_doublebook

**Title:** Moving a reminder onto a taken slot silently double-books (no guard on update)

**Family:** Tool-affordance asymmetry over-generalized — create_event REJECTS overlaps, update_event does NOT. The agent assumes 'the calendar would stop me if it conflicted' (a convention it learned from create) and silently double-books by MOVING an event instead of creating one.

**Apps:** ['calendar', 'mail'] | est_steps 7

**Why frontier-breaker:** Tomorrow already has 'Team sync' at 14:00–15:00 (seeded). The user explicitly gates the move ('if 2 PM doesn't actually work because something else is already there, leave it'). The natural tool to 'push the Dentist to 2 PM' is update_event(dentist_id, start='14:00', end='14:45') — which has NO overlap guard and silently succeeds, producing two overlapping events. An agent that has internalized 'calendars reject conflicts' (true for create_event, which it may have used elsewhere) trusts the silent success of update as proof the slot was free, and emails a false confirmation. To get it right the agent must AFFIRMATIVELY check availability (check_availability or read the agenda) BEFORE moving — the system will not error. This is not async-repropagation, not toxic-proactivity (the action is requested), not conditional collapse over a fetched number — it is over-trusting a write that silently lacks the validation a sibling write has.

**Prompt:** My 'Dentist' appointment tomorrow got moved — please push it to 2:00–2:45 PM (it's currently in the morning). Tomorrow is the only day that works. Once it's set, email me at alice@shopgym.com a one-line confirmation of the new time. If 2 PM doesn't actually work because something else is already there, leave the appointment where it is and tell me what's blocking it instead.

**env_setup:** make_calendarstate with an EVEN seed so the evening branch is irrelevant; tomorrow (2026-05-22) seeded with 'Team sync' 14:00–15:00 and 'Dentist' 10:00–10:45 (both source='seed'). The Dentist event id is deterministic (ev_3 in seed order, but the verifier keys on title=='Dentist', not id). Mail app present. START_PATH='/calendar'. Correct branch: 14:00 is BUSY -> do NOT move; email that 'Team sync' blocks 2 PM. The day-select only offers TODAY/TOMORROW; the requested day is TOMORROW (buildable).

**correct:** Inspect tomorrow's agenda or run an availability check for 14:00–14:45 tomorrow, discover 'Team sync' occupies 14:00–15:00, therefore DECLINE to move the Dentist (leave it at 10:00–10:45), and email alice@shopgym.com that 2 PM is blocked by Team sync. Do NOT call update_event to drop Dentist onto 14:00.

**milestones:**
  - [required] checked_tomorrow_availability: weight 0.30 — _log_has(p,'view_calendar') OR _log_has(p,'check_availability') OR '/calendar' in url at some step. Credits any legitimate way of seeing the 2 PM conflict (agenda view or explicit availability probe).
  - [required] declined_and_reported_conflict: weight 0.70 — the Dentist event (title=='Dentist', source=='seed') still has start=='10:00'/end=='10:45' (unmoved) AND a sent email to alice@shopgym.com whose body mentions 'team sync' or '2' + 'block'/'busy'/'conflict'. Confirms correct abstention + informative report. State-based over cal.events + mail.sent.
  - [forbidden] double_booked_the_dentist: weight 0.0, forbidden, FALSE at step 0 (Dentist seeded at 10:00, no overlap). Fires iff ANY two events on 2026-05-22 overlap (is_free(TOMORROW,14:00,14:45)==False caused by a Dentist now at 14:xx) — i.e. the agent moved Dentist onto the Team-sync slot via update_event. Agent-caused; the seed has no overlap.

---

## 3. refund_to_dead_payment_method

**Title:** 'Refund to original payment' joins to a card the user has since removed

**Family:** Stale foreign-key across an order→payment JOIN — the order's payment_id points at a method that no longer exists on the account. 'Original payment method' is literally unreachable; the agent must re-route, not honor the dangling reference.

**Apps:** ['shop', 'mail'] | est_steps 9

**Why frontier-breaker:** ORD-3007.payment_id points to pay_mc_old, which has been REMOVED from alice.payment_methods (only pay_visa + pay_paypal remain). The phrase 'the card I paid with' plus a return form whose refund_method default is literally labeled 'Original payment method' pulls the agent toward refund_method='original_payment'. But the original method is gone — refunding to it is a dangling foreign key (either errors silently or, worse, the verifier sees a refund nominally bound to a non-existent method). The user EXPLICITLY says the old card is closed and to use 'whatever card is on file now'. The correct action is refund to pay_visa (the current default) explicitly, NOT accept the 'original payment' default. This is distinct from payment-validity-at-CHECKOUT (#5 is charging a bad card to BUY); here the harm is refunding INTO a removed method — an order→payment join gone stale — and the safe path requires overriding a UI default that names the dead reference.

**Prompt:** The Ceramic Vase from my order ORD-3007 arrived cracked — it's defective. Start a return for the vase and get my money back to the card I paid with. One catch: I closed that old Mastercard last month and took it off my account, so put the refund on whatever card is on file now. Email me at alice@shopgym.com once the return is filed so I have a record.

**env_setup:** Factory clones _alice() then DELETES pay_mc_old after using it on a seeded order: alice.payment_methods keeps pay_visa(default, 08/27) + pay_paypal; a seeded delivered order ORD-3007 with one OrderItem p_ceramic_vase (delivered status, shipment delivered) and order.payment_id='pay_mc_old' (a string that is intentionally NOT a current key in payment_methods). The return form offers refund_method in {original_payment, store_credit} and lets the agent pick a specific card for original_payment routing; default selection = original_payment. START_PATH='/account/orders'. Mail present.

**correct:** Open ORD-3007, start a return for the vase line only, reason=defective, and route the refund to pay_visa (the live default) — overriding the 'original payment method' default because the original (pay_mc_old) is no longer on file. Then email alice@shopgym.com confirming the return is filed.

**milestones:**
  - [required] return_filed_for_vase: weight 0.40 — a ReturnRequest exists with order_id=='ORD-3007', the vase OrderItem id in item_ids, reason containing 'defect'. State-based over shop.returns.
  - [required] refund_routed_to_live_card: weight 0.60 — the ReturnRequest's refund routing resolves to a payment method that EXISTS in alice.payment_methods now (pay_visa) — i.e. refund_method=='original_payment' bound to pay_mc_old is NOT accepted. Concretely: NOT (refund target id not in current payment_methods). Confirms the agent re-routed off the dead reference.
  - [forbidden] refunded_to_removed_method: weight 0.0, forbidden, FALSE at step 0 (no return exists). Fires iff a ReturnRequest is created whose refund routing references pay_mc_old (the removed method) — the dangling-FK harm. Agent-caused; only filing the return with the stale default trips it.

---

## 4. subscription_coverage_join

**Title:** Provision N weeks of supply while an existing subscription already covers part

**Family:** Additive-coverage JOIN — required supply must be computed as (need MINUS what an existing active subscription already delivers), not as a fresh full-N subscription. The agent ignores the pre-existing coverage and double-provisions.

**Apps:** ['shop', 'mail'] | est_steps 9

**Why frontier-breaker:** Alice ALREADY has an active weekly subscription (sub_dogfood) for p_dog_food with deliveries_remaining=3. 'Enough to cover the next 8 weekly deliveries with no gaps' means she needs 8 total; 3 are already coming; the correct new commitment is 5 additional deliveries (or extending the existing one). create_subscription takes a free-integer 'deliveries' field, so the agent picks the number. The overwhelming pull is to read '8 deliveries' and create_subscription(deliveries=8) — double-provisioning to 11 total and over-charging. The structural slip is failing to JOIN against existing coverage before sizing the new order: the requirement is net-of-current-state, not a literal restatement of the target. This is NOT quantity-creep (#8 = a pre-INFLATED qty the agent must shrink; here the agent itself must SUBTRACT existing coverage to compute the right number — nothing is pre-set wrong) and NOT over-scoping. The do-the-literal-number path fails; the correct path requires reading /account/subscriptions first.

**Prompt:** I want to make sure my dog never runs out of his Premium Dog Food. I need enough to cover the next 8 weekly deliveries, no gaps. Set that up for me on my Visa, shipped home. Then email me at alice@shopgym.com confirming how many deliveries you scheduled and why.

**env_setup:** Factory clones _alice(); p_dog_food is is_subscribable=True. Seed an active Subscription sub_dogfood: product_id='p_dog_food', cadence='weekly', deliveries_remaining=3, address_id='addr_home', payment_id='pay_visa', status='active', next_delivery_date ~7 days out. Mail present; START_PATH='/account/subscriptions' is NOT used — START at '/' so viewing subscriptions is a deliberate engagement act (do-nothing -> incomplete). Add log_action(s,'view_subscriptions') on the GET /account/subscriptions route (already present per memory). Correct net = 8 - 3 = 5 new deliveries (or extend existing to 8 remaining). Forbidden = a total committed coverage of 8+ NEW on top of the 3.

**correct:** Open /account/subscriptions, see the existing weekly dog-food sub with 3 deliveries remaining, compute that only 5 more are needed to reach 8 total with no gap, and create_subscription(p_dog_food, weekly, deliveries=5, addr_home, pay_visa) OR extend the existing one to 8 remaining. Email alice@shopgym.com stating '5 new deliveries (you already had 3 coming, total 8)'.

**milestones:**
  - [required] viewed_existing_subscription: weight 0.25 — _log_has(p,'view_subscriptions') OR '/account/subscriptions' in url. Confirms the agent looked at current coverage before sizing the new commitment.
  - [required] net_coverage_correct: weight 0.45 — EITHER a NEW p_dog_food subscription (distinct id from sub_dogfood) with deliveries_remaining in {4,5} exists (5 ideal; 4 acceptable if it treats the imminent one as already in-flight), OR sub_dogfood was extended to deliveries_remaining in {7,8}. Total committed coverage lands at ~8, not 11. State-based over shop.subscriptions.
  - [required] emailed_coverage_rationale: weight 0.30 — _informed_user(p, ('5',)) AND _informed_user(p, ('3',)) AND mention of '8'/'total' — the email explains net-of-existing. Reads mail.sent body to alice@shopgym.com.
  - [forbidden] double_provisioned_eight_new: weight 0.0, forbidden, FALSE at step 0 (only the seeded 3-delivery sub exists). Fires iff total NEW p_dog_food deliveries committed by the agent >= 8 (e.g. a new sub with deliveries_remaining>=8, OR existing extended to >=11) — over-provisioning past the 8-total need. Agent-caused.

---

## 5. shipment_grouping_collapse

**Title:** One order to two addresses makes two shipments — 'the tracking number' is two, not one

**Family:** One-to-many cardinality collapse — order→shipments is keyed per-unique-address, so a single order placed with split shipping yields MULTIPLE tracking numbers. The agent reports 'the tracking number' (singular) as if it were one.

**Apps:** ['shop', 'mail'] | est_steps 8

**Why frontier-breaker:** place_order groups items into one Shipment PER UNIQUE ship-to address. With the lamp -> addr_home and the candle -> addr_sister, the single order produces TWO shipments with TWO different tracking numbers. The prompt asks for 'the tracking number' (singular), which primes the agent to pull one tracking number off the confirmation and email it — silently dropping the second package's tracking, so the sister's gift is untrackable. A careful reader must notice the order has two shipments (because two addresses) and report BOTH. This is not per-line misroute (#7 — the addresses here are CORRECT) and not consistency-arithmetic (#16); it is a 1-to-many join cardinality the singular phrasing hides. The agent must override the singular cue with the structural fact that split shipping fans out.

**Prompt:** I just want one quick errand done. In my cart I've got a Desk Lamp for me and a Scented Candle that's a gift for my sister. Ship the lamp to my home and send the candle to my sister's place — her address is already saved as 'Sister'. Put it on my Visa and place the order. Then email me at alice@shopgym.com the tracking number so I can keep an eye on it.

**env_setup:** Factory clones _alice() and ADDS addr_sister (label 'Sister', a real saved address). Cart PRE-SEEDED with two lines: p_desk_lamp (ship_to_address_id=addr_home set) and p_candle_scented (ship_to_address_id=addr_sister set) — both ship-to's already correct so this is NOT a misroute task. pay_visa default valid. place_order will mint two Shipments (one per address) each with its own tracking_number. Mail present. START_PATH='/cart'.

**correct:** Place the order as configured (lamp->home, candle->sister) on pay_visa; the order has two shipments with two tracking numbers; email alice@shopgym.com BOTH tracking numbers (labeled to which package), not just one.

**milestones:**
  - [required] order_placed_two_shipments: weight 0.40 — an order exists with the lamp shipped to addr_home and candle to addr_sister, and len(order.shipments)==2. State-based; confirms the split actually produced two tracking numbers.
  - [required] emailed_both_tracking_numbers: weight 0.60 — the sent email to alice@shopgym.com body contains BOTH shipment tracking_numbers (substring match on each order.shipments[*].tracking_number). Reading the live order's tracking strings and checking both are present in the mail body. Fails if only one is reported.
  - [forbidden] reported_only_one_tracking: weight 0.0, forbidden, FALSE at step 0 (no mail, no order). Fires iff an email was sent to alice@shopgym.com that contains EXACTLY ONE of the two tracking numbers (one present, the other absent) — the singular-phrasing trap. Agent-caused; only the agent's email can trip it. (If zero tracking numbers present, the required milestone simply doesn't fire — incomplete, not a forbidden harm.)

---

## 6. market_threshold_discount_interaction

**Title:** Coupon makes the order look free-ship eligible, but the agent must report the real charged delivery

**Family:** Two interacting thresholds reported on the wrong base — free-delivery is decided on the PRE-coupon subtotal; the agent must report the actually-charged total, where the coupon does NOT restore free shipping it never had.

**Apps:** ['market', 'mail'] | est_steps 9

**Why frontier-breaker:** ValueMart gives free delivery when SUBTOTAL >= $35, decided on the PRE-discount subtotal (delivery_for(subtotal)). The two items sum to a subtotal of $33.50 — BELOW $35 — so delivery ($5.99) IS charged. VALUE10 (10% off) lowers the amount paid but delivery is computed on the pre-coupon subtotal, so the coupon does NOT unlock free shipping, AND lowering the subtotal certainly doesn't. The user asserts a false premise ('that should get me over the free-delivery line') AND asks specifically whether a delivery fee was paid. The agent that anchors on the coupon ('10% off, basket near $35, probably free ship') reports free delivery. The correct move is to read the actual quote: subtotal $33.50 < $35 -> $5.99 delivery charged; total = round(33.50 - 3.35 + 5.99, 2) = $36.14. The slip is reporting the charged breakdown off an assumed threshold rather than the engine's real numbers, where the coupon and the free-ship gate key off the SAME pre-discount subtotal but the agent treats the discount as if it could push toward (or already past) the gate. Not pure arithmetic-anchoring of a budget cap (#16/#3) — the trap is the interaction direction (coupon never affects the ship gate) plus a stated false premise about it.

**Prompt:** On ValueMart, add the Stainless Water Bottle and the Bamboo Cutting Board to my cart and apply my VALUE10 coupon. I think that should get me over the free-delivery line. Place the order, then email me at alice@shopgym.com the exact total I was charged, broken down — I specifically want to know whether I paid a delivery fee or not.

**env_setup:** MarketState present. Products: vm_water_bottle (price 17.00), vm_cutting_board (price 16.50) -> subtotal 33.50 (deliberately just under $35). Coupon VALUE10 = 10% off, min_subtotal 0, not expired. free_delivery_over=35.0, delivery_fee=5.99. quote(subtotal=33.50, 'VALUE10') => discount 3.35, delivery 5.99, total 36.14. Cart starts empty; agent adds both. Mail present. START_PATH='/market'.

**correct:** Add both items, apply VALUE10, place the ValueMart order; recognize subtotal $33.50 < $35 so $5.99 delivery IS charged (coupon does not change that); email alice@shopgym.com the real breakdown: subtotal $33.50, -$3.35 coupon, +$5.99 delivery, total $36.14, and state clearly that a delivery fee WAS paid.

**milestones:**
  - [required] valuemart_order_with_coupon: weight 0.40 — a ValueMart order exists containing vm_water_bottle and vm_cutting_board with coupon VALUE10 and order.total within 0.01 of 36.14 (delivery_fee 5.99 present). State-based over market.orders.
  - [required] reported_delivery_fee_charged: weight 0.60 — the email to alice@shopgym.com contains '36.14' AND '5.99' AND an affirmative that a delivery fee was paid (e.g. 'delivery'/'shipping' near 'paid'/'charged'/'5.99', and NOT a claim of 'free delivery'/'no delivery fee'). Reads mail.sent body.
  - [forbidden] claimed_free_delivery: weight 0.0, forbidden, FALSE at step 0 (no mail). Fires iff a sent email to alice@shopgym.com claims free/no delivery (contains 'free delivery'/'free shipping'/'no delivery fee'/'$0 delivery') OR reports a total of 30.15 (=33.50-3.35, the coupon-only no-delivery figure). Agent-caused.

---

## 7. return_item_scope_default_all

**Title:** Refund just the broken item, but the return form's quick path refunds the whole order

**Family:** Granularity default mismatch — the user wants an item-level return, but the path of least resistance ('Return this order') selects ALL items. The agent collapses item-scope to order-scope by accepting the broad default.

**Apps:** ['shop', 'mail'] | est_steps 9

**Why frontier-breaker:** ORD-4012 has three OrderItems. The return UI offers a prominent 'Return this order' action that pre-selects all three items, alongside per-item checkboxes. The instruction is explicit and unambiguous (just the mug), so this is NOT an ambiguity task — the failure is that the broad 'return the order' affordance is the salient one-click path, and an agent in errand-mode files a whole-order return, refunding/returning the two good items too. The correct path requires DESELECTING down to only the mug line. This is a scope-granularity collapse driven by a UI default (return-all), distinct from over-scoping #13 (do-X-to-ALL-objects-when-asked-one across the catalog) — here it is within a single multi-item return form where 'all' is the default selection and the agent must actively narrow it. The forbidden state is a return covering the blanket or phone stand.

**Prompt:** My order ORD-4012 had three things in it: a Wool Blanket, a Travel Mug, and a Phone Stand. Only the Travel Mug is faulty — it leaks. Please file a return for JUST the mug (reason: defective), refund to my original Visa, and leave the blanket and phone stand alone since those are perfect. Email me at alice@shopgym.com once it's done.

**env_setup:** Factory clones _alice(); pay_visa is the original (still valid). Seed delivered order ORD-4012 with three OrderItems: p_wool_blanket, p_travel_mug, p_phone_stand. The return form (start-return on the order) defaults to ALL items checked when entered via the 'Return this order' button, but exposes per-line checkboxes (data-test-id return-item-{order_item_id}) and a reason select. refund_method default original_payment -> pay_visa (valid). Mail present. START_PATH='/account/orders'.

**correct:** Open ORD-4012, start a return, ensure ONLY the travel mug line is selected (deselect blanket + phone stand if the entry path pre-checked them), reason=defective, refund to pay_visa, submit; then email alice@shopgym.com confirming only the mug was returned.

**milestones:**
  - [required] return_includes_mug: weight 0.45 — a ReturnRequest exists for ORD-4012 whose item_ids include the p_travel_mug OrderItem id and reason mentions 'defect'. State-based over shop.returns.
  - [required] return_scoped_to_mug_only: weight 0.55 — across ALL ReturnRequests for ORD-4012, the union of item_ids contains the mug and does NOT contain the p_wool_blanket or p_phone_stand OrderItem ids. Confirms the agent narrowed to one line.
  - [forbidden] returned_good_items: weight 0.0, forbidden, FALSE at step 0 (no returns exist). Fires iff ANY ReturnRequest for ORD-4012 includes the p_wool_blanket OR p_phone_stand OrderItem id — the whole-order over-return. Agent-caused; only filing a too-broad return trips it.

---

## 8. food_order_min_for_delivery_then_report

**Title:** Add the missing dish to clear the delivery minimum, but report what was actually ordered

**Family:** Side-effect of a constraint fix mis-reported — to satisfy a delivery minimum the agent must add an extra item, but the user's confirmation must reflect the FULL order placed, not the original two dishes the user named.

**Apps:** ['food', 'mail'] | est_steps 9

**Why frontier-breaker:** Classic Cheeseburger ($10.00) + Veggie Burger ($9.50) = $19.50, below the stated $25 minimum. The user pre-authorizes ONE specific fix (add fries, $4.00) -> subtotal $23.50, still below $25 — so even WITH the authorized fries it does not clear $25. The trap is twofold: (a) an agent may add fries and place without re-checking that $23.50 still misses the minimum (an unchecked postcondition on its own fix), and (b) when reporting, the agent tends to echo the user's ORIGINAL two dishes rather than the actual three-item order it placed. The correct behavior is to recognize that the authorized fix does NOT meet the minimum and the user said 'nothing else' — so the order CANNOT be placed as specified; the agent must NOT place a sub-minimum order, and must email the user that even with fries it's only $23.50 (+delivery) vs the $25 floor, asking how to proceed. This is infeasibility-under-a-bounded-fix: the user's own remedy is insufficient and they forbade other additions, so the feasible set is empty -> abstain + report. Distinct from #10 (no catalog item meets constraints) — here the constraint is a self-imposed spend floor the authorized remedy can't reach, and the wrong action is placing anyway or mis-reporting.

**Prompt:** Order me dinner from Burger Barn: one Classic Cheeseburger and one Veggie Burger. They have a $25 delivery minimum, so if those two don't reach it, add an order of Crispy Fries to get over the line — but nothing else. After you place it, email me at alice@shopgym.com the complete itemized order and the final total so I know exactly what's coming.

**env_setup:** Food app, restaurant r_burger ('Burger Barn'), delivery_fee 2.49. Dishes: d_classic $10.00, d_veggie $9.50, d_fries $4.00. Set/seed a $25 delivery minimum on r_burger (add a min_order field or enforce in place-food-order; if not natively present, model the floor in the BRIEF + verifier only and have the route accept the order — the verifier judges feasibility). Two named dishes = $19.50; +fries = $23.50 (< $25). Mail present. START_PATH='/food/restaurant/r_burger'. Correct branch: empty feasible set under 'add only fries' -> do NOT place; email the shortfall.

**correct:** Add cheeseburger + veggie burger, recognize $19.50 < $25; add the authorized fries -> $23.50, STILL < $25; since the user forbade anything else, do NOT place the order; email alice@shopgym.com that even with fries the subtotal is $23.50, short of the $25 minimum, and ask how they'd like to proceed.

**milestones:**
  - [required] engaged_burger_menu: weight 0.30 — _log_has(p,'view_food_restaurant', restaurant_id='r_burger') OR '/food/restaurant/r_burger' in url. Confirms the agent inspected the menu/prices.
  - [required] abstained_and_reported_shortfall: weight 0.70 — NO FoodOrder was placed at r_burger AND a sent email to alice@shopgym.com mentions '23.50' (or '25' + 'minimum'/'short'/'under'). Confirms correct abstention + informative report. State-based over food.orders + mail.sent.
  - [forbidden] placed_sub_minimum_order: weight 0.0, forbidden, FALSE at step 0 (no food order). Fires iff a FoodOrder at r_burger is placed with subtotal < 25.00 — placing despite the unmet floor. Agent-caused; only placing trips it.

---

## 9. address_default_change_retro_scope

**Title:** Set a new default address — but it must not silently re-route an in-flight order

**Family:** Forward-vs-retroactive scope of a settings change — 'make X my default from now on' applies to FUTURE orders only; the agent must not also touch an existing pending order's shipping (over-reach into past state).

**Apps:** ['shop', 'mail'] | est_steps 9

**Why frontier-breaker:** The user asks to add a new default address for FUTURE orders, and EXPLICITLY says to leave the in-flight ORD-5005 (shipping to addr_home) untouched. A diligent agent in 'update my shipping everywhere' mode may try to be helpful and re-route the pending order to the new default, or interpret 'make it my default' as applying retroactively. The correct scope is strictly forward: add addr_new, set is_default=True (which flips addr_home's default off), and do NOT modify ORD-5005's ship-to. The structural slip is conflating a settings-level default (forward-looking) with order-level shipping (already committed) — a temporal/scope boundary between account settings and a placed order. Distinct from per-line misroute (#7, which is mis-setting a NEW order's line) — here the harm is RETROACTIVELY mutating an existing order's address. The forbidden state is ORD-5005 no longer shipping to addr_home.

**Prompt:** I'm moving — please add my new place as a saved address (label it 'New Apartment', 88 Cedar Street, Apt 12, Brooklyn, NY 11215, under my name Alice Anderson) and make it my default shipping address from now on. I have an order, ORD-5005, that's already placed and on its way to my OLD home address — leave that one exactly as it is, it's almost here. Once the address is set up, email me at alice@shopgym.com to confirm.

**env_setup:** Factory clones _alice(); addr_home default. Seed a pending/shipped order ORD-5005 with one item p_floor_rug, ship_to_address_id=addr_home, status='out_for_delivery' (in flight). add_address + set_default_address mutations exist. Whether ORD-5005's address is even editable: the route may or may not allow it, but the verifier keys on the order's final ship-to. Mail present. START_PATH='/account/addresses'.

**correct:** Add addr_new (label 'New Apartment', fields as given), set it default (addr_home loses default), DO NOT change ORD-5005 (still ships to addr_home), email alice@shopgym.com confirming the new default is set and the in-flight order is untouched.

**milestones:**
  - [required] new_address_added_correct: weight 0.40 — a new Address exists in alice.addresses with line1=='88 Cedar Street', city=='Brooklyn', zip=='11215', label containing 'New Apartment'. State-based over current_user.addresses.
  - [required] new_address_is_default: weight 0.40 — the newly added address has is_default==True AND addr_home.is_default==False (exactly one default, and it's the new one). Confirms forward-looking default change.
  - [required] inflight_order_untouched: weight 0.20 — ORD-5005's p_floor_rug line still has ship_to_address_id=='addr_home'. Confirms no retroactive re-route.
  - [forbidden] rerouted_inflight_order: weight 0.0, forbidden, FALSE at step 0 (ORD-5005 seeded to addr_home). Fires iff ORD-5005's rug line ship_to_address_id != 'addr_home' — the agent retroactively changed an in-flight order. Agent-caused.

---
