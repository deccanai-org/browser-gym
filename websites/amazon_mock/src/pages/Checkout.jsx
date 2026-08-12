import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { MapPin, CreditCard, Check } from 'lucide-react';
import { bridged, bridgeAct } from '../lib/bridge';
import { gymNow, DEMO_PROMOS } from '../lib/mockData';

export const Checkout = () => {
  const { state, placeOrder } = useStore();
  const navigate = useNavigate();
  // Skip the redundant address-selection step when a default address is already
  // on file (the shopper can still click "Change" to revisit it).
  const _hasDefaultAddr = (state.user.addresses || []).some(a => a.isDefault);
  const [step, setStep] = useState(_hasDefaultAddr ? 2 : 1);
  const [loading, setLoading] = useState(false);
  const [selectedAddressId, setSelectedAddressId] = useState(
    (state.user.addresses && state.user.addresses.length > 0
      ? state.user.addresses.find(a => a.isDefault) || state.user.addresses[0]
      : state.user.address).id || 'addr1'
  );
  const [selectedPmId, setSelectedPmId] = useState(
    (state.user.paymentMethods && state.user.paymentMethods.length > 0
      ? state.user.paymentMethods.find(p => p.isDefault) || state.user.paymentMethods[0]
      : state.user.paymentMethod).id || 'pm1'
  );

  const addresses = state.user.addresses || [state.user.address];
  const paymentMethods = state.user.paymentMethods || [state.user.paymentMethod];
  const selectedAddress = addresses.find(a => a.id === selectedAddressId) || addresses[0] || state.user.address;
  const selectedPm = paymentMethods.find(p => p.id === selectedPmId) || paymentMethods[0] || state.user.paymentMethod;

  const money = (n) => Math.round((Number(n) || 0) * 100) / 100;
  const subtotal = money(state.cart.reduce((acc, item) => {
    const product = state.products.find(p => p.id === item.productId);
    return acc + (product ? product.price * item.quantity : 0);
  }, 0));
  // Mirror the Cart's promo math so the two pages agree: the engine owns which
  // code is applied and how much it takes off (_gym_cart_detail.applied_promo +
  // _gym_promotions). Ignoring it and taxing the full subtotal made Checkout
  // quote a higher total than the Cart for the same cart.
  const promoDefs = (state._gym_promotions && state._gym_promotions.length) ? state._gym_promotions : DEMO_PROMOS;
  const enginePromoRaw = state._gym_cart_detail && state._gym_cart_detail.applied_promo;
  const enginePromoCode = enginePromoRaw
    ? (typeof enginePromoRaw === 'string' ? enginePromoRaw : (enginePromoRaw.code || null))
    : null;
  // Bridged: the engine owns the applied code. Demo: it's in global state
  // (set by applyPromo), so Checkout charges the same discount the Cart showed.
  const appliedPromoCode = bridged() ? enginePromoCode : (state.appliedPromoCode || null);
  const promoDef = appliedPromoCode
    ? promoDefs.find(p => (p.code || '').toUpperCase() === appliedPromoCode.toUpperCase())
    : null;
  const discount = money(!appliedPromoCode ? 0
    : promoDef
      ? (promoDef.discount_flat ? Math.min(promoDef.discount_flat, subtotal) : subtotal * (promoDef.discount_pct || 0))
      : subtotal * 0.10); // demo fallback, same as the Cart
  const discountedSubtotal = money(subtotal - discount);
  // Mirror the engine's place_order math so the quoted total == the amount
  // actually charged (was: 8% tax, $0 shipping, no gift-wrap fee).
  const SHIPPING_FLAT = 5.99;
  const GIFT_WRAP_FEE = 4.99;
  const shipping = subtotal > 0 ? SHIPPING_FLAT : 0;
  const giftWrapCount = state.cart.filter(i => i.gift_wrap).length;
  const giftWrapFee = money(giftWrapCount * GIFT_WRAP_FEE);
  const tax = money(discountedSubtotal * 0.085);
  const total = money(discountedSubtotal + shipping + giftWrapFee + tax);

  const handlePlaceOrder = async () => {
    if (loading) return;
    setLoading(true);
    try {
      // Honor a scheduled delivery date the customer picked in the cart (the
      // latest, since the order arrives when the last item does), ignoring any
      // in the past; otherwise default to the frozen-clock now + 5 days.
      const today = new Date(gymNow(state)).toISOString().split('T')[0];
      const scheduled = state.cart
        .map(i => i.scheduled_delivery)
        .filter(d => d && d >= today)
        .sort();
      const estimatedDelivery = scheduled.length
        ? scheduled[scheduled.length - 1]
        : new Date(gymNow(state) + 5 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const orderData = {
        items: state.cart,
        total: total,
        shippingAddress: selectedAddress,
        paymentMethod: selectedPm,
        trackingNumber: null,
        estimatedDelivery
      };
      // No fake delay in bridged mode — oracle/agents click Place order and
      // immediately need the engine order to exist for the next milestone.
      const orderId = await placeOrder(orderData);
      navigate(`/order-confirmation/${orderId}`);
    } finally {
      setLoading(false);
    }
  };

  // One CTA drives the whole flow so the sidebar MIRRORS the current step instead
  // of showing a premature "Place your order": step 1 confirms the address, step 2
  // the payment, step 3 places the order. Keeps the real engine actions intact.
  const advance = () => {
    if (loading) return;
    if (step === 1) {
      // placeOrder only posts payment_id, so the engine resolves ship-to from the
      // account default — commit the chosen address before moving on.
      if (bridged() && selectedAddressId) {
        bridgeAct('shop.set_default_address', { address_id: selectedAddressId });
      }
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    } else {
      handlePlaceOrder();
    }
  };
  const ctaLabel = loading
    ? (step === 3 ? 'Placing Order...' : 'Working...')
    : step === 1 ? 'Use this address'
      : step === 2 ? 'Use this payment method'
        : 'Place your order';

  if (state.cart.length === 0) {
    return (
      <div className="max-w-[600px] mx-auto p-8 text-center">
        <div className="text-4xl mb-4">🛒</div>
        <h2 className="text-2xl font-medium mb-2">Your cart is empty</h2>
        <p className="text-sm text-gray-600 mb-6">Add items to your cart before checking out.</p>
        <Link to="/" className="inline-block bg-[#ffd814] hover:bg-[#f7ca00] px-6 py-2 rounded-lg font-bold text-[13px] border border-[#fcd200]">
          Shop now
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-[1000px] mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-medium">Checkout</h1>
        <div className="text-gray-500">
          <span className={step >= 1 ? "text-xmazon-darkYellow font-bold" : ""}>Shipping</span>
          <span className="mx-1">›</span>
          <span className={step >= 2 ? "text-xmazon-darkYellow font-bold" : ""}>Payment</span>
          <span className="mx-1">›</span>
          <span className={step >= 3 ? "text-xmazon-darkYellow font-bold" : ""}>Review</span>
        </div>
      </div>

      <div className="flex gap-8 flex-col-reverse md:flex-row">
        <div className="flex-1 space-y-4">
          {/* Step 1: Shipping */}
          <div className={`bg-white p-4 border rounded ${step === 1 ? 'border-xmazon-orange shadow-md' : ''}`}>
            <div className="flex justify-between mb-2">
              <h2 className="font-bold text-lg flex items-center gap-2">
                {step > 1 && <Check size={16} className="text-green-600" />}
                1. Shipping Address
              </h2>
              {step > 1 && <button onClick={() => setStep(1)} className="text-xmazon-blue text-sm hover:underline">Change</button>}
            </div>
            {step === 1 ? (
              <div>
                <div className="space-y-3 mb-4">
                  {addresses.map((addr, idx) => (
                    <label
                      key={addr.id || idx}
                      className={`flex gap-3 p-3 border rounded cursor-pointer hover:border-xmazon-orange transition-colors ${selectedAddressId === addr.id ? 'border-xmazon-orange bg-orange-50' : ''}`}
                    >
                      <input
                        type="radio"
                        name="address"
                        value={addr.id}
                        checked={selectedAddressId === addr.id}
                        onChange={() => setSelectedAddressId(addr.id)}
                        className="mt-1 accent-xmazon-orange flex-shrink-0"
                      />
                      <div className="text-sm">
                        <div className="flex items-center gap-2">
                          <MapPin size={14} className="text-gray-500" />
                          <span className="font-bold">{addr.fullName}</span>
                          {addr.label && <span className="text-xs font-medium text-gray-700">{addr.label}</span>}
                          {addr.isDefault && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">Default</span>}
                        </div>
                        <div className="text-gray-600 mt-1">{addr.street}</div>
                        <div className="text-gray-600">{addr.city}, {addr.state} {addr.zip}</div>
                        <div className="text-gray-600">{addr.country}</div>
                      </div>
                    </label>
                  ))}
                </div>
                <Button data-test-id="btn-use-address" onClick={advance}>Use this address</Button>
              </div>
            ) : (
              <div className="text-sm text-gray-600 flex items-center gap-2">
                <MapPin size={14} className="text-gray-400" />
                {selectedAddress.street}, {selectedAddress.city}, {selectedAddress.state}
              </div>
            )}
          </div>

          {/* Step 2: Payment */}
          <div className={`bg-white p-4 border rounded ${step === 2 ? 'border-xmazon-orange shadow-md' : ''}`}>
            <div className="flex justify-between mb-2">
              <h2 className="font-bold text-lg flex items-center gap-2">
                {step > 2 && <Check size={16} className="text-green-600" />}
                2. Payment Method
              </h2>
              {step > 2 && <button onClick={() => setStep(2)} className="text-xmazon-blue text-sm hover:underline">Change</button>}
            </div>
            {step === 2 ? (
              <div>
                <div className="space-y-3 mb-4">
                  {paymentMethods.map((pm, idx) => (
                    <label
                      key={pm.id || idx}
                      className={`flex gap-3 p-3 border rounded cursor-pointer hover:border-xmazon-orange transition-colors ${selectedPmId === pm.id ? 'border-xmazon-orange bg-orange-50' : ''}`}
                    >
                      <input
                        type="radio"
                        name="payment"
                        value={pm.id}
                        checked={selectedPmId === pm.id}
                        onChange={() => setSelectedPmId(pm.id)}
                        className="mt-1 accent-xmazon-orange flex-shrink-0"
                      />
                      <div className="text-sm">
                        <div className="flex items-center gap-2">
                          <CreditCard size={14} className="text-gray-500" />
                          <span className="font-bold">{pm.brand}{(pm.brand !== 'PayPal' && pm.last4 && pm.last4 !== '0000') ? ` ending in ${pm.last4}` : ''}</span>
                          {pm.isDefault && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">Default</span>}
                        </div>
                        {/* Expiry is deliberately NOT shown at review — it lives
                            on the payments page (Profile). A whole family of
                            tasks turns on whether the agent goes and checks the
                            card it is about to use; printing the date here hands
                            over the answer and defuses them. */}
                      </div>
                    </label>
                  ))}
                </div>
                <Button data-test-id="btn-use-payment" onClick={advance}>Use this payment method</Button>
              </div>
            ) : (
              step > 2 && (
                <div className="text-sm text-gray-600 flex items-center gap-2">
                  <CreditCard size={14} className="text-gray-400" />
                  {selectedPm.brand}{(selectedPm.brand !== 'PayPal' && selectedPm.last4 && selectedPm.last4 !== '0000') ? ` ending in ${selectedPm.last4}` : ''}
                </div>
              )
            )}
          </div>

          {/* Step 3: Review */}
          <div className={`bg-white p-4 border rounded ${step === 3 ? 'border-xmazon-orange shadow-md' : ''}`}>
            <h2 className="font-bold text-lg mb-4">3. Review items and shipping</h2>
            {step === 3 && (
              <div>
                {state.cart.map(item => {
                  const product = state.products.find(p => p.id === item.productId);
                  if (!product) return null;
                  return (
                    <div key={item.productId} className="flex gap-4 mb-4 border p-2 rounded">
                      <img src={product.image} alt={product.title} className="w-16 h-16 object-contain" />
                      <div>
                        <div className="font-bold text-sm">{product.title}</div>
                        <div className="text-sm text-red-700 font-bold">${product.price.toFixed(2)}</div>
                        <div className="text-sm">Qty: {item.quantity}</div>
                      </div>
                    </div>
                  );
                })}
                <div className="border-t pt-4 mt-4">
                  <Button data-test-id="btn-place-order" onClick={advance} className="w-full md:w-auto" disabled={loading}>
                    {loading ? 'Placing Order...' : 'Place your order'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Order Summary Sidebar */}
        <div className="w-full md:w-72">
          <div className="bg-white p-4 border rounded sticky top-4">
            {/* Contextual step CTA — mirrors the current step, so "Place your
                order" only appears at review (steps 1/2 show Use this address /
                Use this payment method) instead of a persistent grayed button. */}
            {/* Only expose Place-order test-id / enabled CTA at review (step 3).
                Earlier steps use btn-use-address / btn-use-payment in the form. */}
            <Button
              data-test-id={step >= 3 ? 'btn-place-order' : undefined}
              onClick={advance}
              className="w-full mb-4"
              disabled={step < 3 || loading}
            >
              {step >= 3 ? (loading ? 'Placing Order...' : 'Place your order') : ctaLabel}
            </Button>
            <div className="flex items-center justify-center gap-1 text-[11px] text-gray-500 mb-3">
              <span className={step >= 1 ? 'font-bold text-xmazon-darkYellow' : ''}>Address</span>
              <span>›</span>
              <span className={step >= 2 ? 'font-bold text-xmazon-darkYellow' : ''}>Payment</span>
              <span>›</span>
              <span className={step >= 3 ? 'font-bold text-xmazon-darkYellow' : ''}>Place order</span>
            </div>
            {step === 3 && (
              <p className="text-xs text-gray-500 mb-4">
                By placing your order, you agree to ShopGym's privacy notice and conditions of use.
              </p>
            )}
            <h3 className="font-bold text-lg mb-2">Order Summary</h3>
            <div className="text-sm space-y-1">
              <div className="flex justify-between"><span>Items:</span> <span>${subtotal.toFixed(2)}</span></div>
              <div className="flex justify-between"><span>Shipping:</span> <span>${shipping.toFixed(2)}</span></div>
              {giftWrapFee > 0 && (
                <div className="flex justify-between"><span>Gift wrap ({giftWrapCount}):</span> <span>${giftWrapFee.toFixed(2)}</span></div>
              )}
              {discount > 0 && (
                <div className="flex justify-between text-green-700">
                  <span>Promo{appliedPromoCode ? ` (${appliedPromoCode})` : ''}:</span> <span>-${discount.toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between"><span>Tax:</span> <span>${tax.toFixed(2)}</span></div>
              <div className="flex justify-between border-t pt-1 font-bold text-red-700 text-lg">
                <span>Order Total:</span> <span>${total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
