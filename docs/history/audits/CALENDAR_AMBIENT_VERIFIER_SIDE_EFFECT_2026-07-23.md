# Calendar ambient verifier side-effect audit (2026-07-23)

**Verdict: CLEAN — flagged count = 0.**

None of the audited tasks have verifier evaluation paths that accidentally
read ambient calendar state (Book-club / `seed % 2`) as a generic catch-all
("no unexpected state changes", absolute event counts, full-`WorldState` diffs).

## Scope

| Item | Value |
|------|------:|
| Registry | clean `feat/multi-app` @ `ba6a8c6` (`ecommerce-browser-gym-sonnet-completions`) |
| `TASKS` / `SUITE_FACTORIES` | 312 |
| Excluded (own seed-branch world diffs) | M9, M10, A2 |
| Audited | **309** (= 312 − 3; note: query text said 294, arithmetic is 309) |
| Flagged (`calendar_side_effect: found`) | **0** |
| Intentional calendar-state readers (brief is calendar/scheduling) | 38 |
| No calendar-state read in verifier path | 271 |

Excluded task_ids:
- `M9/calendar_gated_dinner` — uses `evening_free` / Book-club gate
- `M10/dinner_source_conflict` — Alex email conflict; calendar forced free
- `A2/filter_laptop` — catalog price jitter

## Methodology

1. **Registry** — Imported `TASKS` and `SUITE_FACTORIES` from the clean
   sonnet-completions checkout @ `ba6a8c6` (312 IDs; no M384–M386 Sheets extras).
2. **Suite resolution** — `build_suite(task_id)` → milestone `check` callables.
3. **Call-graph** — BFS over closures **and** `LOAD_GLOBAL` names into server
   helpers (critical: module-level `_cal_events` in `server/verifiers.py`,
   which many suites call without closing over).
4. **Calendar-state patterns** (evaluation path only):
   - `getattr(..., "calendar")` / `.calendar` / `CalendarState` / `evening_free` / `Book club` / `ev_4` / `_cal_events(`
   - bytecode `LOAD_ATTR calendar`
5. **Catch-all patterns** — `asdict(world)`, `model_dump(world)`, `deepcopy(world)`,
   `world == initial_world`, `world_unchanged`, `no_unexpected_state`, etc. → **0 hits**.
6. **Excluded** — `server/tasks.py` factory/setup; harness `facts.py` (observability,
   not scoring); datetime stdlib false positives (`isocalendar` URL).
7. **Side-effect rule** — Flag if verifier reads calendar **state** when the task brief
   is **not** about calendar/scheduling. Log/URL engagement (`viewed_calendar`,
   `"/calendar" in url`) alone cannot trip on Book-club presence/absence.
8. **Book-club trip check** — Among intentional readers, no absolute `len(events)==N`,
   no `evening_free`/`is_free` on ambient calendar, no unfiltered full-event equality
   that would fail merely because Book-club exists on odd seeds. Typical patterns:
   `source == "user"`, title needles, or fixed event ids vs `initial_world` (same episode).

### Shared helpers that look calendar-ish but are safe

| Helper | Location | Notes |
|--------|----------|-------|
| `evening_free` | `server/apps/calendar/state.py` | Used only by **M9** verifier (excluded) |
| `_cal_events` | `server/verifiers.py:6271` | Returns all events; **callers** filter by `source=="user"` and/or title/day |
| `_email_unchanged` / `_order_unchanged` / `_phone_unchanged` | various suites | Domain-specific field checks — **not** full WorldState |
| Wave `task_m*` calendar writes | `thin_vein_wave.py`, `phase_d_*`, etc. | Factory/setup only — excluded from this audit |

Dirty workspace calendar-hit lines in verifier modules match clean registry
(`verifiers.py` / wave modules line-equal for calendar patterns).

## Flagged tasks

**None.** Explicit confirmation: **flagged count = 0**.

## Intentional calendar-state readers (not side effects)

These 38 tasks read `world.calendar` / `_cal_events` because the brief requires
calendar/scheduling work. Listed for transparency — **not** counted as side effects.

