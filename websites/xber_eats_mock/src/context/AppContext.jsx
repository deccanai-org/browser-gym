import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { getSessionId, fetchCustomState, saveState, initializeData, initialKey, generateId } from '../utils/dataManager';
import { computeStateDiff } from '../utils/stateTracker';
import { bridged, bridgeState, bridgeAct, bridgePoll } from '../lib/bridge';

const APP = 'food'; // bridge engine app key for this mock

// Delivery/Pickup is client-owned until checkout. Full page navigations (and the
// engine projection, which always defaults mode to "delivery") used to wipe a
// Pickup click, so checkout silently placed a delivery order. Persist per-tab.
const _MODE_KEY = 'gym_food_delivery_mode';
const _readMode = () => {
  try { return (sessionStorage.getItem(_MODE_KEY) || '').toLowerCase(); }
  catch (_) { return ''; }
};
const _writeMode = (mode) => {
  try {
    const m = (mode || '').toLowerCase();
    if (m === 'pickup' || m === 'delivery') sessionStorage.setItem(_MODE_KEY, m);
  } catch (_) {}
};
const _applyStoredMode = (ui, cart) => {
  const stored = _readMode();
  if (stored !== 'pickup' && stored !== 'delivery') return { ui, cart };
  return {
    ui: { ...(ui || {}), deliveryMode: stored },
    cart: cart ? { ...cart, deliveryMode: stored } : cart,
  };
};

