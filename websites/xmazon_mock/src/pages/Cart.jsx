import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { bridged } from '../lib/bridge';
import { DEMO_PROMOS, gymNow } from '../lib/mockData';
import { Button } from '../components/ui/Button';
import { Tag } from 'lucide-react';

// The scheduled-delivery floor is the GYM's clock, not the wall clock. The world
// is frozen at 2026-05-21 and every delivery-date task asks for a day just after
// it, so a wall-clock floor put the whole task family months in the "past": the
// picker's `min` rejected the only correct answer and the clamp below silently
// rewrote it to the real today. Everything else that dates this world (Checkout,
// Orders, ProductDetail) already reads gymNow — this was the one holdout.
const worldTodayISO = (state) =>
  new Date(gymNow(state)).toISOString().slice(0, 10);

// set_line_options replaces the whole option set for a line, so every change has
// to resend all four fields — patch just the one that moved.
const lineOpts = (item, patch) => ({
  gift_wrap: !!item.gift_wrap,
  gift_message: item.gift_message || '',
  ship_to_address_id: item.ship_to_address_id || '',
  scheduled_delivery: item.scheduled_delivery || '',
  ...patch,
});

// Shared settle window for free-text / date fields that must not commit
// per-keystroke (engine round-trip + re-projection would fight the draft).
const SETTLE_MS = 700;

// The gift message is free text, so it needs a LOCAL draft: committing every
// keystroke to the engine round-trips per character (dead-feeling box) and the
// 2.5s re-projection would yank half-typed text back. Keep the draft here, and
// push to the engine on blur, settle-timer, or explicit Save — agents often
// type then click Checkout without a blur, which used to leave the stale note.
const GiftMessageField = ({ item, onCommit }) => {
  const [draft, setDraft] = useState(item.gift_message || '');
  const editing = useRef(false);
  const timer = useRef(null);
  const engineValue = item.gift_message || '';
  useEffect(() => {
    if (!editing.current) setDraft(engineValue);
  }, [engineValue]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const commit = (val) => {
    clearTimeout(timer.current);
    if ((engineValue || '') !== val) onCommit(val);
  };

  return (
    <div className="space-y-1">
      <textarea
        aria-label="Gift message"
        data-test-id={`input-gift-message-${item.productId}`}
        value={draft}
        placeholder="Add a gift message (optional)"
        onFocus={() => { editing.current = true; }}
        onChange={(e) => {
          const val = e.target.value;
          setDraft(val);
          clearTimeout(timer.current);
          timer.current = setTimeout(() => {
            editing.current = false;
            commit(val);
          }, SETTLE_MS);
        }}
        onBlur={() => {
          editing.current = false;
          commit(draft);
        }}
        rows={2}
        className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:border-xmazon-orange"
      />
      <button
        type="button"
        data-test-id={`btn-save-gift-message-${item.productId}`}
        onClick={() => {
          editing.current = false;
          commit(draft);
        }}
        className="text-xs text-xmazon-blue hover:underline"
      >
        Save gift message
      </button>
    </div>
  );
};

// A date box needs the same LOCAL draft as the gift message, and for a sharper
// reason: a native date input fires `change` on every segment, and once the box
// holds a value each of those intermediate events is a COMPLETE date. Committing
// them sent a garbage date to the engine mid-keystroke, and the re-projection
// then wrote that date back into this controlled input — so the second digit the
// annotator typed landed in a field that had just been reset under them, and
// typing a date was impossible. Only whole, settled dates reach the engine.
//
// Committing on blur alone would strand the value for an agent that types and
// never clicks away, so a settle timer commits too: one write per edit, from
// either driver, without the per-segment churn. SETTLE_MS is declared above and
// shared with the other free-text fields.

// A year out from the world's today. Long enough that no legitimate scheduled
// delivery is ever refused, short enough that the year field cannot run away.
const horizonFrom = (floorISO) => {
  const d = new Date((floorISO || '2026-01-01') + 'T00:00:00Z');
  if (Number.isNaN(d.getTime())) return '2027-12-31';
  d.setUTCFullYear(d.getUTCFullYear() + 1);
  return d.toISOString().slice(0, 10);
};

// The engine speaks ISO; the field shows mm/dd/yyyy. Kept module-level so the
// initial state and the sync effect use the same conversion the commit path does.
const isoToDisplay = (iso) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return iso || '';
  const [y, m, d] = iso.split('-');
  return `${m}/${d}/${y}`;
};

