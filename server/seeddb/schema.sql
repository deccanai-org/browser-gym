-- SQLite DDL for fixtures/seed.db.v1.sqlite. Conventions:
--  * scope TEXT = 'base' (shared, copied into every clone) OR a task_id (per-task overlay patch).
--  * pos INTEGER = insertion ordinal CAPTURED from the real built world (authoritative, not derived),
--    used to reconstruct BOTH list order AND dict key-insertion order via ORDER BY pos.
--  * tombstone INTEGER = overlay delete marker (rare; a task that removes a base row).
--  * *_json TEXT = free-form / typed-as-dict / list[str] fields, stored as JSON (order preserved inside).
--  * INTEGER vs REAL is deliberate so Python int 5 round-trips as 5, not 5.0.
--  * NO columns for derived keys (products_count, unread_count, cart_count, cart_subtotal, pending,
--    calendar today/tomorrow, current_user) — recomputed by the unchanged to_json from hydrated rows.
--  * mint_counts is NEVER stored (non-field property, empty at seed baseline).

-- ===================== META / TASK =====================
CREATE TABLE fixture_version(version TEXT PRIMARY KEY, git_sha TEXT, created_at TEXT, notes TEXT);

CREATE TABLE task(                               -- one row per 312 tasks; maps GymState scalar header
  task_id TEXT PRIMARY KEY,
  world_kind TEXT NOT NULL CHECK(world_kind IN ('shop','world')),  -- factory return contract: bare GymState vs WorldState
  category TEXT, difficulty TEXT, brief TEXT,    -- GymState.task_category/task_difficulty/task_brief
  start_path TEXT,                               -- START_PATHS[task_id] (not a GymState field; returned by /_harness/reset)
  current_user_id TEXT,                          -- GymState.current_user_id
  cart_applied_promo TEXT,                       -- Cart.applied_promo at seed
  schedule_now INTEGER NOT NULL DEFAULT 0,       -- ScheduleState.now at seed
  calendar_parity_locked INTEGER NOT NULL DEFAULT 0,  -- 1 => suppress the base calendar_parity rule (e.g. M10 pins make_calendarstate(0))
  action_log_json TEXT NOT NULL DEFAULT '[]',    -- GymState.action_log (list[dict], VOLATILE for hash but kept for asdict parity)
  flash_messages_json TEXT NOT NULL DEFAULT '[]' -- GymState.flash_messages (VOLATILE for hash, kept for parity)
);

-- ===================== SHOP CATALOG (scope base|task_id) =====================
CREATE TABLE product(                            -- Product (GymState.products dict; pos = insertion order, RENDER-load-bearing)
  fixture_version TEXT, scope TEXT, product_id TEXT, pos INTEGER,
  name TEXT, brand TEXT, category TEXT, base_price REAL, rating REAL,
  review_count INTEGER, stock INTEGER, image_emoji TEXT,
  short_description TEXT, long_description TEXT, is_subscribable INTEGER, weight_kg REAL,
  tags_json TEXT,                                -- Product.tags list[str]
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, product_id));
CREATE TABLE product_variant(                    -- ProductVariant (Product.variants ordered list)
  fixture_version TEXT, scope TEXT, product_id TEXT, variant_id TEXT, pos INTEGER,
  label TEXT, attributes_json TEXT, price_delta REAL, stock INTEGER,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, product_id, variant_id),
  FOREIGN KEY(fixture_version, scope, product_id) REFERENCES product(fixture_version, scope, product_id));
CREATE TABLE review(                             -- Review (Product.reviews ordered list)
  fixture_version TEXT, scope TEXT, product_id TEXT, review_id TEXT, pos INTEGER,
  author TEXT, rating INTEGER, title TEXT, body TEXT, verified_purchase INTEGER,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, product_id, review_id),
  FOREIGN KEY(fixture_version, scope, product_id) REFERENCES product(fixture_version, scope, product_id));
CREATE TABLE promotion(                          -- Promotion (GymState.promotions dict, PK=code)
  fixture_version TEXT, scope TEXT, code TEXT, pos INTEGER,
  name TEXT, description TEXT, discount_pct REAL, discount_flat REAL,
  applies_to_category TEXT, applies_to_product_id TEXT, min_purchase REAL,
  expired INTEGER, one_per_customer INTEGER, description_fineprint TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, code));