// The engine projects cart/order lines as {cartItemId, menuItem:{...}, quantity}
// with NO flat name/totalPrice/selectedOptions, and order.total as an object.
// The readers (CartPanel.jsx:15, Orders.jsx:37, OrderTracking.jsx:266/303) want
// the flat fields, so fill them in ONCE at adoption rather than shape-guarding
// every reader — otherwise the UI shows "N× undefined" and "$NaN".
const _optDelta = (opts) => (opts || []).reduce((s, o) => s + (o.priceModifier || 0), 0);
const _normLine = (item) => {
  if (!item || typeof item !== 'object') return item;
  const mi = item.menuItem;
  const quantity = item.quantity ?? 1;
  const selectedOptions = item.selectedOptions || [];
  const unit = mi?.price ?? item.basePrice ?? 0;
  return {
    ...item,
    name: item.name ?? mi?.name,
    quantity,
    selectedOptions,
    totalPrice: item.totalPrice ?? (unit + _optDelta(selectedOptions)) * quantity,
  };
};
const normalizeEngineData = (data) => {
  if (!data) return data;
  return {
    ...data,
    cart: data.cart ? { ...data.cart, items: (data.cart.items || []).map(_normLine) } : data.cart,
    orders: (data.orders || []).map(o => ({
      ...o,
      items: (o.items || []).map(_normLine),
      total: o?.total?.total ?? o?.total,
    })),
  };
};

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [state, setState] = useState(null);
  const [initialStateSnapshot, setInitialStateSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);

  // Bridged mode: adopt the engine's authoritative per-app state. Normalize the
  // SAME way the normal load path does — initializeData(sid, engineState) deep-
  // merges it onto the seeded defaults — then REPLACE state (uber's setState
  // replaces, not merges). Guard against a null engine state.
  // Merge the engine projection onto local state the SAME way the 2.5s poll does
  // (below): adopt engine-owned keys but preserve the client-owned ui (delivery
  // mode, scheduled time, filters) and user profile (added cards, addresses,
  // favorites) + local cart note + order ratings. A wholesale replace here wiped
  // all of those on every add_to_cart / place_order.
  const mergeEngine = useCallback((prev, raw) => {
    const { ui, ...engineOwned } = normalizeEngineData(initializeData(sidRef.current, raw));
    if (!prev) {
      const seeded = _applyStoredMode(ui, engineOwned.cart);
      return { ...engineOwned, cart: seeded.cart, ui: seeded.ui };
    }
    const base = prev;
    const cart = engineOwned.cart
      ? { ...(base.cart || {}), ...engineOwned.cart,
          deliveryInstructions: base.cart?.deliveryInstructions ?? engineOwned.cart.deliveryInstructions,
          // Engine cart always projects deliveryMode=delivery; keep the user's toggle.
          deliveryMode: base.cart?.deliveryMode ?? engineOwned.cart.deliveryMode }
      : base.cart;
    const user = base.user || engineOwned.user;
    const orders = engineOwned.orders
      ? engineOwned.orders.map(o => {
          const p = (base.orders || []).find(x => x && x.id === o.id);
          return p && (p.rating != null || p.review)
            ? { ...o, rating: p.rating ?? o.rating, review: p.review ?? o.review }
            : o;
        })
      : base.orders;
    const keptUi = base.ui ?? ui;
    const seeded = _applyStoredMode(keptUi, cart);
    return { ...base, ...engineOwned, cart: seeded.cart, user, orders, ui: seeded.ui };
  }, []);

  const applyEngine = useCallback((engineState) => {
    if (!engineState) return;
    setState(prev => mergeEngine(prev, engineState));
  }, [mergeEngine]);

  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;

    const sid = sidRef.current;

    // Bridged mode: the gym engine is the source of truth. Load its state and
    // poll so cross-app effects (e.g. an order confirmation) surface here too.
    if (bridged()) {
      bridgeState(APP).then(s => {
        if (s) {
          const data = normalizeEngineData(initializeData(sid, s));
          const seeded = _applyStoredMode(data.ui, data.cart);
          const next = { ...data, ui: seeded.ui, cart: seeded.cart };
          setState(next);
          setInitialStateSnapshot(JSON.parse(JSON.stringify(next)));
        }
        setLoading(false);
      });
// Poll = adopt the ENGINE's world, but keep the keys the engine does not own.
      // Re-adopting wholesale every 2.5s snapped the user's own view state back
      // (which month you were on, your filters, saved-for-later) mid-interaction.
      const stop = bridgePoll(APP, s => {
        if (!s) return;
        const { ui, ...engineOwned } = normalizeEngineData(initializeData(sid, s));
        setState(prev => {
          const base = prev || {};
          // The engine projection doesn't carry the delivery note (it's ours
          // until checkout), so a wholesale cart swap wiped it every 2.5s.
          // Spread base.cart first to keep any locally-owned field the engine
          // omits, then explicitly protect deliveryInstructions from an
          // engine-carried empty value.
          const cart = engineOwned.cart
            ? { ...(base.cart || {}), ...engineOwned.cart,
                deliveryInstructions: base.cart?.deliveryInstructions ?? engineOwned.cart.deliveryInstructions,
                deliveryMode: base.cart?.deliveryMode ?? engineOwned.cart.deliveryMode }
            : base.cart;
          // The food engine owns none of the user profile -- addresses, favorite
          // restaurants, saved cards, name/phone, and membership are all seed +
          // client edits (no food.* action records them). So once loaded the user
          // is ours; keep it whole or the 2.5s poll wipes every add-address,
          // heart, profile edit, and membership activation.
          const user = base.user || engineOwned.user;
          // Orders ARE engine-owned (real, from checkout), but the star rating /
          // review a user leaves on a delivered order is client-only -- carry it
          // onto the matching engine order by id so the poll doesn't erase it.
          const orders = engineOwned.orders
            ? engineOwned.orders.map(o => {
                const p = (base.orders || []).find(x => x && x.id === o.id);
                return p && (p.rating != null || p.review)
                  ? { ...o, rating: p.rating ?? o.rating, review: p.review ?? o.review }
                  : o;
              })
            : base.orders;
          const keptUi = base.ui ?? ui;
          const seeded = _applyStoredMode(keptUi, cart);
          return { ...base, ...engineOwned, cart: seeded.cart, user, orders, ui: seeded.ui };
        });
      });
      return () => stop();
    }

    const ik = initialKey(sid);
    const isRefresh = localStorage.getItem(ik) !== null;

    if (isRefresh) {
      const data = initializeData(sid);
      const initial = JSON.parse(localStorage.getItem(ik));
      setState(data);
      setInitialStateSnapshot(initial);
      setLoading(false);
    } else {
      // A sid in the URL means a specific gym session was requested. If its seed
      // state cannot be fetched, fail loudly instead of silently booting generic
      // demo data (createInitialData) — otherwise a reviewer can't tell the
      // session never loaded. The demo fallback stays ONLY when no sid is present.
      const urlSid = new URLSearchParams(window.location.search).get('sid');
      fetchCustomState(sid).then(custom => {
        if (urlSid && !custom) {
          setLoadError(urlSid);
          setLoading(false);
          return;
        }
        const data = initializeData(sid, custom);
        setState(data);
        setInitialStateSnapshot(JSON.parse(JSON.stringify(data)));
        setLoading(false);
      });
    }
  }, []);

  useEffect(() => {
    // In bridged mode the gym engine owns the state; persisting our projection
    // back to localStorage on every 2.5s poll floods storage with churn.
    if (!loading && state && !bridged()) {
      saveState(state, sidRef.current);
    }
  }, [state, loading]);

  // --- Actions ---

  const addToCart = useCallback((menuItem, restaurant, quantity, selectedOptions, specialInstructions) => {
    if (bridged()) {
      bridgeAct('food.add_to_cart', {
        restaurant_id: (restaurant && restaurant.id) || (menuItem && (menuItem.restaurantId || menuItem.restaurant_id)) || '',
        dish_id: menuItem && (menuItem.id || menuItem.dishId),
        quantity: quantity || 1,
        // "no onions" was collected by the item modal and thrown away
        note: specialInstructions || '',
      }).then(r => applyEngine(r && r.apps && r.apps[APP]));
      return;
    }
    setState(prev => {
      if (!prev) return prev;
      const modifierTotal = selectedOptions.reduce((s, o) => s + o.priceModifier, 0);
      const cartItem = {
        id: generateId(),
        menuItemId: menuItem.id,
        restaurantId: restaurant.id,
        name: menuItem.name,
        quantity,
        basePrice: menuItem.price,
        selectedOptions: selectedOptions.map(o => ({
          groupId: o.groupId || '',
          groupName: o.groupName || '',
          optionId: o.optionId || o.id || '',
          optionName: o.optionName || o.name,
          priceModifier: o.priceModifier
        })),
        specialInstructions: specialInstructions || '',
        totalPrice: (menuItem.price + modifierTotal) * quantity
      };

      // If adding from a different restaurant, confirm before wiping the cart.
      if (prev.cart.restaurantId && prev.cart.restaurantId !== restaurant.id) {
        const ok = typeof window !== 'undefined'
          ? window.confirm(`Your cart has items from ${prev.cart.restaurantName || 'another restaurant'}. Clear it and add from ${restaurant.name}?`)
          : true;
        if (!ok) return prev;
        return {
          ...prev,
          cart: {
            ...prev.cart,
            restaurantId: restaurant.id,
            restaurantName: restaurant.name,
            items: [cartItem],
            promoCode: null,
            promoDiscount: 0,
          }
        };
      }

      return {
        ...prev,
        cart: {
          ...prev.cart,
          restaurantId: restaurant.id,
          restaurantName: restaurant.name,
          items: [...prev.cart.items, cartItem]
        }
      };
    });
  }, []);

  // A cart line is addressed by cartItemId; seeded lines only ever had that,
  // while these handlers matched on .id, so nothing seeded could be edited.
  const lineKey = (i) => i.cartItemId ?? i.id;
  const dishOf = (prev, key) => {
    const line = (prev?.cart?.items || []).find(i => lineKey(i) === key);
    return line && (line.menuItem?.id ?? line.menuItemId);
  };

  const removeFromCart = useCallback((cartItemId) => {
    setState(prev => {
      if (!prev) return prev;
      if (bridged()) {
        const dish = dishOf(prev, cartItemId);
        if (dish) bridgeAct('food.remove_item', { dish_id: dish })
          .then(r => applyEngine(r && r.apps && r.apps[APP]));
        return prev;                      // the engine's re-projection is the truth
      }
      const newItems = prev.cart.items.filter(i => lineKey(i) !== cartItemId);
      return {
        ...prev,
        cart: {
          ...prev.cart,
          restaurantId: newItems.length === 0 ? null : prev.cart.restaurantId,
          restaurantName: newItems.length === 0 ? null : prev.cart.restaurantName,
          items: newItems
        }
      };
    });
  }, []);

  const updateCartItemQuantity = useCallback((cartItemId, newQuantity) => {
    setState(prev => {
      if (!prev) return prev;
      if (bridged()) {
        const dish = dishOf(prev, cartItemId);
        if (dish) bridgeAct('food.set_qty', { dish_id: dish, quantity: Math.max(0, newQuantity) })
          .then(r => applyEngine(r && r.apps && r.apps[APP]));
        return prev;
      }
      if (newQuantity < 1) {
        const newItems = prev.cart.items.filter(i => lineKey(i) !== cartItemId);
        return {
          ...prev,
          cart: {
            ...prev.cart,
            restaurantId: newItems.length === 0 ? null : prev.cart.restaurantId,
            restaurantName: newItems.length === 0 ? null : prev.cart.restaurantName,
            items: newItems
          }
        };
      }
      return {
        ...prev,
        cart: {
          ...prev.cart,
          items: prev.cart.items.map(item => {
            if (lineKey(item) !== cartItemId) return item;
            const modTotal = (item.selectedOptions || []).reduce((s, o) => s + (o.priceModifier || 0), 0);
            return {
              ...item,
              quantity: newQuantity,
              totalPrice: ((item.basePrice || 0) + modTotal) * newQuantity
            };
          })
        }
      };
    });
  }, []);

  const clearCart = useCallback(() => {
    if (bridged()) {
      // food.clear_cart existed but nothing ever called it, so a cart seeded
      // from another restaurant could never be emptied — and the engine
      // refuses to add across restaurants.
      bridgeAct('food.clear_cart', {}).then(r => applyEngine(r && r.apps && r.apps[APP]));
      return;
    }
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        cart: {
          restaurantId: null, restaurantName: null, items: [],
          deliveryMode: prev.cart.deliveryMode, scheduledTime: null,
          promoCode: null, promoDiscount: 0, tipAmount: 0, tipPercentage: 18,
          deliveryInstructions: ''
        }
      };
    });
  }, []);

  const placeOrder = useCallback((orderData) => {
    if (bridged()) {
      const mode = (
        (orderData && (orderData.delivery_mode || orderData.deliveryMode)) ||
        _readMode() ||
        (state && ((state.ui && state.ui.deliveryMode) || (state.cart && state.cart.deliveryMode))) ||
        'delivery'
      );
      const scheduled =
        (orderData && (orderData.scheduled_delivery || orderData.scheduledDelivery)) ||
        (state && state.ui && state.ui.scheduledTime && (
          // Prefer ISO date (YYYY-MM-DD) for schedule-ahead dinner nights.
          (typeof state.ui.scheduledTime.iso === 'string' && state.ui.scheduledTime.iso.length >= 10
            ? state.ui.scheduledTime.iso.slice(0, 10)
            : null)
        )) ||
        (state && state.cart && state.cart.scheduledTime) ||
        '';
      return bridgeAct('food.checkout', {
        delivery_note: (orderData && (orderData.note || orderData.instructions || orderData.deliveryInstructions)) ||
          (state && state.cart && state.cart.deliveryInstructions) || '',
        delivery_mode: mode,
        scheduled_delivery: scheduled || '',
      }).then(r => {
        const es = r && r.apps && r.apps[APP];
        applyEngine(es);
        // activeOrderId points at the just-placed real order; os[last] is an
        // ambient "delivered" filler order appended after it (wrong redirect).
        return (es && es.activeOrderId) || undefined;
      });
    }
    const orderId = 'ord_' + Date.now().toString(36);
    setState(prev => {
      if (!prev) return prev;
      const cart = prev.cart;
      const restaurant = prev.restaurants.find(r => r.id === cart.restaurantId);
      const subtotal = cart.items.reduce((s, item) => s + item.totalPrice, 0);
      const serviceFee = Math.min(Math.max(subtotal * 0.15, 0.99), 9.99);
      const deliveryFee = restaurant ? restaurant.deliveryFee : 0;
      const tax = subtotal * 0.09;
      const tipAmount = cart.tipPercentage ? subtotal * (cart.tipPercentage / 100) : cart.tipAmount;
      const total = subtotal + serviceFee + deliveryFee + tax + tipAmount - cart.promoDiscount;

      // Prefer task-frozen gym clock so ETA windows align with GymCal now-line.
      const now = prev._gym_now ? new Date(prev._gym_now) : new Date();
      const delivTimeMin = restaurant ? restaurant.deliveryTimeMin : 25;
      const delivTimeMax = restaurant ? restaurant.deliveryTimeMax : 40;

      const selectedAddr = prev.user.addresses.find(a => a.id === prev.ui.selectedAddressId) || prev.user.addresses[0];

      const newOrder = {
        id: orderId,
        restaurantId: cart.restaurantId,
        restaurantName: cart.restaurantName || (restaurant ? restaurant.name : ''),
        restaurantImageUrl: restaurant ? restaurant.imageUrl : '',
        items: cart.items.map(item => ({
          menuItemId: item.menuItemId,
          name: item.name,
          quantity: item.quantity,
          unitPrice: item.basePrice + item.selectedOptions.reduce((s, o) => s + o.priceModifier, 0),
          totalPrice: item.totalPrice,
          selectedOptions: item.selectedOptions.map(o => o.optionName),
          specialInstructions: item.specialInstructions
        })),
        status: 'placed',
        placedAt: now.toISOString(),
        estimatedDeliveryMin: new Date(now.getTime() + delivTimeMin * 60000).toISOString(),
        estimatedDeliveryMax: new Date(now.getTime() + delivTimeMax * 60000).toISOString(),
        deliveredAt: null,
        deliveryAddress: selectedAddr,
        deliveryMode: cart.deliveryMode,
        subtotal: Math.round(subtotal * 100) / 100,
        serviceFee: Math.round(serviceFee * 100) / 100,
        deliveryFee: Math.round(deliveryFee * 100) / 100,
        tax: Math.round(tax * 100) / 100,
        tip: Math.round(tipAmount * 100) / 100,
        promoDiscount: cart.promoDiscount,
        total: Math.round(total * 100) / 100,
        paymentMethod: prev.user.paymentMethods.find(p => p.isDefault)?.label || 'Visa \u2022\u2022\u2022\u2022 4242',
        deliveryPerson: (() => {
          const pool = [
            { id: 'dp_1', name: 'Marcus R.', photoUrl: '', vehicleType: 'car', rating: 4.9 },
            { id: 'dp_2', name: 'Sarah L.', photoUrl: '', vehicleType: 'bike', rating: 4.8 },
            { id: 'dp_3', name: 'James K.', photoUrl: '', vehicleType: 'car', rating: 4.7 },
            { id: 'dp_4', name: 'Priya M.', photoUrl: '', vehicleType: 'bike', rating: 4.6 }
          ];
          return pool[Math.floor(Math.random() * pool.length)];
        })(),
        rating: null,
        review: null
      };

      return {
        ...prev,
        orders: [newOrder, ...prev.orders],
        activeOrderId: orderId,
        cart: {
          restaurantId: null, restaurantName: null, items: [],
          deliveryMode: prev.cart.deliveryMode, scheduledTime: null,
          promoCode: null, promoDiscount: 0, tipAmount: 0, tipPercentage: 18,
          deliveryInstructions: ''
        }
      };
    });
    return orderId;
  }, [state, applyEngine]);

  const toggleFavorite = useCallback((restaurantId) => {
    setState(prev => {
      if (!prev) return prev;
      const favs = prev.user.favoriteRestaurantIds;
      const isFav = favs.includes(restaurantId);
      return {
        ...prev,
        user: {
          ...prev.user,
          favoriteRestaurantIds: isFav
            ? favs.filter(id => id !== restaurantId)
            : [...favs, restaurantId]
        }
      };
    });
  }, []);

  const setDeliveryMode = useCallback((mode) => {
    _writeMode(mode);
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        cart: { ...prev.cart, deliveryMode: mode },
        ui: { ...prev.ui, deliveryMode: mode }
      };
    });
  }, []);

  // Schedule for later. `scheduled` is null (== "Now") or { label, iso }.
  // Bridged: also persist YYYY-MM-DD onto the gym cart via food.set_schedule so
  // remounts / re-projection cannot drop the day before checkout.
  const setScheduledTime = useCallback((scheduled) => {
    const iso = scheduled && scheduled.iso ? String(scheduled.iso) : '';
    const day = iso.length >= 10 ? iso.slice(0, 10) : '';
    // Prefer explicit dinner-date field when present (Header schedule-ahead slots).
    const schedDay = (scheduled && scheduled.date) ? String(scheduled.date).slice(0, 10) : day;
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        ui: { ...prev.ui, scheduledTime: scheduled },
        cart: { ...prev.cart, scheduledTime: scheduled ? (schedDay || iso) : null },
      };
    });
    if (bridged()) {
      bridgeAct('food.set_schedule', { scheduled_delivery: schedDay || '' })
        .then(r => applyEngine(r && r.apps && r.apps[APP]));
    }
  }, [applyEngine]);

  const updateFilters = useCallback((filters) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        ui: { ...prev.ui, activeFilters: { ...prev.ui.activeFilters, ...filters } }
      };
    });
  }, []);

  const setSearchQuery = useCallback((query) => {
    setState(prev => {
      if (!prev) return prev;
      const recentSearches = prev.ui.recentSearches || [];
      let updated = recentSearches;
      if (query && !recentSearches.includes(query)) {
        updated = [query, ...recentSearches].slice(0, 5);
      }
      return {
        ...prev,
        ui: { ...prev.ui, searchQuery: query, recentSearches: updated }
      };
    });
  }, []);

  const rateOrder = useCallback((orderId, rating, review) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        orders: prev.orders.map(o =>
          o.id === orderId ? { ...o, rating, review: review || null } : o
        )
      };
    });
  }, []);

  const updateAddress = useCallback((addressId) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        ui: { ...prev.ui, selectedAddressId: addressId }
      };
    });
  }, []);

  const updateDefaultPayment = useCallback((paymentId) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        user: {
          ...prev.user,
          defaultPaymentId: paymentId,
          paymentMethods: prev.user.paymentMethods.map(pm => ({
            ...pm,
            isDefault: pm.id === paymentId
          }))
        }
      };
    });
  }, []);

  const setTip = useCallback((amount, percentage) => {
    setState(prev => {
      if (!prev) return prev;
      const clamped = Math.min(500, Math.max(0, Number(amount) || 0));
      return {
        ...prev,
        cart: { ...prev.cart, tipAmount: clamped, tipPercentage: percentage }
      };
    });
  }, []);

  // Add a card. The food user profile is entirely client-side (the poll keeps
  // base.user whole — same as add-address/favorite), so this persists in both
  // demo and bridged mode. New card becomes the selected default.
  const addPaymentMethod = useCallback((card) => {
    setState(prev => {
      if (!prev) return prev;
      const id = `pay_${(prev.user.paymentMethods?.length || 0) + 1}_${(card.last4 || 'x')}`;
      const last4 = (card.last4 || card.cardNumber || '').replace(/\D/g, '').slice(-4);
      const type = card.type || (/^4/.test(last4) ? 'visa' : /^5/.test(last4) ? 'mastercard' : 'card');
      const label = card.label || (type === 'paypal' ? 'PayPal' : `${type[0].toUpperCase()}${type.slice(1)} •••• ${last4 || '0000'}`);
      const nu = { id, type, label, last4, expiry: card.expiry || '', isDefault: true };
      return {
        ...prev,
        user: {
          ...prev.user,
          defaultPaymentId: id,
          paymentMethods: [...(prev.user.paymentMethods || []).map(p => ({ ...p, isDefault: false })), nu],
        },
      };
    });
  }, []);

  const cancelOrder = useCallback((orderId) => {
    if (bridged()) {
      bridgeAct('food.cancel_order', { order_id: orderId })
        .then(r => applyEngine(r && r.apps && r.apps[APP]));
      return;
    }
    setState(prev => prev && ({
      ...prev,
      orders: (prev.orders || []).map(o =>
        o.id === orderId ? { ...o, status: 'cancelled' } : o),
    }));
  }, []);

  const applyPromoCode = useCallback((code) => {
    if (bridged()) {
      // the engine owns the code list and the discount; the box used to look
      // codes up in state.promotions, which was always empty
      bridgeAct('food.apply_promo', { code: code || '' })
        .then(r => applyEngine(r && r.apps && r.apps[APP]));
      return; // engine drives the applied/rejected UI in bridged mode
    }
    if (!state) return { error: 'Invalid promo code' };
    const entered = (code || '').trim();
    // Empty code clears an applied promo (Remove button).
    if (!entered) {
      setState(prev => prev && ({
        ...prev,
        cart: { ...prev.cart, promoCode: null, promoDiscount: 0 },
        appliedPromoCode: null,
      }));
      return true;
    }
    const promo = (state.promotions || []).find(
      p => p.code && p.code.toLowerCase() === entered.toLowerCase()
    );
    if (!promo) return { error: 'Invalid promo code' };
    if (promo.expiresAt) {
      const expiry = new Date(promo.expiresAt);
      expiry.setHours(23, 59, 59, 999);
      if (new Date() > expiry) return { error: 'This promo code has expired' };
    }
    if (promo.restaurantId && state.cart.restaurantId !== promo.restaurantId) {
      return { error: 'Promo code not valid for this restaurant' };
    }
    const subtotal = state.cart.items.reduce((s, item) => s + item.totalPrice, 0);
    if (subtotal < (promo.minOrder || 0)) {
      return { error: `Add $${((promo.minOrder || 0) - subtotal).toFixed(2)} more to use this code` };
    }
    // Support percentOff (a 0..1 fraction) alongside discountAmount / discountPercent.
    let discount = 0;
    if (promo.discountAmount > 0) {
      discount = promo.discountAmount;
    } else if (promo.percentOff > 0) {
      discount = subtotal * promo.percentOff;
    } else if (promo.discountPercent > 0) {
      discount = subtotal * (promo.discountPercent / 100);
    }
    discount = Math.round(discount * 100) / 100;
    setState(prev => prev && ({
      ...prev,
      cart: { ...prev.cart, promoCode: entered, promoDiscount: discount }
    }));
    return { ok: true };
  }, [state, applyEngine]);

  const updateUser = useCallback((fields) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        user: { ...prev.user, ...fields }
      };
    });
  }, []);

  const updateDeliveryInstructions = useCallback((instructions) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        cart: { ...prev.cart, deliveryInstructions: instructions }
      };
    });
  }, []);

  const activateUberOne = useCallback(() => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        user: { ...prev.user, uberOneActive: true }
      };
    });
  }, []);

  const addAddress = useCallback((address) => {
    setState(prev => {
      if (!prev) return prev;
      const newAddr = { ...address, id: 'addr_' + Date.now().toString(36) };
      const updatedAddresses = [...prev.user.addresses, newAddr];
      return {
        ...prev,
        user: { ...prev.user, addresses: updatedAddresses }
      };
    });
  }, []);

  const updateOrderStatus = useCallback((orderId, status) => {
    setState(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        orders: prev.orders.map(o => {
          if (o.id !== orderId) return o;
          const updates = { status };
          if (status === 'delivered') {
            updates.deliveredAt = new Date().toISOString();
          }
          return { ...o, ...updates };
        })
      };
    });
  }, []);

  const getDebugState = useCallback(() => {
    return {
      initial_state: initialStateSnapshot,
      current_state: state,
      state_diff: computeStateDiff(initialStateSnapshot, state)
    };
  }, [state, initialStateSnapshot]);

  if (loadError) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#fff', fontFamily: 'var(--font-family)', padding: '24px' }}>
        <div style={{ textAlign: 'center', maxWidth: 520 }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>&#9888;&#65039;</div>
          <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#000', marginBottom: '8px' }}>
            Could not load session
          </div>
          <p style={{ color: '#6B6B6B', fontSize: '15px', lineHeight: 1.5 }}>
            Could not load session <strong>{loadError}</strong> from the state server.
          </p>
        </div>
      </div>
    );
  }

  if (loading || !state) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#fff', fontFamily: 'var(--font-family)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
            <span style={{ color: '#000' }}>Gym</span>
            <span style={{ color: '#06C167' }}>Eats</span>
          </div>
          <p style={{ color: '#6B6B6B', marginTop: '12px' }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <AppContext.Provider value={{
      state,
      initialState: initialStateSnapshot,
      addToCart,
      removeFromCart,
      updateCartItemQuantity,
      clearCart,
      placeOrder,
      toggleFavorite,
      setDeliveryMode,
      setScheduledTime,
      updateFilters,
      setSearchQuery,
      rateOrder,
      updateAddress,
      updateDefaultPayment,
      addPaymentMethod,
      setTip,
      applyPromoCode,
      cancelOrder,
      updateOrderStatus,
      getDebugState,
      updateUser,
      updateDeliveryInstructions,
      activateUberOne,
      addAddress
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