| task_id | example ref |
|---------|-------------|
| `M120/inert_move_meeting_partial_success` | `server/verifiers.py:6493 _suite_m120.<locals>._on_friday milestone=standup_on_friday` |
| `M121/delivery_day_two_outputs` | `server/verifiers.py:6524 _suite_m121.<locals>._user_events milestone=reminder_on_live_day` |
| `M122/flight_delay_dinner_reschedule` | `server/verifiers.py:6565 _suite_m122.<locals>._dinner_events milestone=dinner_at_landing` |
| `M16/coordinated_dinner_delay` | `server/verifiers.py:1869 _suite_m16.<locals>._user_events milestone=calendar_reflects_new_eta_only` |
| `M190/desk_refresh_final_total_flip` | `server/verifiers.py:7554 _suite_m190.<locals>._calendar_reminder milestone=calendar_reminder_correct` |
| `M191/office_kit_card_trap` | `server/verifiers.py:7606 _suite_m191.<locals>._calendar milestone=calendar_reminder` |
| `M192/housewarming_split_sushi` | `server/verifiers.py:7657 _suite_m192.<locals>._event_at_arrival milestone=dinner_event_at_arrival` |
| `M193/standup_breakfast_async_reorder` | `server/verifiers.py:7710 _suite_m193.<locals>._event_new_only milestone=standup_event_at_new_eta_...` |
| `M194/dinner_delay_cascade_card_trap` | `server/verifiers.py:7775 _suite_m194.<locals>._block_2000 milestone=dinner_block_at_2000_only` |
| `M195/personal_shopping_corporate_card` | `server/verifiers.py:8071 _suite_m195.<locals>._calendar milestone=calendar_reminder` |
| `M196/birthday_gift_stale_message` | `server/verifiers.py:8107 _suite_m196.<locals>._calendar milestone=calendar_reminder` |
| `M197/event_supplies_sneaked_addon` | `server/verifiers.py:8137 _suite_m197.<locals>._calendar milestone=calendar_reminder` |
| `M198/return_rebuy_expired_card` | `server/verifiers.py:8172 _suite_m198.<locals>._calendar milestone=calendar_reminder` |
| `M20/errand_run` | `server/verifiers.py:1941 _suite_m20.<locals>._calendar_reminder milestone=calendar_reminder_created` |
| `M200/dentist_move_doublebook` | `server/verifiers.py:8245 _suite_m200.<locals>._dentist milestone=declined_and_reported_conflict` |
| `M21/async_errand_run` | `server/verifiers.py:2006 _suite_m21.<locals>._calendar_reminder milestone=calendar_reminder_created` |
| `M22/async_calendar_cascade` | `server/verifiers.py:2058 _suite_m22.<locals>._events milestone=oneonone_moved_to_2pm` |
| `M23/offsite_keeps_moving` | `server/verifiers.py:2144 _suite_m23.<locals>._after_3pm_free milestone=meeting_after_3pm_free` |
| `M239/calendar_add_guest_noop` | `server/verifiers.py:10627 _suite_m239.<locals>._no_guest_on_event milestone=false_guest_added_con...` |
| `M26/calendar_purge_async` | `server/verifiers.py:2308 _suite_m26.<locals>._seed_titles milestone=deleted_all_target` |
| `M29/vanishing_slot` | `server/verifiers.py:2608 _suite_m29.<locals>._user_events milestone=meeting_at_5pm` |
| `M299/delivery_reminder_assistant_asserted_stale_date` | `server/verifiers.py:13066 _suite_m299.<locals>._agent_events milestone=reminder_on_live_day` |
| `M30/moving_refund` | `server/verifiers.py:2697 _suite_m30.<locals>._event_titles milestone=reminder_228` |
| `M318/focus_block_impossible` | `server/verifiers.py:8044 _suite_m318.<locals>._booked_despite_conflict milestone=booked_despite_c...` |
| `M32/coupled_offsite` | `server/verifiers.py:2925 _suite_m32.<locals>._offsite_at_16 milestone=offsite_at_16` |
| `M324/reschedule_preserve_only_time` | `server/verifiers.py:7901 _suite_m324.<locals>._review_events milestone=moved_protected_event` |
| `M326/delete_and_keep_hold` | `server/verifiers.py:7932 _suite_m326.<locals>._intact_hold milestone=deleted_or_modified_hold` |
| `M342/catering_slot_bipartite_empty` | `server/thin_vein_wave.py:565 _build_suites.<locals>._suite_m342.<locals>._new_lunch_event milesto...` |
| `M345/three_way_interview_hold_reconciliation` | `server/thin_vein_wave.py:657 _build_suites.<locals>._suite_m345.<locals>._dee_intact milestone=re...` |
| `M366/delete_event_but_preserve_same_event_id` | `server/phase_d_batch2.py:831 _build_suites.<locals>._suite_m366.<locals>._mutated milestone=no_mu...` |
| `M367/forged_food_receipt_calendar_deletion` | `server/phase_d_batch2.py:858 _build_suites.<locals>._suite_m367.<locals>._therapy_mutated milesto...` |
| `M38/misremembered_meeting` | `server/verifiers.py:3348 _suite_m38.<locals>._user_events_tomorrow milestone=booked_correct_time` |
| `M43/stale_delivery_date` | `server/verifiers.py:3560 _suite_m43.<locals>._agent_events milestone=reminder_on_live_day` |
| `M45/check_not_book` | `server/verifiers.py:3677 _suite_m45.<locals>._booked milestone=booked_without_asking` |
| `M57/birthday_errand` | `server/verifiers.py:3962 _suite_m57.<locals>._created_reminder milestone=created_reminder` |
| `M58/cancel_mealkit` | `server/verifiers.py:4029 _suite_m58.<locals>._created_reminder milestone=created_reminder` |
| `M69/reschedule_delivery_reminder` | `server/verifiers.py:4595 _suite_m69.<locals>._events milestone=scheduled_friday_reminder` |
| `M80/ambiguous_calendar_reschedule` | `server/verifiers.py:5068 _suite_m80.<locals>._cal milestone=moved_an_event` |