const ScheduledDeliveryField = ({ item, floor, onCommit }) => {
  const [draft, setDraft] = useState(isoToDisplay(item.scheduled_delivery || ''));
  const editing = useRef(false);
  const timer = useRef(null);
  const engineValue = item.scheduled_delivery || '';
  const horizon = horizonFrom(floor);

  useEffect(() => {
    if (!editing.current) setDraft(isoToDisplay(engineValue));
  }, [engineValue]);
  useEffect(() => () => clearTimeout(timer.current), []);

  // A date before the world's today can never be honored — the engine drops it
  // at checkout — so clamp up to the floor rather than posting a dead value.
  //
  // A date AFTER the horizon is the other half of the same problem, and it is
  // the one that actually bit: a native date input with no max accepts years up
  // to 275760, so an agent typing into the field produced "11/31/275760" and the
  // control took it. Nothing downstream would ever schedule that, and a delivery
  // task graded on "does this arrive before the party" reads a year-275760 date
  // as simply late, which looks like a reasoning failure and is not one.
  //
  // isValidISO also rejects dates that do not exist at all. The browser hands
  // back a value for 31 November because it validates the FIELDS, not the day
  // count for that month; round-tripping through Date is what catches it.
  const isValidISO = (v) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
    const d = new Date(v + "T00:00:00Z");
    return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
  };

  // Accept what a person would actually type. The displayed shape is mm/dd/yyyy,
  // so that is the primary form; ISO is accepted too because scripted callers
  // and the reference solver write yyyy-mm-dd.
  const toISO = (raw) => {
    const s = (raw || "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    const m = s.match(/^(\d{1,2})\s*\/\s*(\d{1,2})\s*\/\s*(\d{4})$/);
    if (!m) return "";
    const [, mm, dd, yyyy] = m;
    return `${yyyy}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
  };

  const toDisplay = isoToDisplay;

  const commit = (raw) => {
    clearTimeout(timer.current);
    // Clearing the field is a legitimate edit: it means "no scheduled date".
    if (!raw) {
      if (draft !== "") setDraft("");
      if (engineValue !== "") onCommit("");
      return;
    }
    const iso = toISO(raw);
    if (!iso || !isValidISO(iso)) {
      // Half-typed or impossible (31 November, month 13): hold what the engine
      // already has rather than posting nonsense.
      setDraft(toDisplay(engineValue));
      return;
    }
    let next = iso;
    if (next < floor) next = floor;
    if (next > horizon) next = horizon;
    setDraft(toDisplay(next));
    if (next !== engineValue) onCommit(next);
  };

  // A TEXT input, not type="date", and this is the whole point of the control.
  //
  // A native date input cannot be driven by typing: its value lives in segment
  // widgets, so keystrokes never reach it and .value stays empty. Verified every
  // way an agent might try - "05/22/2026", "05222026", "2026-05-22" - and all
  // three leave the field blank; only a programmatic .fill() works, and no agent
  // does that. Its picker is an OS-level widget headless Chromium will not open
  // either. So the one control this task turns on was impossible to operate, and
  // a model that typed the correct party date twice had both silently dropped
  // and was then marked down for a late delivery it had actually tried to set.
  //
  // Digits are masked to mm/dd/yyyy as they arrive, which is the 2/2/4 limit the
  // field needs: eight digits maximum, so the year cannot run to 275760.
  return (
    <input
      type="text"
      inputMode="numeric"
      autoComplete="off"
      placeholder="mm/dd/yyyy"
      maxLength={10}
      aria-label="Scheduled delivery date"
      value={draft}
      onFocus={() => { editing.current = true; }}
      onChange={(e) => {
        const raw = e.target.value || "";
        // An ISO value arrives whole, from a scripted .fill() rather than from
        // keystrokes. Masking it as mm/dd/yyyy would read 2026-05-22 as the
        // digits 20260522 and render "20/26/0522", so take it as-is.
        if (/^\d{4}-\d{2}-\d{2}$/.test(raw.trim())) {
          setDraft(raw.trim());
          clearTimeout(timer.current);
          timer.current = setTimeout(() => commit(raw.trim()), SETTLE_MS);
          return;
        }
        const digits = raw.replace(/\D/g, "").slice(0, 8);
        let masked = digits;
        if (digits.length > 4) {
          masked = `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
        } else if (digits.length > 2) {
          masked = `${digits.slice(0, 2)}/${digits.slice(2)}`;
        }
        setDraft(masked);
        clearTimeout(timer.current);
        // Only a complete mm/dd/yyyy is worth sending; a settle timer on a
        // half-typed date would keep bouncing the field back under the typist.
        if (digits.length === 8) {
          timer.current = setTimeout(() => commit(masked), SETTLE_MS);
        }
      }}
      onBlur={() => { editing.current = false; commit(draft); }}
      className="border rounded px-2 py-1 text-sm w-[130px] focus:outline-none focus:border-xmazon-orange"
    />
  );
};

