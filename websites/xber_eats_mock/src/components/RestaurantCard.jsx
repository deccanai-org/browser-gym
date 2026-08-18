import React from 'react';
import { Link } from 'react-router-dom';
import { Heart } from 'lucide-react';
import { useApp } from '../context/AppContext';
import './RestaurantCard.css';

const FOOD_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8C471', '#82E0AA',
  '#D7BDE2', '#AED6F1', '#F9E79F', '#A3E4D7', '#F5B7B1', '#ABEBC6'
];

const FOOD_EMOJIS = {
  italian: '🍕', pizza: '🍕', japanese: '🍣', sushi: '🍣',
  american: '🍔', burgers: '🍔', mexican: '🌮', tacos: '🌮',
  chinese: '🥡', indian: '🍛', healthy: '🥗', salads: '🥗',
  dessert: '🍰', bakery: '🍰', vietnamese: '🍜', pho: '🍜',
  mediterranean: '🥙', korean: '🍖', thai: '🍜', bbq: '🍖',
  breakfast: '🥞', brunch: '🥞', coffee: '☕', steakhouse: '🥩',
};

function getCardColor(id) {
  const idx = parseInt(String(id).replace(/\D/g, ''), 10) || 0;
  return FOOD_COLORS[idx % FOOD_COLORS.length];
}

function getEmoji(cuisineType) {
  if (!cuisineType || cuisineType.length === 0) return '🍽️';
  for (const c of cuisineType) {
    const key = String(c).toLowerCase();
    if (FOOD_EMOJIS[key]) return FOOD_EMOJIS[key];
  }
  return '🍽️';
}

function getPromoBadge(restaurant) {
  if (restaurant.deliveryFee === 0) {
    return { text: '$0 Delivery Fee', color: '#06C167' };
  }
  if (restaurant.promotions && restaurant.promotions.length > 0) {
    const promo = restaurant.promotions[0];
    if (promo.discountPercent) {
      return { text: `${promo.discountPercent}% off`, color: '#06C167' };
    }
    if (promo.discountAmount) {
      return { text: `$${promo.discountAmount} off`, color: '#06C167' };
    }
    if (promo.type === 'free_delivery') {
      return { text: '$0 Delivery Fee', color: '#06C167' };
    }
    return { text: promo.title, color: '#06C167' };
  }
  return null;
}

export default function RestaurantCard({ restaurant }) {
  const { state, toggleFavorite } = useApp();
  const isFav = state.user.favoriteRestaurantIds.includes(restaurant.id);
  const promoBadge = getPromoBadge(restaurant);
  // Pickup mode (header toggle) shows pickup ETA + a "Pickup" label instead of
  // the delivery-fee copy, so the Delivery/Pickup switch has a visible effect.
  const isPickup = state.ui.deliveryMode === 'pickup';
  const timeMin = isPickup ? (restaurant.pickupTimeMin ?? restaurant.deliveryTimeMin) : restaurant.deliveryTimeMin;
  const timeMax = isPickup ? (restaurant.pickupTimeMax ?? restaurant.deliveryTimeMax) : restaurant.deliveryTimeMax;
  const deliveryInfo = restaurant.deliveryFee === 0
    ? 'Lowest Delivery Fee'
    : restaurant.deliveryFee <= 1.99
    ? 'Low Delivery Fee'
    : restaurant.deliveryFee <= 3.00
    ? 'Moderate Delivery Fee'
    : 'Higher Delivery Fee';

  return (
    <div className="rest-card">
      <Link to={`/store/${restaurant.id}`} className="rest-card__image-link">
        <div
          className="rest-card__image"
          style={{ background: getCardColor(restaurant.id) }}
        >
          {restaurant.imageUrl ? (
            <img
              src={restaurant.imageUrl}
              alt={restaurant.name}
              className="rest-card__photo"
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
            />
          ) : (
            <span className="rest-card__emoji">{getEmoji(restaurant.cuisineType)}</span>
          )}

          {promoBadge && (
            <span className="rest-card__promo-badge" style={{ background: promoBadge.color }}>
              {promoBadge.text}
            </span>
          )}

          <span className="rest-card__rating-badge">
            {restaurant.rating}
          </span>
        </div>
      </Link>

      <button
        className={`rest-card__fav ${isFav ? 'rest-card__fav--active' : ''}`}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleFavorite(restaurant.id); }}
        aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
      >
        <Heart size={18} fill={isFav ? '#000' : 'none'} stroke={isFav ? '#000' : 'currentColor'} />
      </button>

      <Link to={`/store/${restaurant.id}`} className="rest-card__info">
        <div className="rest-card__row1">
          <h3 className="rest-card__name">{restaurant.name}</h3>
        </div>
        <div className="rest-card__row2">
          <span className="rest-card__delivery-info">
            {isPickup ? 'Pickup available' : (<>{restaurant.deliveryFee === 0 && <span className="rest-card__uber-one-icon">&#9913;</span>}{deliveryInfo}</>)}
          </span>
          <span className="rest-card__dot">&bull;</span>
          <span>{timeMin} min</span>
        </div>
        <div className="rest-card__row3">
          <span className="rest-card__stars">{restaurant.rating} &#9733;</span>
          <span className="rest-card__reviews">({restaurant.reviewCount}+)</span>
          <span className="rest-card__dot">&bull;</span>
          <span className="rest-card__time">{isPickup ? 'Pickup ' : ''}{timeMin}-{timeMax} min</span>
          {restaurant.etaLabel ? (
            <>
              <span className="rest-card__dot">&bull;</span>
              <span className="rest-card__eta" title="Estimated ready time (gym clock)">
                ~{restaurant.etaLabel}
              </span>
            </>
          ) : null}
        </div>
      </Link>
    </div>
  );
}
