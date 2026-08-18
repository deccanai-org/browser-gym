import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, ShoppingBag, ChevronDown, MapPin, X, Menu, Clock } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { bridged } from '../lib/bridge';
import './Header.css';

export default function Header({ onCartClick, onMenuClick }) {
  const { state, setDeliveryMode, setScheduledTime, updateAddress, addAddress } = useApp();
  const [searchValue, setSearchValue] = useState('');
  const [addressDropdownOpen, setAddressDropdownOpen] = useState(false);
  const [showAddAddressForm, setShowAddAddressForm] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [newAddress, setNewAddress] = useState({ label: 'Home', street: '', apt: '', city: '', state: 'NY', zip: '', instructions: '', isDefault: false });
  const navigate = useNavigate();
  const addressRef = useRef(null);
  const scheduleRef = useRef(null);

  // "Now / Schedule" affordance — same-day half-hours plus dinner slots for the
  // next week (schedule-ahead nights). Uses gym clock when bridged.
  const scheduledTime = state.ui.scheduledTime;
  const scheduleLabel = scheduledTime?.label || 'Now';
  const scheduleSlots = useMemo(() => {
    const two = (n) => (n < 10 ? '0' + n : '' + n);
    const fmt = (dt) => { let h = dt.getHours(); const m = dt.getMinutes(); const ap = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12; return `${h}:${two(m)} ${ap}`; };
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const nowMs = (state && state._gym_now) || Date.now();
    const now = new Date(nowMs);
    const base = new Date(now.getTime());
    base.setSeconds(0, 0);
    base.setMinutes(base.getMinutes() <= 30 ? 30 : 60);
    const slots = [];
    for (let i = 0; i < 4; i++) {
      const s = new Date(base.getTime() + i * 30 * 60000);
      const day = s.getDate() === now.getDate() ? 'Today' : 'Tomorrow';
      slots.push({ label: `${day}, ${fmt(s)}`, iso: s.toISOString() });
    }
    // Dinner evenings for the next 7 calendar days (YYYY-MM-DD iso date).
    for (let d = 0; d < 7; d++) {
      const s = new Date(now.getFullYear(), now.getMonth(), now.getDate() + d, 19, 0, 0, 0);
      const y = s.getFullYear();
      const mo = two(s.getMonth() + 1);
      const da = two(s.getDate());
      const isoDay = `${y}-${mo}-${da}`;
      const labelDay = d === 0 ? 'Tonight' : `${dayNames[s.getDay()]} ${mo}/${da}`;
      slots.push({
        label: `${labelDay}, 7:00 PM dinner`,
        iso: isoDay,
        date: isoDay,
      });
    }
    return slots;
  }, [state && state._gym_now]);

  const cartCount = state.cart.items.reduce((sum, item) => sum + item.quantity, 0);
  const selectedAddress = state.user.addresses.find(a => a.id === state.ui.selectedAddressId) || state.user.addresses[0];
  const addressText = selectedAddress ? `${selectedAddress.street}` : '100 Park Avenue';

  const userInitials = state.user.name
    ? state.user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  // Close address dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (addressRef.current && !addressRef.current.contains(e.target)) {
        setAddressDropdownOpen(false);
        setShowAddAddressForm(false);
      }
    }
    if (addressDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [addressDropdownOpen]);

  // Close schedule popover on outside click
  useEffect(() => {
    function handle(e) {
      if (scheduleRef.current && !scheduleRef.current.contains(e.target)) setScheduleOpen(false);
    }
    if (scheduleOpen) document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [scheduleOpen]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchValue.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchValue.trim())}`);
    }
  };

  const handleSearchFocus = () => {
    navigate('/search');
  };

  const handleSelectAddress = (addrId) => {
    updateAddress(addrId);
    setAddressDropdownOpen(false);
    setShowAddAddressForm(false);
  };

  const handleAddNewAddress = () => {
    if (!newAddress.street.trim() || !newAddress.city.trim()) return;
    addAddress(newAddress);
    setNewAddress({ label: 'Home', street: '', apt: '', city: '', state: 'NY', zip: '', instructions: '', isDefault: false });
    setShowAddAddressForm(false);
  };

  return (
    <header className="ue-header">
      <div className="ue-header__inner">
        {/* Hamburger menu */}
        <button className="ue-header__menu-btn" onClick={onMenuClick} aria-label="Open menu">
          <Menu size={24} />
        </button>

        {/* Logo */}
        <Link to="/" className="ue-header__logo">
          <span className="ue-header__logo-uber">xber</span>
          <span className="ue-header__logo-eats">Eats</span>
        </Link>

        {/* Delivery/Pickup Toggle */}
        <div className="ue-header__mode-toggle">
          <button
            type="button"
            className={`ue-header__mode-btn ${state.ui.deliveryMode === 'delivery' ? 'ue-header__mode-btn--active' : ''}`}
            data-test-id="btn-delivery-mode-delivery"
            onClick={() => setDeliveryMode('delivery')}
          >
            Delivery
          </button>
          <button
            type="button"
            className={`ue-header__mode-btn ${state.ui.deliveryMode === 'pickup' ? 'ue-header__mode-btn--active' : ''}`}
            data-test-id="btn-delivery-mode-pickup"
            onClick={() => setDeliveryMode('pickup')}
          >
            Pickup
          </button>
        </div>

        {/* Address with dropdown */}
        <div className="ue-header__address-wrapper" ref={addressRef}>
          <button
            className="ue-header__address"
            onClick={() => { setAddressDropdownOpen(!addressDropdownOpen); setShowAddAddressForm(false); }}
          >
            <MapPin size={16} />
            <span className="ue-header__address-text">{addressText}</span>
            <ChevronDown size={14} className={addressDropdownOpen ? 'ue-header__chevron--open' : ''} />
          </button>

          {addressDropdownOpen && (
            <div className="ue-header__address-dropdown">
              {!showAddAddressForm ? (
                <>
                  <div className="ue-header__dropdown-title">Deliver to</div>
                  {state.user.addresses.map(addr => (
                    <button
                      key={addr.id}
                      className={`ue-header__dropdown-item ${addr.id === state.ui.selectedAddressId ? 'ue-header__dropdown-item--active' : ''}`}
                      onClick={() => handleSelectAddress(addr.id)}
                    >
                      <MapPin size={16} />
                      <div className="ue-header__dropdown-item-info">
                        <strong>{addr.label}</strong>
                        <span>{addr.street}{addr.apt ? `, ${addr.apt}` : ''}</span>
                      </div>
                      {addr.id === state.ui.selectedAddressId && (
                        <span className="ue-header__dropdown-check">&#10003;</span>
                      )}
                    </button>
                  ))}
                  <div className="ue-header__dropdown-divider" />
                  <button
                    className="ue-header__dropdown-add"
                    onClick={() => setShowAddAddressForm(true)}
                  >
                    <span>+</span>
                    <span>Add new address</span>
                  </button>
                </>
              ) : (
                <div className="ue-header__add-address-form">
                  <div className="ue-header__add-address-header">
                    <strong>Add new address</strong>
                    <button onClick={() => setShowAddAddressForm(false)}><X size={16} /></button>
                  </div>
                  {bridged() && (
                    <p style={{ margin: '0 0 8px', fontSize: 11, color: '#6B6B6B', lineHeight: 1.4 }}>
                      Saved locally, not synced to your account.
                    </p>
                  )}
                  <input
                    className="ue-header__add-address-input"
                    type="text"
                    placeholder="Label (Home, Work...)"
                    value={newAddress.label}
                    onChange={(e) => setNewAddress(a => ({ ...a, label: e.target.value }))}
                  />
                  <input
                    className="ue-header__add-address-input"
                    type="text"
                    placeholder="Street address *"
                    value={newAddress.street}
                    onChange={(e) => setNewAddress(a => ({ ...a, street: e.target.value }))}
                  />
                  <input
                    className="ue-header__add-address-input"
                    type="text"
                    placeholder="Apt / Suite (optional)"
                    value={newAddress.apt}
                    onChange={(e) => setNewAddress(a => ({ ...a, apt: e.target.value }))}
                  />
                  <div className="ue-header__add-address-row">
                    <input
                      className="ue-header__add-address-input"
                      type="text"
                      placeholder="City *"
                      value={newAddress.city}
                      onChange={(e) => setNewAddress(a => ({ ...a, city: e.target.value }))}
                    />
                    <input
                      className="ue-header__add-address-input"
                      type="text"
                      placeholder="ZIP"
                      value={newAddress.zip}
                      onChange={(e) => setNewAddress(a => ({ ...a, zip: e.target.value }))}
                    />
                  </div>
                  <button
                    className="ue-header__add-address-save"
                    onClick={handleAddNewAddress}
                    disabled={!newAddress.street.trim() || !newAddress.city.trim()}
                  >
                    Save address
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Schedule (Now / Later) */}
        <div className="ue-header__address-wrapper" ref={scheduleRef}>
          <button
            type="button"
            className="ue-header__address"
            data-test-id="btn-schedule-when"
            onClick={() => setScheduleOpen(o => !o)}
            aria-haspopup="true"
            aria-expanded={scheduleOpen}
          >
            <Clock size={16} />
            <span className="ue-header__address-text">{scheduleLabel}</span>
            <ChevronDown size={14} className={scheduleOpen ? 'ue-header__chevron--open' : ''} />
          </button>
          {scheduleOpen && (
            <div className="ue-header__address-dropdown" style={{ minWidth: 240 }} data-test-id="schedule-when-menu">
              <div className="ue-header__dropdown-title">When</div>
              <button
                className={`ue-header__dropdown-item ${!scheduledTime ? 'ue-header__dropdown-item--active' : ''}`}
                data-test-id="btn-schedule-now"
                onClick={() => { setScheduledTime(null); setScheduleOpen(false); }}
              >
                <Clock size={16} />
                <div className="ue-header__dropdown-item-info">
                  <strong>Deliver now</strong>
                  <span>In {state.ui.deliveryMode === 'pickup' ? '10-20' : '25-40'} min</span>
                </div>
                {!scheduledTime && <span className="ue-header__dropdown-check">&#10003;</span>}
              </button>
              <div className="ue-header__dropdown-divider" />
              {scheduleSlots.map(slot => (
                <button
                  key={slot.iso}
                  className={`ue-header__dropdown-item ${scheduledTime?.iso === slot.iso ? 'ue-header__dropdown-item--active' : ''}`}
                  data-test-id={`btn-schedule-slot-${slot.date || slot.iso}`}
                  onClick={() => { setScheduledTime(slot); setScheduleOpen(false); }}
                >
                  <Clock size={16} />
                  <div className="ue-header__dropdown-item-info"><span>{slot.label}</span></div>
                  {scheduledTime?.iso === slot.iso && <span className="ue-header__dropdown-check">&#10003;</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Search */}
        <form className="ue-header__search" onSubmit={handleSearch}>
          <Search size={18} className="ue-header__search-icon" />
          <input
            type="text"
            placeholder="Search xber Eats"
            className="ue-header__search-input"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            onFocus={handleSearchFocus}
          />
        </form>

        {/* Right Section */}
        <div className="ue-header__actions">
          <button className="ue-header__cart-btn" onClick={onCartClick}>
            <ShoppingBag size={20} />
            {cartCount > 0 && (
              <span className="ue-header__cart-badge">{cartCount}</span>
            )}
            <span className="ue-header__cart-label">Cart</span>
          </button>

          <Link to="/account" className="ue-header__avatar">
            <span>{userInitials}</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
