import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { cartQtyOf, unitPriceOf, money, priceCart } from '../lib/cart';
import { Trash2, X, Check, ShoppingCart } from 'lucide-react';

const ADDRESS_FIELDS = [
  { key: 'fullName', label: 'Full name' },
  { key: 'street', label: 'Street address' },
  { key: 'city', label: 'City' },
  { key: 'state', label: 'State / region' },
  { key: 'zip', label: 'ZIP or postal code' },
];
const COUNTRIES = ['United States', 'Canada', 'United Kingdom', 'Australia', 'Germany', 'Japan'];
const CARD_BRANDS = ['Visa', 'Mastercard', 'American Express', 'PayPal'];

const EMPTY_ADDRESS = { fullName: '', street: '', city: '', state: '', zip: '', country: COUNTRIES[0] };

export default function Cart() {
  const navigate = useNavigate();
  const { state, removeFromCart, clearCart, updateQty, applyCoupon, removeCoupon, checkout,
          addAddress, addPaymentMethod } = useStore();
  const [couponInput, setCouponInput] = useState('');
  const [couponMsg, setCouponMsg] = useState('');
  const [checkedOut, setCheckedOut] = useState(false);

  // Ship-to address + payment method (from the engine in bridged mode, from the
  // seed in demo). Default to the account defaults.
  const addresses = state.addresses || [];
  const paymentMethods = state.paymentMethods || [];
  const [selectedAddressId, setSelectedAddressId] = useState(
    state.defaultAddressId || (addresses[0] && addresses[0].id) || '');
  const [selectedPaymentId, setSelectedPaymentId] = useState(
    state.defaultPaymentId || (paymentMethods[0] && paymentMethods[0].id) || '');

  const [showAddressForm, setShowAddressForm] = useState(false);
  const [addressForm, setAddressForm] = useState(EMPTY_ADDRESS);
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [paymentForm, setPaymentForm] = useState({ brand: CARD_BRANDS[0], number: '', expiry: '' });

  const handleSaveAddress = () => {
    if (!addressForm.fullName.trim() || !addressForm.street.trim() || !addressForm.city.trim()) return;
    const saved = addAddress({ ...addressForm });
    setSelectedAddressId(saved.id);
    setAddressForm(EMPTY_ADDRESS);
    setShowAddressForm(false);
  };

  const handleSavePayment = () => {
    const isPaypal = paymentForm.brand === 'PayPal';
    const digits = paymentForm.number.replace(/\D/g, '');
    if (!isPaypal && digits.length < 4) return;
    const last4 = digits.slice(-4);
    const saved = addPaymentMethod({
      brand: paymentForm.brand,
      last4,
      expiry: paymentForm.expiry,
      label: isPaypal ? 'PayPal' : `${paymentForm.brand} •••• ${last4}`,
    });
    setSelectedPaymentId(saved.id);
    setPaymentForm({ brand: CARD_BRANDS[0], number: '', expiry: '' });
    setShowPaymentForm(false);
  };

  const cartIds = state.cart || [];
  const cartListings = cartIds
    .map(id => state.listings.find(l => l.id === id))
    .filter(Boolean);

  // The engine may expose the applied coupon as a plain code string or an
  // object; normalize to a display code either way.
  const rawCoupon = state.coupon;
  const couponCode = rawCoupon
    ? (typeof rawCoupon === 'string' ? rawCoupon : (rawCoupon.code || rawCoupon.id || 'Applied'))
    : null;

  // Per-line quantity, from the one shared helper so the cart page, the navbar
  // badge and the dropdown can never disagree.
  const qtyOf = (id) => cartQtyOf(state, id);

  const priceOf = (l) => unitPriceOf(l);
  const subtotal = money(cartListings.reduce((sum, l) => sum + priceOf(l) * qtyOf(l.id), 0));
  // Units, not lines — "3 items in cart" when one item is in the cart 3 times.
  const unitCount = cartListings.reduce((n, l) => n + qtyOf(l.id), 0);

  // The banner used to say "applied" while Total stayed at the full subtotal.
  // Price the cart through the shared function the checkout reducer also uses,
  // so the order is written for exactly the total shown here — including the
  // delivery fee the engine charges on carts under the free-shipping threshold.
  const { coupon, valid: couponValid, discount, delivery, total } = priceCart(state, subtotal);

  const handleApplyCoupon = (e) => {
    e.preventDefault();
    const code = couponInput.trim();
    if (!code) return;
    // Validate against the coupon catalog before applying, so an unknown/expired
    // code shows an error instead of a green "applied" banner with no discount.
    const def = (state._gym_coupons || []).find(
      c => String(c.code).toUpperCase() === code.toUpperCase());
    if (!def) { setCouponMsg('That code is not valid.'); return; }
    if (def.expired) { setCouponMsg('That coupon has expired.'); return; }
    if (subtotal < (def.min_subtotal || 0)) {
      setCouponMsg(`Spend at least $${def.min_subtotal} to use this coupon.`); return;
    }
    setCouponMsg('');
    applyCoupon(code);
    setCouponInput('');
  };

  const canCheckout = cartListings.length > 0 && !!selectedAddressId && !!selectedPaymentId;

  const handleCheckout = () => {
    if (!canCheckout) return;
    checkout(selectedAddressId, selectedPaymentId);
    setCheckedOut(true);
    setTimeout(() => navigate('/dashboard'), 1200);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <ShoppingCart size={24} /> Shopping Cart
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Cart items */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            {cartListings.length > 0 && (
              <div className="flex justify-between items-center p-4 border-b border-gray-100">
                <span className="text-sm font-bold text-gray-700">
                  {unitCount} item{unitCount !== 1 ? 's' : ''} in cart
                </span>
                <button
                  type="button"
                  aria-label="Clear cart"
                  onClick={() => clearCart()}
                  className="text-sm font-bold text-gray-500 hover:text-red-500 flex items-center gap-1"
                >
                  <Trash2 size={16} /> Clear cart
                </button>
              </div>
            )}
            {cartListings.length === 0 ? (
              <div className="p-10 text-center text-gray-500">
                <p className="mb-4">Your cart is empty.</p>
                <Link to="/" className="text-xbay-blue font-bold hover:underline">Continue shopping</Link>
              </div>
            ) : (
              <ul>
                {cartListings.map(item => (
                  <li
                    key={item.id}
                    className="flex items-center gap-4 p-4 border-b border-gray-100 last:border-0"
                  >
                    <img
                      src={item.images[0]}
                      alt={item.title}
                      className="w-20 h-20 object-cover rounded bg-gray-100 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/item/${item.id}`}
                        className="font-medium text-gray-900 hover:text-xbay-blue line-clamp-2"
                      >
                        {item.title}
                      </Link>
                      <div className="text-sm text-gray-500">Condition: {item.condition}</div>
                      <div className="text-sm text-gray-500">${priceOf(item).toFixed(2)} each</div>
                    </div>
                    <div className="flex items-center border border-gray-300 rounded shrink-0">
                      <button
                        type="button"
                        aria-label={`Decrease quantity of ${item.title}`}
                        onClick={() => updateQty(item.id, qtyOf(item.id) - 1)}
                        disabled={qtyOf(item.id) <= 1}
                        className="px-2.5 py-1 text-lg font-bold text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        −
                      </button>
                      <input
                        type="number"
                        min="1"
                        aria-label={`Quantity of ${item.title}`}
                        value={qtyOf(item.id)}
                        onChange={(e) => updateQty(item.id, Math.max(1, parseInt(e.target.value, 10) || 1))}
                        className="w-10 text-center border-x border-gray-300 py-1 text-sm font-medium focus:outline-none"
                      />
                      <button
                        type="button"
                        aria-label={`Increase quantity of ${item.title}`}
                        onClick={() => updateQty(item.id, qtyOf(item.id) + 1)}
                        className="px-2.5 py-1 text-lg font-bold text-gray-600 hover:bg-gray-100"
                      >
                        +
                      </button>
                    </div>
                    <div className="font-bold text-gray-900 shrink-0 w-20 text-right">
                      ${(priceOf(item) * qtyOf(item.id)).toFixed(2)}
                    </div>
                    <button
                      type="button"
                      aria-label={`Remove ${item.title} from cart`}
                      onClick={() => removeFromCart(item.id)}
                      className="text-gray-400 hover:text-red-500 shrink-0 p-1"
                    >
                      <Trash2 size={18} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Summary + coupon + checkout */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
            <h2 className="font-bold text-gray-900 mb-4">Order Summary</h2>

            <div className="flex justify-between text-sm text-gray-700 mb-2">
              <span>Items ({unitCount})</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>

            {/* Coupon */}
            <div className="border-t border-gray-100 mt-4 pt-4">
              {(couponCode && coupon && couponValid) ? (
                <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded px-3 py-2 text-sm">
                  <span className="text-green-800 font-medium flex items-center gap-1">
                    <Check size={14} /> Coupon “{couponCode}” applied
                  </span>
                  <button
                    type="button"
                    aria-label="Remove coupon"
                    onClick={removeCoupon}
                    className="text-gray-500 hover:text-red-500"
                  >
                    <X size={16} />
                  </button>
                </div>
              ) : (
                <form onSubmit={handleApplyCoupon} className="flex gap-2">
                  <input
                    type="text"
                    aria-label="Coupon code"
                    value={couponInput}
                    onChange={e => setCouponInput(e.target.value)}
                    placeholder="Coupon code"
                    className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-xbay-blue focus:outline-none"
                  />
                  <button
                    type="submit"
                    aria-label="Apply coupon"
                    className="bg-gray-800 text-white px-4 py-2 rounded text-sm font-bold hover:bg-gray-900 whitespace-nowrap"
                  >
                    Apply coupon
                  </button>
                </form>
              )}
              {couponMsg && (
                <div className="text-red-600 text-xs mt-2" role="alert">{couponMsg}</div>
              )}
            </div>

            {discount > 0 && (
              <div className="flex justify-between text-sm text-green-700 mt-2">
                <span>Discount ({couponCode})</span>
                <span>-${discount.toFixed(2)}</span>
              </div>
            )}
            {cartListings.length > 0 && (
              <div className="flex justify-between text-sm text-gray-700 mt-2">
                <span>Delivery</span>
                {delivery > 0
                  ? <span>${delivery.toFixed(2)}</span>
                  : <span className="text-green-700 font-medium">Free</span>}
              </div>
            )}
            <div className="border-t border-gray-100 mt-4 pt-4 flex justify-between font-bold text-gray-900 mb-4">
              <span>Total</span>
              <span>${total.toFixed(2)}</span>
            </div>

            {/* Ship-to address. Both sections render unconditionally: when the
                account has nothing on file the picker used to disappear, so an
                order could be placed with no address and no payment method. */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-bold text-gray-600">Ship to</label>
                <button
                  type="button"
                  onClick={() => setShowAddressForm(v => !v)}
                  className="text-xs font-medium text-xbay-blue hover:underline"
                >
                  {showAddressForm ? 'Cancel' : 'Add a new address'}
                </button>
              </div>
              {addresses.length > 0 ? (
                <select
                  aria-label="Shipping address"
                  value={selectedAddressId}
                  onChange={e => setSelectedAddressId(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-2 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                >
                  {addresses.map(a => (
                    <option key={a.id} value={a.id}>
                      {a.fullName} — {a.street}, {a.city} {a.state} {a.zip}
                    </option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-gray-500">No address on file. Add one to check out.</p>
              )}

              {showAddressForm && (
                <div className="mt-2 space-y-2 border border-gray-200 rounded p-3 bg-gray-50">
                  {ADDRESS_FIELDS.map(f => (
                    <input
                      key={f.key}
                      aria-label={f.label}
                      placeholder={f.label}
                      value={addressForm[f.key]}
                      onChange={e => setAddressForm({ ...addressForm, [f.key]: e.target.value })}
                      className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                    />
                  ))}
                  <select
                    aria-label="Country"
                    value={addressForm.country}
                    onChange={e => setAddressForm({ ...addressForm, country: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                  >
                    {COUNTRIES.map(c => <option key={c}>{c}</option>)}
                  </select>
                  <button
                    type="button"
                    onClick={handleSaveAddress}
                    className="w-full bg-xbay-blue text-white text-sm font-bold rounded py-2 hover:bg-blue-700"
                  >
                    Save address
                  </button>
                </div>
              )}
            </div>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-bold text-gray-600">Pay with</label>
                <button
                  type="button"
                  onClick={() => setShowPaymentForm(v => !v)}
                  className="text-xs font-medium text-xbay-blue hover:underline"
                >
                  {showPaymentForm ? 'Cancel' : 'Add a payment method'}
                </button>
              </div>
              {paymentMethods.length > 0 ? (
                <select
                  aria-label="Payment method"
                  value={selectedPaymentId}
                  onChange={e => setSelectedPaymentId(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-2 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                >
                  {paymentMethods.map(p => (
                    <option key={p.id} value={p.id}>{p.label || p.brand}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-gray-500">No payment method on file. Add one to check out.</p>
              )}

              {showPaymentForm && (
                <div className="mt-2 space-y-2 border border-gray-200 rounded p-3 bg-gray-50">
                  <select
                    aria-label="Card brand"
                    value={paymentForm.brand}
                    onChange={e => setPaymentForm({ ...paymentForm, brand: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                  >
                    {CARD_BRANDS.map(c => <option key={c}>{c}</option>)}
                  </select>
                  {paymentForm.brand !== 'PayPal' && (
                    <>
                      <input
                        aria-label="Card number"
                        placeholder="Card number"
                        inputMode="numeric"
                        value={paymentForm.number}
                        onChange={e => setPaymentForm({ ...paymentForm, number: e.target.value })}
                        className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                      />
                      <input
                        aria-label="Expiry"
                        placeholder="MM/YY"
                        value={paymentForm.expiry}
                        onChange={e => setPaymentForm({ ...paymentForm, expiry: e.target.value })}
                        className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-xbay-blue"
                      />
                    </>
                  )}
                  <button
                    type="button"
                    onClick={handleSavePayment}
                    className="w-full bg-xbay-blue text-white text-sm font-bold rounded py-2 hover:bg-blue-700"
                  >
                    Save payment method
                  </button>
                </div>
              )}
            </div>

            {checkedOut ? (
              <div className="text-center text-green-700 font-bold py-2 flex items-center justify-center gap-2">
                <Check size={18} /> Order placed!
              </div>
            ) : (
              <>
                <button
                  type="button"
                  aria-label="Checkout"
                  onClick={handleCheckout}
                  disabled={!canCheckout}
                  className="w-full bg-xbay-blue text-white px-6 py-3 rounded-full font-bold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Checkout
                </button>
                {cartListings.length > 0 && !canCheckout && (
                  <p className="mt-2 text-xs text-center text-red-600">
                    Choose a shipping address and a payment method to continue.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
