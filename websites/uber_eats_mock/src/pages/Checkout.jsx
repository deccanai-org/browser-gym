import React, { useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { MapPin, Clock, CreditCard, Check } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { bridged } from '../lib/bridge';
import { formatCurrency } from '../utils/dataManager';
import './Checkout.css';

const TIP_OPTIONS = [15, 18, 20, 25];

export default function Checkout() {
  const {
    state,
    placeOrder,
    setTip,
    applyPromoCode,
    updateAddress,
    updateDefaultPayment,
    addPaymentMethod,
    updateDeliveryInstructions,
  } = useApp();
  const navigate = useNavigate();
  const [promoInput, setPromoInput] = useState('');
  const [promoError, setPromoError] = useState('');
  const [editing, setEditing] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [addingCard, setAddingCard] = useState(false);
  const [newCard, setNewCard] = useState({ label: '', cardNumber: '', expiry: '' });
  const [showCustomTip, setShowCustomTip] = useState(false);
  const [customTip, setCustomTip] = useState('');

  const { cart, user, restaurants } = state;
  const restaurant = restaurants.find(r => r.id === cart.restaurantId);
  // Pickup makes it a pickup order: no delivery address/instructions, no delivery
  // fee, pickup ETA. Scheduled time (from the header Now/Later picker) shows here.
  const isPickup = state.ui.deliveryMode === 'pickup';
  const scheduledTime = state.ui.scheduledTime;
  const selectedAddress = user.addresses.find(a => a.id === state.ui.selectedAddressId) || user.addresses[0];
  const selectedPayment = user.paymentMethods.find(p => p.id === user.defaultPaymentId) || user.paymentMethods[0];

  const handleAddCard = () => {
    const digits = (newCard.cardNumber || '').replace(/\D/g, '');
    if (digits.length < 4 && !newCard.label.trim()) return;
    addPaymentMethod({ label: newCard.label.trim(), cardNumber: digits, expiry: newCard.expiry.trim() });
    setNewCard({ label: '', cardNumber: '', expiry: '' });
    setAddingCard(false);
    setEditing(null);
  };

  // The engine stores the applied promo in state.appliedPromoCode and the code
  // list (with percentOff) in state.promotions — derive the chip + discount from
  // those so an applied code actually shows and reduces the total.
  const appliedCode = state.appliedPromoCode || cart.promoCode || '';
  const appliedPromo = appliedCode
    ? (state.promotions || []).find(p => (p.code || '').toUpperCase() === appliedCode.toUpperCase())
    : null;

  const totals = useMemo(() => {
    const subtotal = cart.items.reduce((s, item) => s + item.totalPrice, 0);
    const serviceFee = Math.min(Math.max(subtotal * 0.15, 0.99), 9.99);
    const deliveryFee = (restaurant && !isPickup) ? restaurant.deliveryFee : 0;
    const tax = subtotal * 0.09;
    const promoDiscount = appliedPromo
      ? Math.round(subtotal * (appliedPromo.percentOff || 0) * 100) / 100
      : (cart.promoDiscount || 0);
    // food.checkout has no tip field — the engine never records or charges a tip.
    // In bridged mode force it to 0 so the displayed total isn't a figure the
    // gym will never see (the tip selector is hidden below in the same mode).
    const tipAmount = bridged()
      ? 0
      : (cart.tipPercentage ? subtotal * (cart.tipPercentage / 100) : cart.tipAmount);
    const total = subtotal + serviceFee + deliveryFee + tax + tipAmount - promoDiscount;
    return {
      subtotal,
      serviceFee,
      deliveryFee,
      tax,
      tipAmount,
      promoDiscount,
      total,
    };
  }, [cart, restaurant, isPickup, appliedPromo]);

  if (!cart.items.length) {
    return (
      <div className="checkout-empty">
        <h2>Your cart is empty</h2>
        <p>Add items from a restaurant to checkout</p>
        <Link to="/" className="checkout-empty__btn">Browse restaurants</Link>
      </div>
    );
  }

  const handleApplyPromo = (e) => {
    e.preventDefault();
    setPromoError('');
    const result = applyPromoCode(promoInput.trim());
    if (result === false || result?.error) {
      setPromoError(typeof result === 'object' ? result.error : 'Invalid promo code');
    }
  };

  const handlePlaceOrder = async () => {
    if (!selectedAddress) return;
    setPlacing(true);
    // placeOrder is async in bridged mode; awaiting a plain value is a no-op
    // in legacy mode. Without the await we navigated to /orders/undefined.
    const orderId = await placeOrder({});
    navigate(orderId ? `/orders/${orderId}` : '/orders');
  };

  return (
    <div className="checkout">
      <h1 className="checkout__title">Checkout</h1>

      <div className="checkout__layout">
        <div className="checkout__main">
          {/* Delivery / Pickup details */}
          <section className="checkout__section">
            <h2 className="checkout__section-title">{isPickup ? 'Pickup details' : 'Delivery details'}</h2>

            {isPickup ? (
              <div className="checkout__card">
                <div className="checkout__row">
                  <MapPin size={20} />
                  <div className="checkout__row-content">
                    <strong>{restaurant ? `Pick up at ${restaurant.name}` : 'Pickup'}</strong>
                    <span className="checkout__row-sub">
                      {restaurant?.address ? restaurant.address : 'Show this order at the counter when you arrive'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="checkout__card">
                <div className="checkout__row">
                  <MapPin size={20} />
                  <div className="checkout__row-content">
                    <strong>{selectedAddress?.label || 'Address'}</strong>
                    <span className="checkout__row-sub">
                      {selectedAddress
                        ? `${selectedAddress.street}${selectedAddress.apt ? `, ${selectedAddress.apt}` : ''}, ${selectedAddress.city}`
                        : 'No address selected'}
                    </span>
                  </div>
                  <button className="checkout__edit-btn" onClick={() => setEditing(editing === 'address' ? null : 'address')}>
                    Edit
                  </button>
                </div>
                {editing === 'address' && (
                  <div className="checkout__picker">
                    <div className="checkout__picker-title">Choose address</div>
                    {user.addresses.map(addr => (
                      <button
                        key={addr.id}
                        className={`checkout__picker-option ${addr.id === selectedAddress?.id ? 'checkout__picker-option--active' : ''}`}
                        onClick={() => { updateAddress(addr.id); setEditing(null); }}
                      >
                        {addr.id === selectedAddress?.id && <Check size={16} />}
                        <div className="checkout__picker-info">
                          <strong>{addr.label}</strong>
                          <span>{addr.street}{addr.apt ? `, ${addr.apt}` : ''}, {addr.city}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* When: reflects the header Now/Later choice, else ASAP / pickup ETA */}
            <div className="checkout__card">
              <div className="checkout__row">
                <Clock size={20} />
                <div className="checkout__row-content">
                  <strong>{scheduledTime ? 'Scheduled' : (isPickup ? 'Ready for pickup' : 'ASAP')}</strong>
                  <span className="checkout__row-sub">
                    {scheduledTime
                      ? scheduledTime.label
                      : isPickup
                        ? `${restaurant?.pickupTimeMin ?? 10}-${restaurant?.pickupTimeMax ?? 20} min`
                        : (restaurant ? `${restaurant.deliveryTimeMin}-${restaurant.deliveryTimeMax} min` : '25-40 min')}
                  </span>
                </div>
              </div>
            </div>

            {!isPickup && (
              <div className="checkout__card">
                <label className="checkout__instructions-label" htmlFor="delivery-instructions">
                  Delivery instructions
                </label>
                <textarea
                  id="delivery-instructions"
                  className="checkout__instructions-input"
                  placeholder="Gate code, landmark, etc."
                  value={cart.deliveryInstructions || ''}
                  onChange={(e) => updateDeliveryInstructions(e.target.value)}
                  rows={2}
                />
              </div>
            )}
          </section>

          {/* Payment */}
          <section className="checkout__section">
            <h2 className="checkout__section-title">Payment</h2>
            <div className="checkout__card">
              <div className="checkout__row">
                <CreditCard size={20} />
                <div className="checkout__row-content">
                  <strong>{selectedPayment?.label || 'Payment method'}</strong>
                  <span className="checkout__row-sub">
                    {selectedPayment?.type === 'paypal' ? 'PayPal' : `•••• ${selectedPayment?.last4 || '4242'}`}
                  </span>
                </div>
                <button className="checkout__edit-btn" onClick={() => setEditing(editing === 'payment' ? null : 'payment')}>
                  Edit
                </button>
              </div>
              {editing === 'payment' && (
                <div className="checkout__picker">
                  <div className="checkout__picker-title">Choose payment</div>
                  {user.paymentMethods.map(pm => (
                    <button
                      key={pm.id}
                      className={`checkout__picker-option ${pm.id === selectedPayment?.id ? 'checkout__picker-option--active' : ''}`}
                      onClick={() => { updateDefaultPayment(pm.id); setEditing(null); }}
                    >
                      {pm.id === selectedPayment?.id && <Check size={16} />}
                      <div className="checkout__picker-info">
                        <strong>{pm.label}</strong>
                        {pm.last4 ? <span>•••• {pm.last4}</span> : null}
                      </div>
                    </button>
                  ))}
                  {!addingCard ? (
                    <button
                      onClick={() => setAddingCard(true)}
                      style={{ width: '100%', textAlign: 'left', padding: '10px 12px', marginTop: 4, border: '1px dashed #cbd5e1', borderRadius: 8, background: 'transparent', color: '#06803a', fontWeight: 600, cursor: 'pointer' }}
                    >
                      + Add payment method
                    </button>
                  ) : (
                    <div style={{ padding: 12, border: '1px solid #e5e7eb', borderRadius: 8, marginTop: 4, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <input
                        placeholder="Card number" inputMode="numeric"
                        value={newCard.cardNumber}
                        onChange={e => setNewCard(c => ({ ...c, cardNumber: e.target.value }))}
                        style={{ padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
                      />
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          placeholder="MM/YY"
                          value={newCard.expiry}
                          onChange={e => setNewCard(c => ({ ...c, expiry: e.target.value }))}
                          style={{ flex: 1, padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
                        />
                        <input
                          placeholder="Label (optional)"
                          value={newCard.label}
                          onChange={e => setNewCard(c => ({ ...c, label: e.target.value }))}
                          style={{ flex: 1, padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
                        />
                      </div>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => { setAddingCard(false); setNewCard({ label: '', cardNumber: '', expiry: '' }); }}
                          style={{ padding: '8px 14px', border: '1px solid #d1d5db', borderRadius: 999, background: '#fff', cursor: 'pointer' }}
                        >Cancel</button>
                        <button
                          onClick={handleAddCard}
                          disabled={(newCard.cardNumber || '').replace(/\D/g, '').length < 4 && !newCard.label.trim()}
                          style={{ padding: '8px 14px', border: 'none', borderRadius: 999, background: '#000', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
                        >Add card</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Promo */}
          <section className="checkout__section">
            <h2 className="checkout__section-title">Promo code</h2>
            {appliedCode ? (
              <div className="checkout__promo-applied">
                <span className="checkout__promo-code">{appliedCode}</span>
                <span className="checkout__promo-save">−{formatCurrency(totals.promoDiscount)}</span>
              </div>
            ) : (
              <form className="checkout__promo-form" onSubmit={handleApplyPromo}>
                <input
                  className="checkout__promo-input"
                  value={promoInput}
                  onChange={(e) => setPromoInput(e.target.value)}
                  placeholder="Enter promo code"
                />
                <button type="submit" className="checkout__promo-btn">Apply</button>
              </form>
            )}
            {promoError && <p className="checkout__promo-error">{promoError}</p>}
          </section>

          {/* Tip — hidden in bridged mode: the gym engine's food.checkout has no
              tip field, so a courier tip can't be recorded or charged there. */}
          {!bridged() && (
            <section className="checkout__section">
              <h2 className="checkout__section-title">Tip your courier</h2>
              <div className="checkout__tips">
                {TIP_OPTIONS.map(pct => (
                  <button
                    key={pct}
                    className={`checkout__tip-btn ${!showCustomTip && cart.tipPercentage === pct ? 'checkout__tip-btn--active' : ''}`}
                    onClick={() => { setShowCustomTip(false); setTip(0, pct); }}
                  >
                    {pct}%
                  </button>
                ))}
                <button
                  className={`checkout__tip-btn ${showCustomTip ? 'checkout__tip-btn--active' : ''}`}
                  onClick={() => { setShowCustomTip(v => !v); if (!showCustomTip) { const v = parseFloat(customTip); setTip(isNaN(v) ? 0 : v, null); } }}
                >
                  Other
                </button>
                <button
                  className={`checkout__tip-btn ${!showCustomTip && !cart.tipPercentage && !cart.tipAmount ? 'checkout__tip-btn--active' : ''}`}
                  onClick={() => { setShowCustomTip(false); setCustomTip(''); setTip(0, null); }}
                >
                  None
                </button>
              </div>
              {showCustomTip && (
                <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
                  <span style={{ fontWeight: 700 }}>$</span>
                  <input
                    type="number" min="0" step="0.5" inputMode="decimal" autoFocus
                    placeholder="Custom tip amount"
                    value={customTip}
                    onChange={e => { setCustomTip(e.target.value); const v = parseFloat(e.target.value); setTip(isNaN(v) ? 0 : v, null); }}
                    style={{ flex: 1, padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
                  />
                </div>
              )}
            </section>
          )}

          {/* Items */}
          <section className="checkout__section">
            <h2 className="checkout__section-title">Your items</h2>
            {restaurant && <p className="checkout__rest-name">{restaurant.name}</p>}
            <div className="checkout__items">
              {cart.items.map(item => (
                <div key={item.id} className="checkout__item">
                  <span className="checkout__item-qty">{item.quantity}</span>
                  <div className="checkout__item-info">
                    <span className="checkout__item-name">{item.name}</span>
                    {item.selectedOptions?.length > 0 && (
                      <span className="checkout__item-opts">
                        {item.selectedOptions.map(o => o.optionName).join(', ')}
                      </span>
                    )}
                  </div>
                  <span className="checkout__item-price">{formatCurrency(item.totalPrice)}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="checkout__sidebar">
          <div className="checkout__totals">
            <div className="checkout__total-row">
              <span>Subtotal</span>
              <span>{formatCurrency(totals.subtotal)}</span>
            </div>
            <div className="checkout__total-row">
              <span>Service fee</span>
              <span>{formatCurrency(totals.serviceFee)}</span>
            </div>
            {!isPickup && (
              <div className="checkout__total-row">
                <span>Delivery fee</span>
                <span>{formatCurrency(totals.deliveryFee)}</span>
              </div>
            )}
            <div className="checkout__total-row">
              <span>Tax</span>
              <span>{formatCurrency(totals.tax)}</span>
            </div>
            {!bridged() && (
              <div className="checkout__total-row">
                <span>Tip</span>
                <span>{formatCurrency(totals.tipAmount)}</span>
              </div>
            )}
            {totals.promoDiscount > 0 && (
              <div className="checkout__total-row checkout__total-row--discount">
                <span>Promo</span>
                <span>−{formatCurrency(totals.promoDiscount)}</span>
              </div>
            )}
            <div className="checkout__total-row checkout__total-row--final">
              <span>Total</span>
              <span>{formatCurrency(totals.total)}</span>
            </div>
          </div>

          <button
            className="checkout__place-btn"
            onClick={handlePlaceOrder}
            disabled={placing || !selectedAddress}
          >
            Place Order — {formatCurrency(totals.total)}
          </button>
          <p className="checkout__terms">
            By placing your order, you agree to the terms of service.
          </p>
        </aside>
      </div>
    </div>
  );
}
