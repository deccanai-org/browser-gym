import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { bridged } from '../lib/bridge';
import { DEMO_PROMOS } from '../lib/mockData';
import { Button } from '../components/ui/Button';
import { Tag } from 'lucide-react';

// The scheduled-delivery floor deliberately tracks the REAL calendar date (not
// the gym's frozen 2026-05-21 clock): a delivery must not be schedulable before
// the actual current day. Local date, so it matches the shopper's own calendar.
const realTodayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

// set_line_options replaces the whole option set for a line, so every change has
// to resend all four fields — patch just the one that moved.
const lineOpts = (item, patch) => ({
  gift_wrap: !!item.gift_wrap,
  gift_message: item.gift_message || '',
  ship_to_address_id: item.ship_to_address_id || '',
  scheduled_delivery: item.scheduled_delivery || '',
  ...patch,
});

// The gift message is free text, so it needs a LOCAL draft: committing every
// keystroke to the engine round-trips per character (dead-feeling box) and the
// 2.5s re-projection would yank half-typed text back. Keep the draft here, and
// only push to the engine on blur. Adopt engine updates only while unfocused so
// the poll can't overwrite what the user is mid-typing.
const GiftMessageField = ({ item, onCommit }) => {
  const [draft, setDraft] = useState(item.gift_message || '');
  const editing = useRef(false);
  useEffect(() => {
    if (!editing.current) setDraft(item.gift_message || '');
  }, [item.gift_message]);
  return (
    <textarea
      aria-label="Gift message"
      value={draft}
      placeholder="Add a gift message (optional)"
      onFocus={() => { editing.current = true; }}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        editing.current = false;
        if ((item.gift_message || '') !== draft) onCommit(draft);
      }}
      rows={2}
      className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:border-xmazon-orange"
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
                <h2 className="text-2xl font-medium mb-2">Your ShopGym Cart is empty</h2>
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
                          <button onClick={() => removeFromCart(item.productId)} className="text-xmazon-blue hover:underline text-xs">Delete</button>
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
                            <input
                              type="date"
                              aria-label="Scheduled delivery date"
                              min={realTodayISO()}
                              value={item.scheduled_delivery || ''}
                              onChange={(e) => {
                                // The native `min` only soft-warns, so a date
                                // typed before the real current day is hard-
                                // rejected here — clamped up to today.
                                const today = realTodayISO();
                                const picked = e.target.value;
                                const val = picked && picked < today ? today : picked;
                                setLineOptions(item.productId, lineOpts(item, { scheduled_delivery: val }));
                              }}
                              className="border rounded px-2 py-1 text-sm focus:outline-none focus:border-xmazon-orange"
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
                onClick={() => navigate('/checkout')}
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
