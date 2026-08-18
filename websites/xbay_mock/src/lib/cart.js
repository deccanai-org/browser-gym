import { bridged } from './bridge';

// Single source of truth for cart quantities.
//
// The authoritative quantity lives in two different places depending on mode:
// bridged mode gets it from the engine as state._gym_cart_detail (items keyed
// by product_id), demo mode keeps it in the state.cartQty map. Every surface
// that shows a count, a line total or a subtotal has to agree, so they all go
// through these helpers rather than each re-deriving it.

export function cartQtyOf(state, listingId) {
  if (bridged()) {
    const detail = (state && state._gym_cart_detail) || [];
    const line = detail.find(it => it.product_id === listingId);
    return line ? Math.max(1, line.quantity || 1) : 1;
  }
  const qty = state && state.cartQty && state.cartQty[listingId];
  return Math.max(1, qty || 1);
}

// Total number of UNITS in the cart (3 of one item = 3, not 1). This is what a
// shopper means by "items in cart", and what the navbar badge should show.
export function cartUnitCount(state) {
  const ids = (state && state.cart) || [];
  return ids.reduce((n, id) => n + cartQtyOf(state, id), 0);
}

// Unit price for a listing, tolerating the several shapes the seed uses.
export function unitPriceOf(listing) {
  if (!listing) return 0;
  return listing.buyItNowPrice || listing.price || listing.currentBid || 0;
}

// Money helper: keep cart math off binary-float cents.
export function money(n) {
  return Math.round((Number(n) || 0) * 100) / 100;
}

// Resolve the applied coupon against the catalog and price it. Used by both the
// cart display and the checkout reducer so the total the shopper was shown is
// the total the order is written for.
export function resolveCoupon(state, subtotal) {
  const raw = state && state.coupon;
  if (!raw) return { code: null, coupon: null, valid: false, discount: 0 };
  const code = typeof raw === 'string' ? raw : (raw.code || raw.id || null);
  if (!code) return { code: null, coupon: null, valid: false, discount: 0 };
  const coupon = ((state && state._gym_coupons) || []).find(
    c => String(c.code).toUpperCase() === String(code).toUpperCase());
  const valid = !!coupon && !coupon.expired && subtotal >= (coupon.min_subtotal || 0);
  return {
    code,
    coupon: coupon || null,
    // Whether it discounts THIS cart right now. The banner keys off this, so a
    // coupon that stops qualifying (cart dropped below its minimum, expired)
    // can't keep claiming to be applied while the total sits at full price.
    valid,
    discount: valid ? money(subtotal * (coupon.percent_off || 0)) : 0,
  };
}

// Split a cart-level amount (a discount, a delivery fee) across lines in
// proportion to their weights, in whole cents, giving any rounding remainder to
// the largest line. The shares then sum to EXACTLY the input, so the orders a
// checkout writes always add up to the total the shopper was shown.
export function allocate(amount, weights) {
  const cents = Math.round((Number(amount) || 0) * 100);
  const total = weights.reduce((s, w) => s + w, 0);
  if (!cents || total <= 0) return weights.map(() => 0);
  const raw = weights.map(w => Math.floor((cents * w) / total));
  let remainder = cents - raw.reduce((s, c) => s + c, 0);
  // Hand out the leftover cents to the heaviest lines first.
  const order = weights.map((w, i) => i).sort((a, b) => weights[b] - weights[a]);
  for (let k = 0; remainder > 0; k = (k + 1) % order.length, remainder--) {
    raw[order[k]] += 1;
  }
  return raw.map(c => c / 100);
}

// Delivery mirrors the engine (server/apps/market/state.py delivery_for): it is
// charged on the PRE-discount subtotal, so applying a coupon never silently
// removes free shipping.
const DEFAULT_DELIVERY_FEE = 5.99;
const DEFAULT_FREE_DELIVERY_OVER = 35.0;

export function deliveryFor(state, subtotal) {
  const s = Number(subtotal) || 0;
  if (s <= 0) return 0;
  const fee = (state && state.deliveryFee != null) ? Number(state.deliveryFee) : DEFAULT_DELIVERY_FEE;
  const over = (state && state.freeDeliveryOver != null)
    ? Number(state.freeDeliveryOver) : DEFAULT_FREE_DELIVERY_OVER;
  return s >= over ? 0 : money(fee);
}

// The one pricing function: subtotal - discount + delivery, matching the
// engine's quote() exactly so the number the shopper approves is the number the
// order is written for.
export function priceCart(state, subtotal) {
  const { code, coupon, valid, discount } = resolveCoupon(state, subtotal);
  const delivery = deliveryFor(state, subtotal);
  return {
    code, coupon, valid, discount, delivery,
    subtotal: money(subtotal),
    total: money(Math.max(0, subtotal - discount) + delivery),
  };
}
