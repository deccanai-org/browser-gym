import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Package, Star } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { formatCurrency } from '../utils/dataManager';
import './Orders.css';

const ACTIVE_STATUSES = ['placed', 'confirmed', 'preparing', 'picked_up', 'delivering', 'out_for_delivery'];

const STATUS_LABELS = {
  placed: 'Order received',
  confirmed: 'Confirmed',
  preparing: 'Preparing',
  picked_up: 'Picked up',
  delivering: 'On the way',
  out_for_delivery: 'On the way',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
};

const PROGRESS = {
  placed: 15,
  confirmed: 30,
  preparing: 50,
  picked_up: 70,
  delivering: 85,
  out_for_delivery: 85,
  delivered: 100,
  cancelled: 0,
};

function OrderCard({ order, onReorder, onRate }) {
  const [showRating, setShowRating] = useState(false);
  const [rating, setRating] = useState(0);
  const [review, setReview] = useState('');
  const isActive = ACTIVE_STATUSES.includes(order.status);
  const itemSummary = order.items.map(i => `${i.quantity}× ${i.name}`).join(', ');

  const submitRating = () => {
    if (rating < 1) return;
    onRate(order.id, rating, review);
    setShowRating(false);
  };

  return (
    <div className={`order-card ${isActive ? 'order-card--active' : ''}`}>
      <div className="order-card__header">
        <div className="order-card__rest">
          <div className="order-card__rest-avatar">
            {(order.restaurantName || '?').charAt(0)}
          </div>
          <div>
            <div className="order-card__rest-name">{order.restaurantName}</div>
            <div className="order-card__date">
              {new Date(order.placedAt).toLocaleString()}
            </div>
          </div>
        </div>
        <div className="order-card__status">
          {STATUS_LABELS[order.status] || order.status}
        </div>
      </div>

      {isActive && (
        <div className="order-card__progress">
          <div className="order-card__progress-bar">
            <div
              className="order-card__progress-fill"
              style={{ width: `${PROGRESS[order.status] || 10}%` }}
            />
          </div>
          <div className="order-card__progress-labels">
            <span>Received</span>
            <span>Preparing</span>
            <span>On the way</span>
            <span>Delivered</span>
          </div>
        </div>
      )}

      <p className="order-card__items-summary">{itemSummary}</p>

      <div className="order-card__footer">
        <span className="order-card__total">{formatCurrency(order.total)}</span>
        <div className="order-card__actions">
          {isActive ? (
            <Link to={`/orders/${order.id}`} className="order-card__action-btn order-card__action-btn--track">
              Track order
            </Link>
          ) : (
            <>
              <Link to={`/orders/${order.id}`} className="order-card__action-btn">
                View receipt
              </Link>
              <button className="order-card__action-btn" onClick={() => onReorder(order)}>
                Reorder
              </button>
              {order.status === 'delivered' && !order.rating && !showRating && (
                <button
                  className="order-card__action-btn order-card__action-btn--rate"
                  onClick={() => setShowRating(true)}
                >
                  Rate
                </button>
              )}
              {order.rating && (
                <span className="order-card__rated">
                  {'★'.repeat(order.rating)}{'☆'.repeat(5 - order.rating)}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {showRating && (
        <div className="order-card__rating-form">
          <div className="order-card__star-select">
            {[1, 2, 3, 4, 5].map(n => (
              <button
                key={n}
                className={`order-card__star ${n <= rating ? 'order-card__star--active' : ''}`}
                onClick={() => setRating(n)}
                aria-label={`${n} stars`}
              >
                <Star size={24} fill={n <= rating ? 'currentColor' : 'none'} />
              </button>
            ))}
          </div>
          <textarea
            className="order-card__review-input"
            placeholder="Leave a review (optional)"
            value={review}
            onChange={(e) => setReview(e.target.value)}
            rows={3}
          />
          <div className="order-card__rating-actions">
            <button className="order-card__cancel-btn" onClick={() => setShowRating(false)}>Cancel</button>
            <button className="order-card__submit-btn" onClick={submitRating} disabled={rating < 1}>
              Submit
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Orders() {
  const { state, rateOrder, clearCart, addToCart } = useApp();
  const navigate = useNavigate();

  const { activeOrders, pastOrders } = useMemo(() => {
    const sorted = [...state.orders].sort(
      (a, b) => new Date(b.placedAt) - new Date(a.placedAt)
    );
    return {
      activeOrders: sorted.filter(o => ACTIVE_STATUSES.includes(o.status)),
      pastOrders: sorted.filter(o => !ACTIVE_STATUSES.includes(o.status)),
    };
  }, [state.orders]);

  const handleReorder = (order) => {
    const restaurant = state.restaurants.find(r => r.id === order.restaurantId);
    if (!restaurant) {
      navigate(`/store/${order.restaurantId}`);
      return;
    }
    clearCart();
    order.items.forEach(item => {
      // engine-projected lines nest the dish under menuItem; locally-added
      // ones carry a flat menuItemId.
      const dishId = item.menuItem?.id ?? item.menuItemId;
      const menuItem = state.menuItems.find(m => m.id === dishId) || {
        id: dishId,
        name: item.menuItem?.name ?? item.name,
        price: item.unitPrice || item.totalPrice / item.quantity,
      };
      addToCart(menuItem, restaurant, item.quantity, [], item.specialInstructions || '');
    });
    navigate('/checkout');
  };

  if (state.orders.length === 0) {
    return (
      <div className="orders-empty">
        <div className="orders-empty__icon">
          <Package size={40} />
        </div>
        <h2>No orders yet</h2>
        <p>When you place an order, it will show up here</p>
        <Link to="/" className="orders-empty__btn">Browse restaurants</Link>
      </div>
    );
  }

  return (
    <div className="orders-page">
      <h1 className="orders-page__title">Your orders</h1>

      {activeOrders.length > 0 && (
        <section className="orders-section">
          <h2 className="orders-section__title">Active</h2>
          <div className="orders-list">
            {activeOrders.map(order => (
              <OrderCard
                key={order.id}
                order={order}
                onReorder={handleReorder}
                onRate={rateOrder}
              />
            ))}
          </div>
        </section>
      )}

      {pastOrders.length > 0 && (
        <section className="orders-section">
          <h2 className="orders-section__title">Past orders</h2>
          <div className="orders-list">
            {pastOrders.map(order => (
              <OrderCard
                key={order.id}
                order={order}
                onReorder={handleReorder}
                onRate={rateOrder}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