CREATE TABLE app_user(                           -- User (GymState.users dict; FULL dict hydrated, verifiers read all users)
  fixture_version TEXT, scope TEXT, user_id TEXT, pos INTEGER,
  email TEXT, password TEXT, full_name TEXT, two_fa_enabled INTEGER, loyalty_tier TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, user_id));
CREATE TABLE address(                            -- Address (User.addresses dict)
  fixture_version TEXT, scope TEXT, user_id TEXT, address_id TEXT, pos INTEGER,
  label TEXT, full_name TEXT, line1 TEXT, line2 TEXT, city TEXT, state TEXT, zip TEXT, is_default INTEGER,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, user_id, address_id),
  FOREIGN KEY(fixture_version, scope, user_id) REFERENCES app_user(fixture_version, scope, user_id));
CREATE TABLE payment_method(                     -- PaymentMethod (User.payment_methods dict)
  fixture_version TEXT, scope TEXT, user_id TEXT, payment_id TEXT, pos INTEGER,
  label TEXT, kind TEXT, is_default INTEGER, expires TEXT, nickname TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, user_id, payment_id),
  FOREIGN KEY(fixture_version, scope, user_id) REFERENCES app_user(fixture_version, scope, user_id));

-- ===================== SHOP SEEDED-MUTABLE (task-scoped; base = no rows) =====================
CREATE TABLE seed_shop_cart_item(                -- CartItem (Cart.items ORDERED list)
  task_id TEXT, pos INTEGER, item_id TEXT, product_id TEXT, variant_id TEXT,
  quantity INTEGER, gift_wrap INTEGER, gift_message TEXT, ship_to_address_id TEXT, scheduled_delivery TEXT,
  PRIMARY KEY(task_id, pos));
CREATE TABLE seed_order(                          -- Order (GymState.orders dict)
  task_id TEXT, order_id TEXT, pos INTEGER, user_id TEXT, placed_at TEXT,
  subtotal REAL, discount REAL, tax REAL, shipping REAL, total REAL,
  promo_code TEXT, payment_id TEXT, status TEXT, is_subscription INTEGER, subscription_id TEXT,
  PRIMARY KEY(task_id, order_id));
CREATE TABLE seed_order_item(                     -- OrderItem (Order.items ORDERED list; product_name/variant_label/unit_price are SNAPSHOTS, stored verbatim)
  task_id TEXT, order_id TEXT, pos INTEGER, item_id TEXT, product_id TEXT,
  product_name TEXT, variant_id TEXT, variant_label TEXT, quantity INTEGER, unit_price REAL,
  gift_wrap INTEGER, gift_message TEXT, ship_to_address_id TEXT, scheduled_delivery TEXT,
  PRIMARY KEY(task_id, order_id, pos),
  FOREIGN KEY(task_id, order_id) REFERENCES seed_order(task_id, order_id));
CREATE TABLE seed_shipment(                       -- Shipment (Order.shipments ORDERED list); item_ids ordered JSON
  task_id TEXT, order_id TEXT, pos INTEGER, shipment_id TEXT, tracking_number TEXT,
  carrier TEXT, status TEXT, estimated_delivery TEXT, item_ids_json TEXT,
  PRIMARY KEY(task_id, shipment_id),
  FOREIGN KEY(task_id, order_id) REFERENCES seed_order(task_id, order_id));
CREATE TABLE seed_shipment_event(                 -- ShipmentEvent (Shipment.events ORDERED list)
  task_id TEXT, shipment_id TEXT, pos INTEGER, timestamp TEXT, status TEXT, location TEXT, detail TEXT,
  PRIMARY KEY(task_id, shipment_id, pos),
  FOREIGN KEY(task_id, shipment_id) REFERENCES seed_shipment(task_id, shipment_id));
CREATE TABLE seed_return(                          -- ReturnRequest (GymState.returns dict); item_ids ordered JSON
  task_id TEXT, return_id TEXT, pos INTEGER, order_id TEXT, user_id TEXT, item_ids_json TEXT,
  reason TEXT, refund_method TEXT, status TEXT, created_at TEXT, notes TEXT,
  PRIMARY KEY(task_id, return_id));
CREATE TABLE seed_subscription(                   -- Subscription (GymState.subscriptions dict)
  task_id TEXT, subscription_id TEXT, pos INTEGER, user_id TEXT, product_id TEXT, variant_id TEXT,
  quantity INTEGER, cadence TEXT, deliveries_remaining INTEGER, next_delivery_date TEXT,
  address_id TEXT, payment_id TEXT, loyalty_discount_pct REAL, status TEXT,
  PRIMARY KEY(task_id, subscription_id));

