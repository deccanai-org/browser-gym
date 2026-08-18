import React from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Minus, Plus, Trash2, ShoppingBag } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { formatCurrency } from '../utils/dataManager';
import './CartPanel.css';

export default function CartPanel({ isOpen, onClose }) {
  const { state, removeFromCart, updateCartItemQuantity } = useApp();
  const navigate = useNavigate();

  if (!isOpen) return null;

  const { items, restaurantId, restaurantName } = state.cart;
  const subtotal = items.reduce((s, item) => s + item.totalPrice, 0);
  const restaurant = (state.restaurants || []).find(r => r.id === restaurantId);
  const menuItems = state.menuItems || [];
  let cartArrivalLabel = null;
  let bestMins = -1;
  for (const it of items) {
    const mi = menuItems.find(m => m.id === it.menuItemId);
    const label = mi?.etaLabel;
    if (!label) continue;
    const m = String(label).trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (!m) {
      if (!cartArrivalLabel) cartArrivalLabel = label;
      continue;
    }
    let h = parseInt(m[1], 10) % 12;
    if (m[3].toUpperCase() === 'PM') h += 12;
    const mins = h * 60 + parseInt(m[2], 10);
    if (mins >= bestMins) {
      bestMins = mins;
      cartArrivalLabel = label;
    }
  }
  if (!cartArrivalLabel) cartArrivalLabel = restaurant?.etaLabel || null;

  const handleCheckout = () => {
    onClose();
    navigate('/checkout');
  };

  return (
    <div className="cart-overlay" data-test-id="cart-overlay" onClick={onClose}>
      <div className="cart-panel animate-slideInRight" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="cart-panel__header">
          <h2 className="cart-panel__title">Your cart</h2>
          <button className="cart-panel__close" data-test-id="btn-close-cart" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {items.length === 0 ? (
          <div className="cart-panel__empty">
            <div className="cart-panel__empty-icon">
              <ShoppingBag size={40} />
            </div>
            <h3 className="cart-panel__empty-title">Your cart is empty</h3>
            <p className="cart-panel__empty-text">Add items from a restaurant to start your order</p>
            <button className="cart-panel__browse-btn" data-test-id="btn-cart-browse" onClick={onClose}>
              Start browsing
            </button>
          </div>
        ) : (
          <>
            {/* Restaurant name */}
            {restaurantName && (
              <div className="cart-panel__restaurant">
                <span className="cart-panel__restaurant-label">From</span>
                <span className="cart-panel__restaurant-name">{restaurantName}</span>
              </div>
            )}

            {/* Items */}
            <div className="cart-panel__items">
              {items.map((item) => {
                const lineId = item.cartItemId ?? item.id;
                const qty = item.quantity ?? 1;
                const opts = item.selectedOptions || [];
                return (
                <div key={lineId} className="cart-item">
                  <div className="cart-item__info">
                    <div className="cart-item__name">{item.name}</div>
                    {opts.length > 0 && (
                      <div className="cart-item__options">
                        {opts.map(o => o.optionName).join(', ')}
                      </div>
                    )}
                    {item.specialInstructions && (
                      <div className="cart-item__instructions">"{item.specialInstructions}"</div>
                    )}
                  </div>
                  <div className="cart-item__right">
                    <div className="cart-item__price">{formatCurrency(item.totalPrice)}</div>
                    <div className="cart-item__qty-controls">
                      <button
                        type="button"
                        className="cart-item__qty-btn"
                        aria-label={qty <= 1 ? `Remove ${item.name} from cart` : `Decrease quantity of ${item.name}`}
                        data-test-id={`btn-cart-dec-${lineId}`}
                        onClick={() => updateCartItemQuantity(lineId, qty - 1)}
                      >
                        {qty === 1 ? <Trash2 size={14} /> : <Minus size={14} />}
                      </button>
                      <span className="cart-item__qty">{qty}</span>
                      <button
                        type="button"
                        className="cart-item__qty-btn"
                        aria-label={`Increase quantity of ${item.name}`}
                        data-test-id={`btn-cart-inc-${lineId}`}
                        onClick={() => updateCartItemQuantity(lineId, qty + 1)}
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                  </div>
                </div>
                );
              })}
            </div>

            {/* Footer */}
            <div className="cart-panel__footer">
              {cartArrivalLabel && (
                <div className="cart-panel__subtotal" style={{ marginBottom: 8 }}>
                  <span>Estimated arrival</span>
                  <span className="cart-panel__subtotal-amount">~{cartArrivalLabel}</span>
                </div>
              )}
              <div className="cart-panel__subtotal">
                <span>Subtotal</span>
                <span className="cart-panel__subtotal-amount">{formatCurrency(subtotal)}</span>
              </div>
              <button
                className="cart-panel__checkout-btn"
                data-test-id="btn-go-to-checkout"
                onClick={handleCheckout}
              >
                Go to Checkout
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