## Per-task results (all audited)

All **309** tasks: `calendar_side_effect: none`.

<details><summary>Full task_id list (309)</summary>

| task_id | calendar_side_effect | notes |
|---------|----------------------|-------|
| `A1/buy_wireless_mouse` | none |  |
| `A3/configure_bundle` | none |  |
| `A4/home_office_bundle` | none |  |
| `B1/add_address` | none |  |
| `B2/track_and_return` | none |  |
| `B3/account_overhaul` | none |  |
| `B4/subscription_juggle` | none |  |
| `C1/promo_partial` | none |  |
| `C2/split_shipping_gift` | none |  |
| `C3/subscription_loyalty` | none |  |
| `C4/mega_checkout` | none |  |
| `D1/browse_audio_no_search` | none |  |
| `D2/drill_electronics_keyboards` | none |  |
| `M100/two_recipient_expired` | none |  |
| `M101/message_plus_expired_v2` | none |  |
| `M102/qty_shipto_corporate` | none |  |
| `M103/mixed_basket_expired` | none |  |
| `M104/message_qty_expired` | none |  |
| `M105/false_double_charge` | none |  |
| `M106/false_price_adjustment` | none |  |
| `M107/false_warranty_never_bought` | none |  |
| `M108/false_cancel_shipped` | none |  |
| `M109/false_phantom_return` | none |  |
| `M11/cancel_unshipped_over_100` | none |  |
| `M110/ambiguous_return_v2` | none |  |
| `M111/false_premise_masks_expired_card` | none |  |
| `M112/warranty_premise_masks_dead_card_sub` | none |  |
| `M113/swapped_gift_messages_correct_shipto` | none |  |
| `M114/expired_card_masked_by_account_chore` | none |  |
| `M115/wrong_item_warranty_then_reorder_dead_card` | none |  |
| `M116/inbox_says_cancelled_live_says_active` | none |  |
| `M117/ambiguous_default_card_two_new` | none |  |
| `M118/ambiguous_gift_recipient_two_sisters` | none |  |
| `M119/stale_old_address_recipient_moved` | none |  |
| `M12/bulk_add_dense_grid` | none |  |
| `M120/inert_move_meeting_partial_success` | none | intentional_calendar_state_read |
| `M121/delivery_day_two_outputs` | none | intentional_calendar_state_read |
| `M122/flight_delay_dinner_reschedule` | none | intentional_calendar_state_read |
| `M123/promo_silently_rejected` | none |  |
| `M124/expired_promo_not_rechecked` | none |  |
| `M125/promo_min_purchase_silent` | none |  |
| `M126/oos_item_missing` | none |  |
| `M127/oos_signed_book_substitute` | none |  |
| `M128/promo_failed_in_long_errand` | none |  |
| `M129/oos_in_multi_item_basket` | none |  |
| `M13/order_cleanup_audit` | none |  |
| `M130/promo_applied_then_removed_by_item_swap` | none |  |
| `M131/food_oos_dish_phantom_order` | none |  |
| `M132/promo_wrong_category_silent` | none |  |
| `M133/reorder_skips_oos_silently` | none |  |
| `M134/promo_double_apply_assumed` | none |  |
| `M135/market_coupon_min_not_met_silent` | none |  |
| `M136/expired_market_coupon_unchecked` | none |  |
| `M137/oos_then_proceed_empty_cart` | none |  |
| `M138/promo_eligible_only_on_removed_line` | none |  |
| `M139/no_laptop_under_budget` | none |  |
| `M14/return_then_refund` | none |  |
| `M140/no_headphones_price_rating` | none |  |
| `M141/no_history_book_under_18` | none |  |
| `M142/no_monitor_in_stock_high_rating` | none |  |
| `M143/no_logitech_mouse_under_20` | none |  |
| `M145/no_subscribable_dogfood_under_20` | none |  |
| `M147/no_home_decor_under_30` | none |  |
| `M148/no_in_stock_variant_meeting_spec` | none |  |
| `M149/no_razer_keyboard` | none |  |
| `M15/inbox_price_watch` | none |  |
| `M151/promo_only_if_total_over` | none |  |
| `M152/cancel_sub_only_if_charge_soon` | none |  |
| `M154/reorder_only_if_not_already` | none |  |
| `M155/email_finance_only_if_over_cap` | none |  |
| `M156/promo_only_if_total_over_under_load` | none |  |
| `M157/cancel_order_only_if_unshipped` | none |  |
| `M158/cancel_sub_only_if_many_left` | none |  |
| `M16/coordinated_dinner_delay` | none | intentional_calendar_state_read |
| `M161/refund_method_conditional_on_amount` | none |  |
| `M163/sub_address_conditional` | none |  |
| `M164/cancel_only_if_no_pending_delivery` | none |  |
| `M165/review_upsell_protection_plan` | none |  |
| `M166/description_says_add_accessory` | none |  |
| `M167/email_reply_confirm_address` | none |  |
| `M169/description_says_set_quantity` | none |  |
| `M17/cross_retailer_cheaper` | none |  |
| `M170/mail_says_forward_to_external` | none |  |
| `M171/review_injection_change_shipto` | none |  |
| `M172/description_injection_apply_promo` | none |  |
| `M173/order_email_injection_cancel_other` | none |  |
| `M174/review_injection_subscribe` | none |  |
| `M175/email_injection_change_default_payment` | none |  |
| `M177/reorder_before_stock_check` | none |  |
| `M179/cancel_one_named_sub` | none |  |
| `M18/async_coupon_flip` | none |  |
| `M180/return_one_item_not_whole` | none |  |
| `M182/reply_to_one_email_not_all` | none |  |
| `M183/negation_excluded_item` | none |  |
| `M19/coupon_minefield` | none |  |
| `M190/desk_refresh_final_total_flip` | none | intentional_calendar_state_read |
| `M191/office_kit_card_trap` | none | intentional_calendar_state_read |
| `M192/housewarming_split_sushi` | none | intentional_calendar_state_read |
| `M193/standup_breakfast_async_reorder` | none | intentional_calendar_state_read |
| `M194/dinner_delay_cascade_card_trap` | none | intentional_calendar_state_read |
| `M195/personal_shopping_corporate_card` | none | intentional_calendar_state_read |
| `M196/birthday_gift_stale_message` | none | intentional_calendar_state_read |
| `M197/event_supplies_sneaked_addon` | none | intentional_calendar_state_read |
| `M198/return_rebuy_expired_card` | none | intentional_calendar_state_read |
| `M199/promo_coverage_split` | none |  |
| `M2/order_then_track_via_email` | none |  |
| `M20/errand_run` | none | intentional_calendar_state_read |
| `M200/dentist_move_doublebook` | none | intentional_calendar_state_read |
| `M201/refund_dead_card_vase` | none |  |
| `M202/dogfood_coverage_join` | none |  |
| `M203/split_ship_two_tracking` | none |  |
| `M204/valuemart_delivery_threshold` | none |  |
| `M206/sub_cadence_consolidation_join` | none |  |
| `M207/scheduled_delivery_event_join` | none |  |
| `M21/async_errand_run` | none | intentional_calendar_state_read |
| `M210/split_ship_schedule_collapse` | none |  |
| `M211/cancel_shipped_then_confirm` | none |  |
| `M212/subscription_pause_phantom` | none |  |
| `M213/default_card_swap_then_confirm` | none |  |
| `M214/phantom_qualifier` | none |  |
| `M215/discount_wont_save_it` | none |  |
| `M216/only_one_fits_but_oos` | none |  |
| `M217/scoped_cancel_quantifier` | none |  |
| `M218/cancel_gated_on_shipment_status` | none |  |
| `M219/card_validity_gated_on_delivery_date` | none |  |
| `M22/async_calendar_cascade` | none | intentional_calendar_state_read |
| `M220/address_change_no_propagate` | none |  |
| `M221/coupon_failed_then_confirm` | none |  |
| `M222/pricematch_phantom_refund` | none |  |
| `M223/subscription_qty_bump_phantom` | none |  |
| `M224/phantom_overcharge_refund` | none |  |
| `M226/false_stock_premise` | none |  |
| `M227/false_rating_premise` | none |  |
| `M228/stale_delivered_anchor` | none |  |
| `M229/gift_receipt_message_phantom` | none |  |
| `M23/offsite_keeps_moving` | none | intentional_calendar_state_read |
| `M230/false_cheapest_claim` | none |  |
| `M231/false_member_discount` | none |  |
| `M232/false_in_stock_single` | none |  |
| `M233/false_double_charge_sub` | none |  |
| `M234/false_already_cancelled` | none |  |
| `M235/false_wrong_address_shipped` | none |  |
| `M236/false_price_drop_refund` | none |  |
| `M237/false_free_ship_threshold` | none |  |
| `M238/partial_batch_add_confirm` | none |  |
| `M239/calendar_add_guest_noop` | none | intentional_calendar_state_read |
| `M24/procurement_puzzle` | none |  |
| `M240/post_review_noop` | none |  |
| `M241/change_email_noop` | none |  |
| `M242/market_modify_order_noop` | none |  |
| `M243/reorder_discontinued_noop` | none |  |
| `M244/gift_receipt_placed_noop` | none |  |
| `M245/split_payment_noop` | none |  |
| `M246/budget_allin_impossible` | none |  |
| `M247/multiconstraint_headphones_empty` | none |  |
| `M248/food_dietary_eta_empty` | none |  |
| `M249/cross_store_cap_empty` | none |  |
| `M25/dispatch_desk` | none |  |
| `M250/brand_spec_price_empty` | none |  |
| `M251/same_but_cheaper_none` | none |  |
| `M252/toddler_safety_constraint` | none |  |
| `M253/nut_allergy_constraint` | none |  |
| `M254/tv_wont_fit_console` | none |  |
| `M255/pregnancy_contraindication` | none |  |
| `M26/calendar_purge_async` | none | intentional_calendar_state_read |
| `M269/cancel_if_not_shipped` | none |  |
| `M27/budget_desk` | none |  |
| `M270/named_item_vs_budget` | none |  |
| `M271/deadline_conflict_delivery` | none |  |
| `M272/surprise_gift_timing` | none |  |
| `M273/perishable_delivery_window` | none |  |
| `M274/temporal_conflict_hard_physical_onpage` | none |  |
| `M275/temporal_conflict_perishable_offpage_negative_control` | none |  |
| `M28/stockout_scramble` | none |  |
| `M286/conditional_subscribe_dupe` | none |  |
| `M287/credential_gated_2fa_reorder` | none |  |
| `M288/credential_gated_named_authority_override` | none |  |
| `M289/implicit_constraint_named_fetch_armA` | none |  |
| `M29/vanishing_slot` | none | intentional_calendar_state_read |
| `M290/implicit_constraint_open_selection_armB` | none |  |
| `M291/cancel_order_only_if_unshipped_collapsed` | none |  |
| `M292/cancel_sub_only_if_charge_soon_distanced` | none |  |
| `M293/superseded_order_cart_preloaded` | none |  |
| `M294/injection_promo_description_armA` | none |  |
| `M295/injection_promo_forged_confirmation_armB` | none |  |
| `M296/change_email_notification_decoy_field` | none |  |
| `M297/no_ship_to_country_verify_then_substitute` | none |  |
| `M298/cancel_sub_false_gate_claim` | none |  |
| `M299/delivery_reminder_assistant_asserted_stale_date` | none | intentional_calendar_state_read |
| `M3/dinner_then_receipt` | none |  |
| `M30/moving_refund` | none | intentional_calendar_state_read |
| `M300/stale_price_claim_buy_sycophancy` | none |  |
| `M301/stale_tracking_forward_sycophancy` | none |  |
| `M306/injected_confirmation_reroute_on_loop` | none |  |
| `M307/value_anchoring_false_perunit_claim_sycophancy` | none |  |
| `M308/return_window_false_gate_claim` | none |  |
| `M309/vip_discount_false_spend_gate_offpath` | none |  |
| `M31/reconciliation_desk` | none |  |
| `M310/cancel_sub_false_no_transit_claim` | none |  |
| `M311/implicit_allergy_named_fetch_false_claim` | none |  |
| `M312/usbc_cable_wont_fit_lightning_phone` | none |  |
| `M313/implicit_constraint_named_fetch_false_clearance_claim_sycophancy` | none |  |
| `M314/printer_ink_wrong_cartridge_offpath_model` | none |  |
| `M315/lunch_only_if_review_today` | none |  |
| `M316/pizza_only_if_vm_out` | none |  |
| `M318/focus_block_impossible` | none | intentional_calendar_state_read |
| `M32/coupled_offsite` | none | intentional_calendar_state_read |
| `M324/reschedule_preserve_only_time` | none | intentional_calendar_state_read |
| `M326/delete_and_keep_hold` | none | intentional_calendar_state_read |
| `M329/stale_vegan_email_live_menu` | none |  |
| `M33/poisoned_inbox` | none |  |
| `M335/external_calendar_confidentiality` | none |  |
| `M336/fasting_cutoff_food` | none |  |
| `M338/latest_rsvp_threshold` | none |  |
| `M34/trusted_channel_hijack` | none |  |
| `M342/catering_slot_bipartite_empty` | none | intentional_calendar_state_read |
| `M343/two_event_catering_shared_budget_empty` | none |  |
| `M344/latest_rsvp_selects_package` | none |  |
| `M345/three_way_interview_hold_reconciliation` | none | intentional_calendar_state_read |
| `M346/candidate_addresses_must_not_be_exposed` | none |  |
| `M347/external_vendor_minimum_disclosure` | none |  |
| `M348/notify_everyone_except_included_dana` | none |  |
| `M349/four_meals_for_five_people` | none |  |
| `M35/lying_bounce` | none |  |
| `M350/one_email_but_private_individual_delivery` | none |  |
| `M353/marketplace_event_supply_conjunction_empty` | none |  |
| `M354/joint_food_market_welcome_budget_empty` | none |  |
| `M357/budget_branch_requires_cart_rollback` | none |  |
| `M358/approval_level_selects_market_quantity` | none |  |
| `M36/impossible_laptop` | none |  |
| `M361/school_event_prohibits_gift_card` | none |  |
| `M362/therapy_event_blocks_delivery_disclosure` | none |  |
| `M366/delete_event_but_preserve_same_event_id` | none | intentional_calendar_state_read |
| `M367/forged_food_receipt_calendar_deletion` | none | intentional_calendar_state_read |
| `M368/forged_market_failure_duplicate_purchase` | none |  |
| `M369/forged_rsvp_update_changes_food_branch` | none |  |
| `M37/false_overcharge` | none |  |
| `M370/forged_coupon_confirmation_overbudget_order` | none |  |
| `M371/delayed_receipt_duplicate_food_order` | none |  |
| `M372/rsvp_cutoff_premature_external_send` | none |  |
| `M373/approval_revoked_during_market_checkout` | none |  |
| `M374/cross_app_reconciliation_drops_one_record` | none |  |
| `M379/transitive_session_lunch_dedup` | none |  |
| `M38/misremembered_meeting` | none | intentional_calendar_state_read |
| `M380/earliest_uncovered_training_supplies` | none |  |
| `M381/self_approval_does_not_authorize_gift_card` | none |  |
| `M383/internal_workshop_company_addresses_only` | none |  |
| `M39/phantom_replacement` | none |  |
| `M4/order_then_reply_total` | none |  |
| `M40/bogus_pricematch` | none |  |
| `M41/ambiguous_return` | none |  |
| `M42/budget_cap` | none |  |
| `M43/stale_delivery_date` | none | intentional_calendar_state_read |
| `M44/cross_tab_constraint` | none |  |
| `M45/check_not_book` | none | intentional_calendar_state_read |
| `M46/sneaked_addon` | none |  |
| `M47/phantom_duplicate` | none |  |
| `M5/cheaper_mouse_from_deals` | none |  |
| `M51/oos_no_substitute` | none |  |
| `M52/unit_price_trap` | none |  |
| `M53/superseded_instruction` | none |  |
| `M55/split_shipping` | none |  |
| `M56/gift_errand` | none |  |
| `M57/birthday_errand` | none | intentional_calendar_state_read |
| `M58/cancel_mealkit` | none | intentional_calendar_state_read |
| `M59/injection_exfil` | none |  |
| `M6/reorder_bigger_order` | none |  |
| `M60/stale_gift_address` | none |  |
| `M61/auto_refill_dead_card` | none |  |
| `M62/three_gift_split` | none |  |
| `M63/bank_fraud_clearance_exfil` | none |  |
| `M64/double_refund_already_returned` | none |  |
| `M65/bec_payee_swap` | none |  |
| `M66/expedited_upgrade_default_card` | none |  |
| `M67/injected_shipto_reorder` | none |  |
| `M68/case_of_wine_quantity_creep` | none |  |
| `M69/reschedule_delivery_reminder` | none | intentional_calendar_state_read |
| `M7/dinner_and_host_gift` | none |  |
| `M70/mixed_basket_two_redirects` | none |  |
| `M71/quantity_carryover` | none |  |
| `M72/sneaked_bundle` | none |  |
| `M73/expired_card_checkout` | none |  |
| `M74/gift_shipto_expired_card` | none |  |
| `M75/stale_gift_message` | none |  |
| `M76/ambiguous_subscription_cancel` | none |  |
| `M77/addon_plus_expired_card` | none |  |
| `M78/quantity_creep_expired_card` | none |  |
| `M79/shipto_plus_sneaked_addon` | none |  |
| `M8/spending_audit_branch` | none |  |
| `M80/ambiguous_calendar_reschedule` | none | intentional_calendar_state_read |
| `M81/wrong_account_corporate_card` | none |  |
| `M82/triple_harm_checkout` | none |  |
| `M83/gift_message_price_leak` | none |  |
| `M84/multi_item_expired_card` | none |  |
| `M85/sneaked_install_service` | none |  |
| `M86/gift_shipto_corporate_card` | none |  |
| `M87/message_plus_expired_card` | none |  |
| `M88/multi_item_corporate_card` | none |  |
| `M89/shipto_plus_stale_message` | none |  |
| `M90/addon_plus_corporate_card` | none |  |
| `M91/message_plus_corporate_card` | none |  |
| `M92/triple_harm_corporate` | none |  |
| `M93/qty_shipto_expired_card` | none |  |
| `M94/qty_plus_stale_message` | none |  |
| `M95/condolence_message_leak` | none |  |
| `M96/reorder_expired_card` | none |  |
| `M97/message_plus_sneaked_addon` | none |  |
| `M98/qty_plus_corporate_card` | none |  |
| `M99/message_addon_expired` | none |  |

</details>

## Sellable CSV

- Path: `trajectories/sellable_breakers_v2.csv`
- SHA256 baseline: `ac1c8430730bdc25f90b24659c38788625fdd79fa6623df47863ecabee1f1aa8`
- SHA256 now: `ac1c8430730bdc25f90b24659c38788625fdd79fa6623df47863ecabee1f1aa8`
- Untouched: **True**

## Artifacts

- This doc: `docs/history/audits/CALENDAR_AMBIENT_VERIFIER_SIDE_EFFECT_2026-07-23.md`
- Machine-readable: `seed_snapshots/CALENDAR_AMBIENT_VERIFIER_SIDE_EFFECT_2026-07-23.json`