-- ===================== MAIL (scope base|task_id) =====================
CREATE TABLE mail_state(                           -- MailState non-to_json fields MUST be sourced from the dataclass, not to_json
  fixture_version TEXT, scope TEXT, account_email TEXT, account_name TEXT, next_counter INTEGER,
  armed_bounce_json TEXT, armed_forged_market_failure_json TEXT,
  armed_forged_food_calendar_threat_json TEXT, armed_forged_coupon_confirmation_json TEXT,
  PRIMARY KEY(fixture_version, scope));
CREATE TABLE mail_email(                           -- Email; container = dict discriminator, folder = redundant dataclass field (BOTH stored)
  fixture_version TEXT, scope TEXT, container TEXT CHECK(container IN ('inbox','sent','drafts')),
  email_id TEXT, pos INTEGER, sender TEXT, to_addr TEXT, subject TEXT, body TEXT,
  received_at TEXT, received_label TEXT, read INTEGER, labels_json TEXT, folder TEXT,
  order_id TEXT, tracking_url TEXT, amount_total REAL, eta TEXT, product_id TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, container, email_id));

-- ===================== FOOD (scope base|task_id) =====================
CREATE TABLE food_state(                           -- FoodState non-to_json fields (defer_receipt_steps/enable_delivery_notes) + cart scalars + _next
  fixture_version TEXT, scope TEXT, next_counter INTEGER,
  defer_receipt_steps INTEGER, enable_delivery_notes INTEGER,
  cart_restaurant_id TEXT, cart_delivery_note TEXT,
  PRIMARY KEY(fixture_version, scope));
CREATE TABLE restaurant(                           -- Restaurant (FoodState.restaurants dict)
  fixture_version TEXT, scope TEXT, restaurant_id TEXT, pos INTEGER, name TEXT, cuisine TEXT,
  rating REAL, eta_label TEXT, delivery_fee REAL, emoji TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, restaurant_id));
CREATE TABLE dish(                                 -- Dish (Restaurant.dishes ORDERED list)
  fixture_version TEXT, scope TEXT, restaurant_id TEXT, dish_id TEXT, pos INTEGER,
  name TEXT, description TEXT, price REAL, tags_json TEXT, emoji TEXT, popular INTEGER,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, restaurant_id, dish_id),
  FOREIGN KEY(fixture_version, scope, restaurant_id) REFERENCES restaurant(fixture_version, scope, restaurant_id));
CREATE TABLE seed_food_cart_item(                  -- FoodCartItem (FoodCart.items ORDERED list; base=no rows)
  task_id TEXT, pos INTEGER, dish_id TEXT, restaurant_id TEXT, name TEXT, unit_price REAL, quantity INTEGER,
  PRIMARY KEY(task_id, pos));
CREATE TABLE seed_food_order(                      -- FoodOrder (FoodState.orders dict); restaurant_name is a SNAPSHOT
  task_id TEXT, order_id TEXT, pos INTEGER, restaurant_id TEXT, restaurant_name TEXT,
  subtotal REAL, delivery_fee REAL, total REAL, placed_at TEXT, eta_label TEXT, status TEXT, delivery_note TEXT,
  PRIMARY KEY(task_id, order_id));
CREATE TABLE seed_food_order_item(                 -- FoodCartItem inside FoodOrder.items ORDERED list
  task_id TEXT, order_id TEXT, pos INTEGER, dish_id TEXT, restaurant_id TEXT, name TEXT, unit_price REAL, quantity INTEGER,
  PRIMARY KEY(task_id, order_id, pos),
  FOREIGN KEY(task_id, order_id) REFERENCES seed_food_order(task_id, order_id));

-- ===================== CALENDAR (scope base|task_id) =====================
CREATE TABLE calendar_state(                       -- CalendarState non-to_json fields (account_name, _next)
  fixture_version TEXT, scope TEXT, account_name TEXT, next_counter INTEGER,
  PRIMARY KEY(fixture_version, scope));
CREATE TABLE calendar_event(                       -- CalendarEvent (seed-INVARIANT rows only; the seed%2 'Book club' event is a seed_rule, computed live)
  fixture_version TEXT, scope TEXT, event_id TEXT, pos INTEGER,
  title TEXT, day TEXT, day_label TEXT, start TEXT, end TEXT, source TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, event_id));

