import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

// Checkout for the System-B (AppContext) app. The mock shipped without a checkout
// page even though CartPanel navigates to /checkout; this fills that gap using the
// existing placeOrder() action so the cart -> order flow completes.
const card = { background: '#fff', border: '1px solid #eee', borderRadius: 12, padding: 16, marginBottom: 16 };
const h2 = { fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#888', marginBottom: 8 };
const btn = { background: '#06C167', color: '#fff', border: 'none', borderRadius: 999, padding: '14px 24px', fontSize: 16, fontWeight: 700, cursor: 'pointer', width: '100%' };

export default function CheckoutPage() {
  const navigate = useNavigate();
  const { state, placeOrder } = useApp();
  const cart = state.cart || { items: [] };
  const items = cart.items || [];
  const restaurant = (state.restaurants || []).find(r => r.id === cart.restaurantId);
  const subtotal = items.reduce((s, it) => s + (it.totalPrice || 0), 0);
  const deliveryFee = restaurant ? (restaurant.deliveryFee || 0) : 0;
  const serviceFee = items.length ? Math.min(Math.max(subtotal * 0.15, 0.99), 9.99) : 0;
  const tax = subtotal * 0.09;
  const total = subtotal + deliveryFee + serviceFee + tax;

  const addrs = state.user?.addresses || [];
  const addr = addrs.find(a => a.id === (state.ui?.selectedAddressId || state.user?.defaultAddressId)) || addrs[0];
  const pays = state.user?.paymentMethods || [];
  const pay = pays.find(p => p.id === state.user?.defaultPaymentId) || pays[0];

  if (items.length === 0) {
    return (
      <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Checkout</h1>
        <p style={{ color: '#666', margin: '12px 0 20px' }}>Your cart is empty.</p>
        <button onClick={() => navigate('/')} style={btn}>Browse restaurants</button>
      </div>
    );
  }

  const handlePlace = () => {
    placeOrder({});
    navigate('/orders');
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Checkout</h1>
      {restaurant && <p style={{ color: '#666', marginBottom: 16 }}>Order from <b>{restaurant.name}</b></p>}

      <section style={card}>
        <h2 style={h2}>Delivery address</h2>
        <p>{addr ? `${addr.street}${addr.apt ? ', ' + addr.apt : ''}, ${addr.city}, ${addr.state} ${addr.zip}` : 'No address on file'}</p>
      </section>

      <section style={card}>
        <h2 style={h2}>Payment</h2>
        <p>{pay ? pay.label : 'No payment method'}</p>
      </section>

      <section style={card}>
        <h2 style={h2}>Your items</h2>
        {items.map((it, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
            <span>{it.quantity}× {it.name}</span>
            <span>${(it.totalPrice || 0).toFixed(2)}</span>
          </div>
        ))}
        <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #eee' }} />
        {[['Subtotal', subtotal], ['Delivery fee', deliveryFee], ['Service fee', serviceFee], ['Tax', tax]].map(([l, v]) => (
          <div key={l} style={{ display: 'flex', justifyContent: 'space-between', color: '#666', padding: '2px 0' }}>
            <span>{l}</span><span>${Number(v).toFixed(2)}</span>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginTop: 8, fontSize: 18 }}>
          <span>Total</span><span>${total.toFixed(2)}</span>
        </div>
      </section>

      <button onClick={handlePlace} style={btn}>Place order · ${total.toFixed(2)}</button>
    </div>
  );
}
