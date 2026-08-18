import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, CreditCard, Heart, Clock, Settings, ChevronRight, User, Phone, Mail, Shield, Edit2, Check, X } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { bridged } from '../lib/bridge';
import './Account.css';

// Honest caption for controls that only touch local session state — the food
// engine has no user/address/payment/favorites store, so edits here aren't
// synced anywhere and no task is scored on them. Shown only in bridged mode.
const localOnlyNote = (text) => bridged() ? (
  <p style={{ margin: '4px 0 0', fontSize: 12, color: '#6B6B6B', lineHeight: 1.4 }}>{text}</p>
) : null;

export default function Account() {
  const { state, updateUser, activateUberOne, addAddress, addPaymentMethod } = useApp();
  const user = state.user;
  const favRestaurants = state.restaurants.filter(r => user.favoriteRestaurantIds.includes(r.id));

  const [editingField, setEditingField] = useState(null);
  const [fieldValue, setFieldValue] = useState('');
  const [showUberOneModal, setShowUberOneModal] = useState(false);

  // Add-address inline form
  const emptyAddress = { label: 'Home', street: '', apt: '', city: '', state: '', zip: '', instructions: '' };
  const [showAddAddress, setShowAddAddress] = useState(false);
  const [newAddress, setNewAddress] = useState(emptyAddress);

  // Add-payment inline form
  const emptyCard = { type: 'visa', label: '', last4: '', expiry: '' };
  const [showAddPayment, setShowAddPayment] = useState(false);
  const [newCard, setNewCard] = useState(emptyCard);

  const handleStartEdit = (field, currentValue) => {
    setEditingField(field);
    setFieldValue(currentValue);
  };

  const handleSaveEdit = () => {
    if (editingField && fieldValue.trim()) {
      updateUser({ [editingField]: fieldValue.trim() });
    }
    setEditingField(null);
  };

  const handleCancelEdit = () => {
    setEditingField(null);
    setFieldValue('');
  };

  const handleActivateUberOne = () => {
    activateUberOne();
    setShowUberOneModal(false);
  };

  const handleAddAddress = () => {
    if (!newAddress.street.trim() || !newAddress.city.trim()) return;
    addAddress({
      label: newAddress.label.trim() || 'Home',
      street: newAddress.street.trim(),
      apt: newAddress.apt.trim(),
      city: newAddress.city.trim(),
      state: newAddress.state.trim(),
      zip: newAddress.zip.trim(),
      instructions: newAddress.instructions.trim(),
      isDefault: false,
    });
    setNewAddress(emptyAddress);
    setShowAddAddress(false);
  };

  const handleCancelAddAddress = () => {
    setNewAddress(emptyAddress);
    setShowAddAddress(false);
  };

  const handleAddPayment = () => {
    const last4 = newCard.last4.replace(/\D/g, '').slice(-4);
    if (newCard.type !== 'paypal' && last4.length < 4) return;
    addPaymentMethod({
      type: newCard.type,
      label: newCard.label.trim(),
      last4,
      expiry: newCard.expiry.trim(),
    });
    setNewCard(emptyCard);
    setShowAddPayment(false);
  };

  const handleCancelAddPayment = () => {
    setNewCard(emptyCard);
    setShowAddPayment(false);
  };

  const scrollToSection = (sectionId) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const userInitials = user.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  const addressInvalid = !newAddress.street.trim() || !newAddress.city.trim();
  const cardInvalid = newCard.type !== 'paypal' && newCard.last4.replace(/\D/g, '').length < 4;

  return (
    <div className="account-page">
      {/* Profile Header */}
      <div className="account-profile">
        <div className="account-profile__avatar">
          {userInitials}
        </div>
        <h1 className="account-profile__name">{user.name}</h1>
        <p className="account-profile__email">{user.email}</p>
      </div>

      {/* xber Eats One banner */}
      {!user.uberOneActive && (
        <div className="account-uber-one">
          <div className="account-uber-one__content">
            <strong>xber Eats One</strong>
            <p>$0 Delivery Fee and 5% off eligible orders</p>
          </div>
          <button className="account-uber-one__btn" onClick={() => setShowUberOneModal(true)}>Try free for 1 month</button>
        </div>
      )}
      {user.uberOneActive && (
        <div className="account-uber-one account-uber-one--active">
          <div className="account-uber-one__content">
            <strong>xber Eats One Member</strong>
            <p>Enjoy $0 delivery and 5% off eligible orders</p>
          </div>
          <Shield size={24} />
        </div>
      )}

      {/* Quick links menu */}
      <div className="account-menu">
        <Link to="/orders" className="account-menu__item">
          <Clock size={20} />
          <span className="account-menu__label">Orders</span>
          <span className="account-menu__count">{state.orders.length}</span>
          <ChevronRight size={16} />
        </Link>
        <Link to="/favorites" className="account-menu__item">
          <Heart size={20} />
          <span className="account-menu__label">Favorites</span>
          <span className="account-menu__count">{user.favoriteRestaurantIds.length}</span>
          <ChevronRight size={16} />
        </Link>
        <button
          type="button"
          className="account-menu__item"
          onClick={() => scrollToSection('addresses')}
        >
          <MapPin size={20} />
          <span className="account-menu__label">Addresses</span>
          <span className="account-menu__count">{user.addresses.length}</span>
          <ChevronRight size={16} />
        </button>
        <button
          type="button"
          className="account-menu__item"
          onClick={() => scrollToSection('payment')}
        >
          <CreditCard size={20} />
          <span className="account-menu__label">Payment</span>
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Personal Info */}
      <section className="account-section">
        <h2 className="account-section__title">Personal Info</h2>
        {localOnlyNote('Saved locally, not synced to your account.')}
        <div className="account-info-card">
          <div className="account-info__row">
            <User size={18} />
            <div className="account-info__field">
              <span className="account-info__label">Name</span>
              {editingField === 'name' ? (
                <div className="account-info__edit-row">
                  <input
                    type="text"
                    className="account-info__input"
                    value={fieldValue}
                    onChange={(e) => setFieldValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit(); if (e.key === 'Escape') handleCancelEdit(); }}
                    autoFocus
                  />
                  <button className="account-info__save-btn" onClick={handleSaveEdit} title="Save"><Check size={16} /></button>
                  <button className="account-info__cancel-btn" onClick={handleCancelEdit} title="Cancel"><X size={16} /></button>
                </div>
              ) : (
                <span className="account-info__value">{user.name}</span>
              )}
            </div>
            {editingField !== 'name' && (
              <button className="account-info__edit" onClick={() => handleStartEdit('name', user.name)}>
                <Edit2 size={16} />
              </button>
            )}
          </div>

          <div className="account-info__row">
            <Mail size={18} />
            <div className="account-info__field">
              <span className="account-info__label">Email</span>
              {editingField === 'email' ? (
                <div className="account-info__edit-row">
                  <input
                    type="email"
                    className="account-info__input"
                    value={fieldValue}
                    onChange={(e) => setFieldValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit(); if (e.key === 'Escape') handleCancelEdit(); }}
                    autoFocus
                  />
                  <button className="account-info__save-btn" onClick={handleSaveEdit} title="Save"><Check size={16} /></button>
                  <button className="account-info__cancel-btn" onClick={handleCancelEdit} title="Cancel"><X size={16} /></button>
                </div>
              ) : (
                <span className="account-info__value">{user.email}</span>
              )}
            </div>
            {editingField !== 'email' && (
              <button className="account-info__edit" onClick={() => handleStartEdit('email', user.email)}>
                <Edit2 size={16} />
              </button>
            )}
          </div>

          <div className="account-info__row">
            <Phone size={18} />
            <div className="account-info__field">
              <span className="account-info__label">Phone</span>
              {editingField === 'phone' ? (
                <div className="account-info__edit-row">
                  <input
                    type="tel"
                    className="account-info__input"
                    value={fieldValue}
                    onChange={(e) => setFieldValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEdit(); if (e.key === 'Escape') handleCancelEdit(); }}
                    autoFocus
                  />
                  <button className="account-info__save-btn" onClick={handleSaveEdit} title="Save"><Check size={16} /></button>
                  <button className="account-info__cancel-btn" onClick={handleCancelEdit} title="Cancel"><X size={16} /></button>
                </div>
              ) : (
                <span className="account-info__value">{user.phone}</span>
              )}
            </div>
            {editingField !== 'phone' && (
              <button className="account-info__edit" onClick={() => handleStartEdit('phone', user.phone)}>
                <Edit2 size={16} />
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Favorites section */}
      {favRestaurants.length > 0 && (
        <section className="account-section">
          <div className="account-section__header">
            <h2 className="account-section__title">Favorite Restaurants</h2>
            <Link to="/favorites" className="account-section__link">See all</Link>
          </div>
          {localOnlyNote('Favorites are kept locally for this session only.')}
          <div className="account-favs">
            {favRestaurants.slice(0, 3).map(r => (
              <Link key={r.id} to={`/store/${r.id}`} className="account-fav">
                <div className="account-fav__icon">{r.name.charAt(0)}</div>
                <div className="account-fav__info">
                  <span className="account-fav__name">{r.name}</span>
                  <span className="account-fav__meta">{r.cuisineType.join(', ')}</span>
                </div>
                <ChevronRight size={16} />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Addresses */}
      <section id="addresses" className="account-section">
        <h2 className="account-section__title">Saved Addresses</h2>
        {localOnlyNote('Saved locally, not synced to your account.')}
        <div className="account-addresses">
          {user.addresses.map(addr => (
            <div key={addr.id} className="account-address">
              <MapPin size={18} />
              <div className="account-address__info">
                <strong>{addr.label}</strong>
                <span className="account-address__detail">{addr.street}{addr.apt ? `, ${addr.apt}` : ''}</span>
                <span className="account-address__detail">{addr.city}, {addr.state} {addr.zip}</span>
              </div>
              {addr.isDefault && <span className="account-address__badge">Default</span>}
            </div>
          ))}
        </div>

        {!showAddAddress ? (
          <button
            type="button"
            data-testid="add-address-btn"
            onClick={() => setShowAddAddress(true)}
            style={{ width: '100%', textAlign: 'left', padding: '12px 16px', marginTop: 8, border: '1px dashed var(--color-gray-300)', borderRadius: 'var(--radius-card)', background: 'transparent', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer' }}
          >
            + Add address
          </button>
        ) : (
          <div style={{ padding: 16, marginTop: 8, border: '1px solid var(--color-gray-200)', borderRadius: 'var(--radius-card)', display: 'grid', gap: 8 }}>
            <input
              className="account-info__input"
              type="text"
              data-testid="address-label-input"
              placeholder="Label (Home, Work...)"
              value={newAddress.label}
              onChange={(e) => setNewAddress(a => ({ ...a, label: e.target.value }))}
            />
            <input
              className="account-info__input"
              type="text"
              data-testid="address-street-input"
              placeholder="Street address *"
              value={newAddress.street}
              onChange={(e) => setNewAddress(a => ({ ...a, street: e.target.value }))}
            />
            <input
              className="account-info__input"
              type="text"
              data-testid="address-apt-input"
              placeholder="Apt / Suite (optional)"
              value={newAddress.apt}
              onChange={(e) => setNewAddress(a => ({ ...a, apt: e.target.value }))}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 8 }}>
              <input
                className="account-info__input"
                type="text"
                data-testid="address-city-input"
                placeholder="City *"
                value={newAddress.city}
                onChange={(e) => setNewAddress(a => ({ ...a, city: e.target.value }))}
              />
              <input
                className="account-info__input"
                type="text"
                data-testid="address-state-input"
                placeholder="State"
                value={newAddress.state}
                onChange={(e) => setNewAddress(a => ({ ...a, state: e.target.value }))}
              />
              <input
                className="account-info__input"
                type="text"
                data-testid="address-zip-input"
                placeholder="ZIP"
                value={newAddress.zip}
                onChange={(e) => setNewAddress(a => ({ ...a, zip: e.target.value }))}
              />
            </div>
            <input
              className="account-info__input"
              type="text"
              data-testid="address-instructions-input"
              placeholder="Delivery instructions (optional)"
              value={newAddress.instructions}
              onChange={(e) => setNewAddress(a => ({ ...a, instructions: e.target.value }))}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button
                type="button"
                data-testid="cancel-address-btn"
                onClick={handleCancelAddAddress}
                style={{ padding: '8px 16px', border: '1px solid var(--color-gray-300)', borderRadius: 'var(--radius-pill)', background: 'var(--color-white)', fontWeight: 600, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="account-uber-one__btn"
                data-testid="save-address-btn"
                onClick={handleAddAddress}
                disabled={addressInvalid}
                style={{ opacity: addressInvalid ? 0.5 : 1, cursor: addressInvalid ? 'not-allowed' : 'pointer' }}
              >
                Save address
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Payment Methods */}
      <section id="payment" className="account-section">
        <h2 className="account-section__title">Payment Methods</h2>
        {localOnlyNote('Saved locally, not synced. No real payment method is stored or charged.')}
        <div className="account-payments">
          {user.paymentMethods.map(pm => (
            <div key={pm.id} className="account-payment">
              <CreditCard size={18} />
              <div className="account-payment__info">
                <strong>{pm.label}</strong>
                {pm.type === 'visa' && <span className="account-payment__type">Visa</span>}
                {pm.type === 'mastercard' && <span className="account-payment__type">Mastercard</span>}
                {pm.type === 'paypal' && <span className="account-payment__type">PayPal</span>}
                {pm.expiry && <span className="account-payment__type">Expires {pm.expiry}</span>}
              </div>
              {pm.isDefault && <span className="account-address__badge">Default</span>}
            </div>
          ))}
        </div>

        {!showAddPayment ? (
          <button
            type="button"
            data-testid="add-payment-btn"
            onClick={() => setShowAddPayment(true)}
            style={{ width: '100%', textAlign: 'left', padding: '12px 16px', marginTop: 8, border: '1px dashed var(--color-gray-300)', borderRadius: 'var(--radius-card)', background: 'transparent', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer' }}
          >
            + Add payment method
          </button>
        ) : (
          <div style={{ padding: 16, marginTop: 8, border: '1px solid var(--color-gray-200)', borderRadius: 'var(--radius-card)', display: 'grid', gap: 8 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <select
                className="account-info__input"
                data-testid="payment-type-select"
                value={newCard.type}
                onChange={(e) => setNewCard(c => ({ ...c, type: e.target.value }))}
              >
                <option value="visa">Visa</option>
                <option value="mastercard">Mastercard</option>
                <option value="paypal">PayPal</option>
              </select>
              <input
                className="account-info__input"
                type="text"
                data-testid="payment-label-input"
                placeholder="Name on card (optional)"
                value={newCard.label}
                onChange={(e) => setNewCard(c => ({ ...c, label: e.target.value }))}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input
                className="account-info__input"
                type="text"
                inputMode="numeric"
                data-testid="payment-last4-input"
                placeholder={newCard.type === 'paypal' ? 'Last 4 (optional)' : 'Card last 4 *'}
                value={newCard.last4}
                onChange={(e) => setNewCard(c => ({ ...c, last4: e.target.value }))}
              />
              <input
                className="account-info__input"
                type="text"
                data-testid="payment-expiry-input"
                placeholder="Expiry MM/YY"
                value={newCard.expiry}
                onChange={(e) => setNewCard(c => ({ ...c, expiry: e.target.value }))}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button
                type="button"
                data-testid="cancel-payment-btn"
                onClick={handleCancelAddPayment}
                style={{ padding: '8px 16px', border: '1px solid var(--color-gray-300)', borderRadius: 'var(--radius-pill)', background: 'var(--color-white)', fontWeight: 600, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="account-uber-one__btn"
                data-testid="save-payment-btn"
                onClick={handleAddPayment}
                disabled={cardInvalid}
                style={{ opacity: cardInvalid ? 0.5 : 1, cursor: cardInvalid ? 'not-allowed' : 'pointer' }}
              >
                Add card
              </button>
            </div>
          </div>
        )}
      </section>

      {/* xber Eats One Modal */}
      {showUberOneModal && (
        <div className="uber-one-modal-overlay" onClick={() => setShowUberOneModal(false)}>
          <div className="uber-one-modal" onClick={(e) => e.stopPropagation()}>
            <button className="uber-one-modal__close" onClick={() => setShowUberOneModal(false)}>
              <X size={20} />
            </button>
            <div className="uber-one-modal__header">
              <strong>xber Eats One</strong>
            </div>
            <div className="uber-one-modal__benefits">
              <div className="uber-one-modal__benefit">
                <span className="uber-one-modal__benefit-icon">🚚</span>
                <div>
                  <strong>$0 Delivery Fee</strong>
                  <p>No delivery fees on eligible orders</p>
                </div>
              </div>
              <div className="uber-one-modal__benefit">
                <span className="uber-one-modal__benefit-icon">💰</span>
                <div>
                  <strong>5% off eligible orders</strong>
                  <p>Save on every eligible order you place</p>
                </div>
              </div>
              <div className="uber-one-modal__benefit">
                <span className="uber-one-modal__benefit-icon">⚡</span>
                <div>
                  <strong>Priority delivery</strong>
                  <p>Your orders get priority assignment</p>
                </div>
              </div>
            </div>
            <p className="uber-one-modal__price">$9.99/month after free trial</p>
            <button className="uber-one-modal__cta" onClick={handleActivateUberOne}>
              Start free trial
            </button>
            <button className="uber-one-modal__skip" onClick={() => setShowUberOneModal(false)}>
              No thanks
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