-- ===================== MARKET (scope base|task_id) =====================
CREATE TABLE market_state(                         -- MarketState config (store_name, fees) + _next + cart.applied_coupon
  fixture_version TEXT, scope TEXT, store_name TEXT, delivery_fee REAL, free_delivery_over REAL,
  next_counter INTEGER, cart_applied_coupon TEXT,
  PRIMARY KEY(fixture_version, scope));
CREATE TABLE market_product(                       -- MarketProduct (MarketState.products dict)
  fixture_version TEXT, scope TEXT, product_id TEXT, pos INTEGER, name TEXT, category TEXT,
  price REAL, emoji TEXT, description TEXT, in_stock INTEGER, shop_sku TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, product_id));
CREATE TABLE market_coupon(                        -- MarketCoupon (MarketState.coupons dict keyed by UPPER(code)); key AND code both stored
  fixture_version TEXT, scope TEXT, coupon_key TEXT, pos INTEGER, code TEXT,
  percent_off REAL, min_subtotal REAL, description TEXT, expired INTEGER,
  tombstone INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(fixture_version, scope, coupon_key));
CREATE TABLE seed_market_cart_item(                -- MarketCartItem (MarketCart.items ORDERED list; base=no rows)
  task_id TEXT, pos INTEGER, product_id TEXT, name TEXT, unit_price REAL, quantity INTEGER,
  PRIMARY KEY(task_id, pos));
CREATE TABLE seed_market_order(                     -- MarketOrder (MarketState.orders dict)
  task_id TEXT, order_id TEXT, pos INTEGER, subtotal REAL, discount REAL, delivery_fee REAL,
  total REAL, placed_at TEXT, coupon_code TEXT,
  PRIMARY KEY(task_id, order_id));
CREATE TABLE seed_market_order_item(               -- MarketCartItem inside MarketOrder.items ORDERED list
  task_id TEXT, order_id TEXT, pos INTEGER, product_id TEXT, name TEXT, unit_price REAL, quantity INTEGER,
  PRIMARY KEY(task_id, order_id, pos),
  FOREIGN KEY(task_id, order_id) REFERENCES seed_market_order(task_id, order_id));

-- ===================== CROSS-APP (task-scoped) =====================
CREATE TABLE seed_world_event(                     -- WorldEvent (WorldState.events APPEND-ONLY list; pos=emission index; id must equal evt_{pos+1})
  task_id TEXT, pos INTEGER, event_id TEXT, type TEXT, source_app TEXT, target_app TEXT,
  step INTEGER, payload_json TEXT, delivered INTEGER,
  PRIMARY KEY(task_id, pos));
CREATE TABLE seed_scheduled_event(                 -- ScheduledEvent (ScheduleState.queue list); fired/fired_at_step round-trip exactly (monotonic guard)
  task_id TEXT, pos INTEGER, event_id TEXT, emit_type TEXT, source_app TEXT, target_app TEXT,
  payload_json TEXT, fire_at_step INTEGER, after_event_type TEXT, delay_steps INTEGER,
  fired INTEGER, fired_at_step INTEGER,
  PRIMARY KEY(task_id, pos));

-- ===================== SEED RULES (seed-dependent values computed LIVE at hydrate, never table-looked-up) =====================
CREATE TABLE seed_rule(
  rule_id INTEGER PRIMARY KEY, scope TEXT, kind TEXT, target TEXT, args_json TEXT);
-- Row 1: kind='prng_uniform_round2', scope='A2/filter_laptop',
--        target='shop.products.p_laptop_studio.base_price', args={"min":799.0,"max":989.0,"ndigits":2}
--        => hydrate runs round(random.Random(seed).uniform(799.0,989.0),2), byte-exact for ANY seed.
-- Row 2: kind='calendar_parity', scope='base', target='calendar',
--        args={"mod":2,"eq":1,"event":{<CalendarEvent asdict for 'Book club' 19:00-21:30 tomorrow>}}
--        => hydrate inserts the event iff seed%2==1 AND task.calendar_parity_locked==0.

-- Entities with NO table (assembled in code, never stored): GymState, WorldState (built by hydrate from the
-- rows above, returning bare GymState when task.world_kind='shop' or WorldState when 'world'); Cart/FoodCart/
-- MarketCart/ScheduleState wrappers (reconstructed from their *_item / config rows); and every derived value
-- (products_count, unread_count, cart_count, cart_subtotal, schedule pending, calendar today/tomorrow,
-- current_user, mint_counts) — recomputed by the unchanged to_json / left as a non-field property.