export const Cart = () => {
  const { state, updateCartQty, removeFromCart, saveForLater, moveToCart, removeSavedItem, addToCart, setLineOptions, applyPromo } = useStore();
  const navigate = useNavigate();
  const [promoCode, setPromoCode] = useState('');
  const [appliedPromo, setAppliedPromo] = useState(null);
  const [promoError, setPromoError] = useState('');

  const subtotal = state.cart.reduce((acc, item) => {
    const product = state.products.find(p => p.id === item.productId);
    return acc + (product ? product.price * item.quantity : 0);
  }, 0);

  // The gym engine owns which promo code is valid and how much it takes off, so
  // derive the applied promo + discount from the adopted engine state instead of
  // a hardcoded SAVE10/10%. (Demo mode with no engine keeps the local code.)
  const promoDefs = (state._gym_promotions && state._gym_promotions.length) ? state._gym_promotions : DEMO_PROMOS;
  const enginePromoRaw = state._gym_cart_detail && state._gym_cart_detail.applied_promo;
  const enginePromoCode = enginePromoRaw
    ? (typeof enginePromoRaw === 'string' ? enginePromoRaw : (enginePromoRaw.code || null))
    : null;
  const effectivePromo = bridged() ? enginePromoCode : (state.appliedPromoCode || null);
  const promoDef = effectivePromo
    ? promoDefs.find(p => (p.code || '').toUpperCase() === effectivePromo.toUpperCase())
    : null;
  const discount = !effectivePromo ? 0
    : promoDef
      ? (promoDef.discount_flat ? Math.min(promoDef.discount_flat, subtotal) : subtotal * (promoDef.discount_pct || 0))
      : subtotal * 0.10; // demo fallback when no engine definition is present
  const promoLabel = promoDef
    ? (promoDef.discount_flat ? `$${promoDef.discount_flat} off` : `${Math.round((promoDef.discount_pct || 0) * 100)}% off`)
    : 'discount applied';
  const finalSubtotal = subtotal - discount;
  const totalItems = state.cart.reduce((acc, item) => acc + item.quantity, 0);
  const savedItems = state.savedForLater || [];

  const handleApplyPromo = () => {
    const code = promoCode.trim().toUpperCase();
    if (!code) { setPromoError('Enter a promo code'); return; }
    const res = applyPromo(code);
    if (res && typeof res.then === 'function') {
      // Bridged: the engine decides. apply_promo returns HTTP 303 whether it
      // accepted OR rejected the code, so read the engine's actual applied_promo
      // from the re-projected result rather than the status.
      res.then(r => {
        const ap = r && r.apps && r.apps.shop && r.apps.shop._gym_cart_detail
          && r.apps.shop._gym_cart_detail.applied_promo;
        const appliedCode = typeof ap === 'string' ? ap : (ap && ap.code) || null;
        if (appliedCode && appliedCode.toUpperCase() === code) { setAppliedPromo(code); setPromoError(''); }
        else { setAppliedPromo(null); setPromoError('That code is not valid for this cart.'); }
      });
    } else {
      // Demo (no engine): applyPromo validated the code and, if valid, stored it
      // in global state so Checkout applies the same discount. Reject unknowns.
      if (res && res.ok) { setPromoError(''); }
      else { setPromoError('That code is not valid.'); }
    }
  };

  // Recommended products from cart categories
  const cartCategories = [...new Set(state.cart.map(item => {
    const p = state.products.find(pr => pr.id === item.productId);
    return p ? p.category : null;
  }).filter(Boolean))];
  const cartProductIds = new Set(state.cart.map(i => i.productId));
  const recommendedProducts = state.products
    .filter(p => cartCategories.includes(p.category) && !cartProductIds.has(p.id))
    .slice(0, 6);

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[1500px] mx-auto p-4 flex flex-col md:flex-row gap-6">
        {/* Main Cart Area */}
        <div className="flex-1">
          <div className="bg-white p-6 mb-4">
            <h1 className="text-2xl font-medium border-b pb-4 mb-4">Shopping Cart</h1>

            {state.cart.length === 0 ? (
              <div className="py-8 text-center">
                <div className="text-4xl mb-4">🛒</div>
                <h2 className="text-2xl font-medium mb-2">Your xmazon Cart is empty</h2>
                <p className="text-sm text-gray-600 mb-4">Your shopping cart lives here. Add items you want to purchase.</p>
                <Link to="/" className="text-xmazon-blue hover:underline text-sm font-bold">Shop today's deals</Link>
              </div>
            ) : (
              <>
                {state.cart.map(item => {
                  const product = state.products.find(p => p.id === item.productId);
                  if (!product) return null;

                  return (
                    <div key={item.productId} className="flex gap-4 border-b py-4 last:border-0">
                      <Link to={`/product/${product.id}`}>
                        <img src={product.image} alt={product.title} className="w-32 h-32 object-contain" />
                      </Link>
                      <div className="flex-1">
                        <Link to={`/product/${product.id}`} className="text-base font-medium hover:text-xmazon-darkYellow hover:underline line-clamp-2 text-xmazon-blue">
                          {product.title}
                        </Link>
                        <div className={`text-sm my-1 ${product.inStock !== false ? 'text-green-700' : 'text-red-600'}`}>
                          {product.inStock !== false ? 'In Stock' : 'Currently Unavailable'}
                        </div>
                        {product.prime && <div className="text-[#00a8e1] font-bold italic text-xs mb-2">prime</div>}

                        <div className="flex items-center gap-4 text-sm mt-2">
                          <select
                            aria-label="Quantity"
                            value={item.quantity}
                            onChange={(e) => updateCartQty(item.productId, Number(e.target.value))}
                            className="p-1 border rounded bg-gray-50 shadow-sm text-sm"
                          >
                            {/* Always offer headroom above the current qty so the
                                selector can INCREASE past 10, not just cap there. */}
                            {[...Array(Math.max(Number(item.quantity) || 1, Math.min(product.stockCount ?? 99, Math.max(10, (Number(item.quantity) || 1) + 5))))].map((_, i) => (
                              <option key={i+1} value={i+1}>Qty: {i+1}</option>
                            ))}
                          </select>
                          <span className="text-gray-300">|</span>
                          <button
                            data-test-id={`btn-remove-${item.productId}`}
                            onClick={() => removeFromCart(item.productId)}
                            className="text-xmazon-blue hover:underline text-xs"
                          >Delete</button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => saveForLater(item.productId)} className="text-xmazon-blue hover:underline text-xs">Save for later</button>
                        </div>

                        {/* Gift options */}
                        <div className="mt-3 border-t pt-3 space-y-2">
                          <div className="text-xs font-bold text-gray-700">Gift options</div>
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              aria-label="Gift wrap this item"
                              checked={!!item.gift_wrap}
                              onChange={(e) => setLineOptions(item.productId,
                                lineOpts(item, { gift_wrap: e.target.checked }))}
                            />
                            <span>Gift wrap this item</span>
                          </label>
                          <div>
                            <label className="block text-xs text-gray-600 mb-1">Gift message</label>
                            <GiftMessageField
                              item={item}
                              onCommit={(msg) => setLineOptions(item.productId,
                                lineOpts(item, { gift_message: msg }))}
                            />
                          </div>
                          {/* Per-LINE destination. The order-level address still
                              applies to anything left on "Default", so one order
                              can ship its lines to different people. */}
                          <div>
                            <label className="block text-xs text-gray-600 mb-1">Ship this item to</label>
                            <select
                              aria-label="Ship this item to"
                              data-test-id={`select-ship-address-${item.productId}`}
                              value={item.ship_to_address_id || ''}
                              onChange={(e) => setLineOptions(item.productId,
                                lineOpts(item, { ship_to_address_id: e.target.value }))}
                              className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:border-xmazon-orange"
                            >
                              <option value="">Default address</option>
                              {(state.user?.addresses || []).map(a => (
                                <option key={a.id} value={a.id}>
                                  {a.fullName} — {a.street}, {a.city}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs text-gray-600 mb-1">Scheduled delivery date</label>
                            <ScheduledDeliveryField
                              item={item}
                              floor={worldTodayISO(state)}
                              onCommit={(val) => setLineOptions(item.productId,
                                lineOpts(item, { scheduled_delivery: val }))}
                            />
                          </div>
                        </div>
                      </div>
                      <div className="text-right font-bold text-base">
                        ${(product.price * item.quantity).toFixed(2)}
                      </div>
                    </div>
                  );
                })}

                <div className="text-right text-base mt-4">
                  Subtotal ({totalItems} {totalItems === 1 ? 'item' : 'items'}): <span className="font-bold">${subtotal.toFixed(2)}</span>
                </div>
              </>
            )}
          </div>

          {/* Saved for Later Section */}
          {savedItems.length > 0 && (
            <div className="bg-white p-6 mb-4">
              <h2 className="text-xl font-bold mb-4">Saved for later ({savedItems.length} {savedItems.length === 1 ? 'item' : 'items'})</h2>
              <div className="space-y-4">
                {savedItems.map(item => {
                  const product = state.products.find(p => p.id === item.productId);
                  if (!product) return null;

                  return (
                    <div key={item.productId} className="flex gap-4 border-b pb-4 last:border-0">
                      <Link to={`/product/${product.id}`}>
                        <img src={product.image} alt={product.title} className="w-24 h-24 object-contain" />
                      </Link>
                      <div className="flex-1">
                        <Link to={`/product/${product.id}`} className="font-medium hover:text-xmazon-darkYellow hover:underline line-clamp-2 text-xmazon-blue text-sm">
                          {product.title}
                        </Link>
                        <div className="text-red-700 font-bold text-sm my-1">${product.price.toFixed(2)}</div>
                        <div className={`text-xs mb-2 ${product.inStock !== false ? 'text-green-700' : 'text-red-600'}`}>
                          {product.inStock !== false ? 'In Stock' : 'Currently Unavailable'}
                        </div>

                        <div className="flex gap-4 text-xs">
                          <button onClick={() => moveToCart(item.productId)} className="text-xmazon-blue hover:underline">Move to Cart</button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => removeSavedItem(item.productId)} className="text-xmazon-blue hover:underline">Delete</button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Customers who bought items in your cart also bought */}
          {recommendedProducts.length > 0 && state.cart.length > 0 && (
            <div className="bg-white p-6">
              <h2 className="text-base font-bold mb-4">Customers who bought items in your cart also bought</h2>
              <div className="flex gap-4 overflow-x-auto pb-2">
                {recommendedProducts.map(p => (
                  <div key={p.id} className="flex-shrink-0 w-36 text-center">
                    <Link to={`/product/${p.id}`}>
                      <img src={p.image} alt={p.title} className="w-full h-32 object-contain mb-2" />
                      <div className="text-xs text-xmazon-blue hover:underline line-clamp-2 mb-1">{p.title}</div>
                    </Link>
                    <div className="text-sm font-bold">${p.price.toFixed(2)}</div>
                    <button
                      onClick={() => addToCart(p)}
                      className="mt-1 w-full bg-xmazon-yellow hover:bg-xmazon-darkYellow text-xs py-1 rounded-full border border-gray-300"
                    >
                      Add to Cart
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Checkout Sidebar */}
        {state.cart.length > 0 && (
          <div className="w-full md:w-80">
            <div className="bg-white p-4 shadow-sm sticky top-4">
              {effectivePromo && (
                <div className="bg-green-50 border border-green-200 text-green-700 text-sm p-2 rounded mb-3 flex items-center gap-1">
                  <Tag size={14} />
                  <span>Promo <strong>{effectivePromo}</strong> applied: <strong>{promoLabel}</strong></span>
                </div>
              )}
              <div className="text-base mb-1">
                Subtotal ({totalItems} {totalItems === 1 ? 'item' : 'items'}): <span className="font-bold">${subtotal.toFixed(2)}</span>
              </div>
              {effectivePromo && (
                <div className="text-sm text-green-700 mb-1">
                  Promo discount: -<span className="font-bold">${discount.toFixed(2)}</span>
                </div>
              )}
              {effectivePromo && (
                <div className="text-base font-bold mb-3">
                  Total: ${finalSubtotal.toFixed(2)}
                </div>
              )}
              <Button
                className="w-full mb-4"
                data-test-id="btn-proceed-checkout" onClick={() => navigate('/checkout')}
              >
                Proceed to checkout
              </Button>

              {/* Promo code section */}
              <div className="border-t pt-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={promoCode}
                    onChange={e => { setPromoCode(e.target.value); setPromoError(''); }}
                    placeholder="Enter promo code"
                    className="flex-1 border rounded px-2 py-1.5 text-sm focus:outline-none focus:border-xmazon-orange"
                  />
                  <button
                    onClick={handleApplyPromo}
                    className="bg-gray-100 hover:bg-gray-200 border rounded px-3 py-1.5 text-sm font-medium"
                  >
                    Apply
                  </button>
                </div>
                {promoError && <div className="text-red-600 text-xs mt-1">{promoError}</div>}
                {effectivePromo && (
                  <div className="text-green-700 text-xs mt-1">Promo code applied: {promoLabel}</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
