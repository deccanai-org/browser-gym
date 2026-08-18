import React from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Minus, Plus, Trash2, ShoppingBag } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { formatCurrency } from '../utils/dataManager';
import './CartPanel.css';

export default function CartPanel({ isOpen, onClose }) {
  const { state, removeFromCart, updateCartItemQuantity, clearCart } = useApp();
  const navigate = useNavigate();

  if (!isOpen) return null;

  const { items, restaurantId, restaurantName } = state.cart;
  const subtotal = items.reduce((s, item) => s + item.totalPrice, 0);

  const handleCheckout = () => {
    onClose();
    navigate('/checkout');
  };

  return (
    <div className="cart-overlay" onClick={onClose}>
      <div className="cart-panel animate-slideInRight" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="cart-panel__header">
          <h2 className="cart-panel__title">Your cart</h2>
          <button className="cart-panel__close" onClick={onClose}>
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
            <button className="cart-panel__browse-btn" onClick={onClose}>
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
                // Locally-added lines look like {id, name, totalPrice, selectedOptions};
                // engine-projected ones look like {cartItemId, menuItem, quantity}.
                // Read through both shapes so the panel renders either without
                // throwing — an unguarded .length here white-screened the app.
                const key = item.cartItemId ?? item.id;
                const dish = item.menuItem ?? item;
                const opts = item.selectedOptions ?? [];
                const note = item.specialInstructions ?? item.instructions ?? '';
                const unit = item.basePrice ?? dish.price ?? 0;
                const line = item.totalPrice ?? unit * (item.quantity ?? 1);
                return (
                <div key={key} className="cart-item">
                  <div className="cart-item__info">
                    <div className="cart-item__name">{dish.name}</div>
                    {opts.length > 0 && (
                      <div className="cart-item__options">
                        {opts.map(o => o.optionName).join(', ')}
                      </div>
                    )}
                    {note && (
                      <div className="cart-item__instructions">"{note}"</div>
                    )}
                  </div>
                  <div className="cart-item__right">
                    <div className="cart-item__price">{formatCurrency(line)}</div>
                    <div className="cart-item__qty-controls">
                      <button
                        className="cart-item__qty-btn"
                        aria-label="Decrease quantity"
                        onClick={() => updateCartItemQuantity(key, item.quantity - 1)}
                      >
                        {item.quantity === 1 ? <Trash2 size={14} /> : <Minus size={14} />}
                      </button>
                      <span className="cart-item__qty">{item.quantity}</span>
                      <button
                        className="cart-item__qty-btn"
                        aria-label="Increase quantity"
                        onClick={() => updateCartItemQuantity(key, item.quantity + 1)}
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
              <div className="cart-panel__subtotal">
                <span>Subtotal</span>
                <span className="cart-panel__subtotal-amount">{formatCurrency(subtotal)}</span>
              </div>
              <button className="cart-panel__checkout-btn" onClick={handleCheckout}>
                Go to Checkout
              </button>
              {/* Food carts are single-restaurant: without a way to empty it, a
                  cart seeded from one place blocks ordering from anywhere else. */}
              <button
                className="cart-panel__clear-btn"
                aria-label="Clear cart"
                onClick={clearCart}
                style={{ width: '100%', marginTop: 8, padding: '10px 0', background: 'none',
                         border: '1px solid #e2e2e2', borderRadius: 8, cursor: 'pointer',
                         fontSize: 14, color: '#545454' }}
              >
                Clear cart
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
