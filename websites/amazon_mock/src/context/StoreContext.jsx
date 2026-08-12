import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { INITIAL_DATA, getSessionId, fetchCustomState, saveState, initializeData, gymNow, DEMO_PROMOS } from '../lib/mockData';
import { bridged, bridgeState, bridgeAct, bridgePoll } from '../lib/bridge';

const APP = 'shop'; // bridge engine app key for this mock
// In bridged mode: run the gym action, then adopt the engine's authoritative
// per-app state (already in this mock's shape). Merge so UI-only fields survive.
const applyEngine = (setState, r) => {
  // Normalize through initializeData (deep-merge onto defaults) so the adopted
  // state matches the seeded shape — same path normal seeding uses.
  if (r && r.apps && r.apps[APP]) setState(prev => ({ ...prev, ...initializeData(null, r.apps[APP]) }));
};

const StoreContext = createContext();

export const useStore = () => useContext(StoreContext);

const BASE_INITIAL_KEY = 'shopgym_mock_state_initialState';

export const StoreProvider = ({ children }) => {
  const [state, setState] = useState(() => ({ ...INITIAL_DATA, savedForLater: [] }));
  const [initialState, setInitialState] = useState(JSON.parse(JSON.stringify(INITIAL_DATA)));
  const [hydrated, setHydrated] = useState(false);
  // When a ?sid is present in the URL but its seed state can't be loaded, we must
  // fail loud instead of silently booting generic demo data (a reviewer can't
  // tell demo from a real session otherwise).
  const [loadError, setLoadError] = useState(null);

  // Session ID
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);

  // Session-aware initialization
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    const sid = sidRef.current;

    // Bridged mode: the gym engine is the source of truth. Load its state and
    // poll so cross-app effects (e.g. an order email) surface here too.
    if (bridged()) {
      bridgeState(APP).then(s => {
        if (s) { const data = initializeData(sid, s); setState(data); setInitialState(JSON.parse(JSON.stringify(data))); }
        setHydrated(true);
      });
// Poll = adopt the ENGINE's world, but keep the keys the engine does not own.
      // Re-adopting wholesale every 2.5s snapped the user's own view state back
      // (which month you were on, your filters, saved-for-later) mid-interaction.
      const stop = bridgePoll(APP, s => setState(prev => {
        if (!s) return prev;
        // wishlist is a session-only UI shelf the engine doesn't own; keep it out
        // of engineOwned so a locally-added item survives the poll re-projection.
        const { savedForLater, recentlyViewed, recentSearches, wishlist, ...engineOwned } = initializeData(sid, s);
        return { ...prev, ...engineOwned };
      }));
      return () => stop();
    }

    if (sid) {
      const urlHasSid = new URLSearchParams(window.location.search).has('sid');
      const sessionKey = `${BASE_INITIAL_KEY}_${sid}`;
      const isRefresh = localStorage.getItem(sessionKey) !== null;
      if (isRefresh) {
        const data = initializeData(sid);
        setState(data);
        setInitialState(JSON.parse(JSON.stringify(data)));
        setHydrated(true);
      } else {
        fetchCustomState(sid).then(customState => {
          // A ?sid in the URL must resolve to real seed state. If the state
          // server has none (null/errored), surface it loudly instead of
          // silently falling back to createDefaultData() demo data.
          if (customState == null && urlHasSid) {
            setLoadError(sid);
            setHydrated(true);
            return;
          }
          const data = initializeData(sid, customState);
          setState(data);
          setInitialState(JSON.parse(JSON.stringify(data)));
          setHydrated(true);
        });
      }
    } else {
      const data = initializeData();
      setState(data);
      setInitialState(JSON.parse(JSON.stringify(data)));
      setHydrated(true);
    }
  }, []);

  // Save to localStorage. In bridged mode the engine is the source of truth and
  // the 2.5s poll re-projects it, so persisting every local setState here just
  // floods localStorage with soon-to-be-overwritten copies — gate it off.
  useEffect(() => {
    if (hydrated && !bridged()) saveState(state, sidRef.current);
  }, [state, hydrated]);

  // Actions
  // Returns a promise of the ENGINE's verdict in bridged mode, so the caller can
  // tell the truth instead of confirming an add that did not happen. Most of
  // what this storefront shows is ambient filler the engine has never heard of
  // (188 of 231 products), so a refusal is the common path, not the edge — and
  // it used to be invisible: the cart stayed empty under a green "Added to cart".
  const addToCart = (product, quantity = 1) => {
    // Refuse out-of-stock / zero-stock products (including listing cards).
    if (product && (product.inStock === false || product.stockCount === 0)) return;
    if (bridged()) {
      return bridgeAct('shop.add_to_cart', { product_id: product.id, quantity })
        .then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => {
      // Gift cards are synthetic products not in the catalog — register them so
      // cart/checkout can resolve title + price (otherwise they render blank/$0).
      let products = prev.products || [];
      if (product && product.id && !products.some(p => p.id === product.id)) {
        products = [...products, {
          ...product,
          inStock: true,
          stockCount: null,
          prime: false,
          rating: product.rating ?? 0,
          reviewCount: product.reviewCount ?? 0,
        }];
      }
      // Never let the cart exceed a stock-tracked product's availability
      // (null stockCount = unlimited). The engine enforces this in bridged mode.
      const cap = (product.stockCount != null) ? product.stockCount : Infinity;
      if (cap <= 0) return prev;
      const existing = prev.cart.find(item => item.productId === product.id);
      let newCart;
      if (existing) {
        const q = Math.min(existing.quantity + quantity, cap);
        if (q <= 0) return prev;
        newCart = prev.cart.map(item =>
          item.productId === product.id ? { ...item, quantity: q } : item
        );
      } else {
        const q = Math.min(quantity, cap);
        if (q <= 0) return prev;
        newCart = [...prev.cart, { productId: product.id, quantity: q }];
      }
      const next = { ...prev, products, cart: newCart };
      // Persist immediately so a hard navigation (or QA full-page goto) can't
      // race the React useEffect save and drop the just-added line.
      try { saveState(next, sidRef.current); } catch (_) { /* ignore */ }
      return next;
    });
    return Promise.resolve({ ok: true });
  };

  const removeFromCart = (productId) => {
    if (bridged()) {
      bridgeAct('shop.remove_product', { product_id: productId })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => ({
      ...prev,
      cart: prev.cart.filter(item => item.productId !== productId)
    }));
  };

  const updateCartQty = (productId, quantity) => {
    if (quantity < 1) return removeFromCart(productId);
    if (bridged()) {
      bridgeAct('shop.set_qty', { product_id: productId, quantity })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => {
      const product = (prev.products || []).find(p => p.id === productId);
      const cap = (product && product.stockCount != null) ? product.stockCount : Infinity;
      const q = Math.min(quantity, cap);
      return {
        ...prev,
        cart: prev.cart.map(item =>
          item.productId === productId ? { ...item, quantity: q } : item
        )
      };
    });
  };

  const toggleWishlist = (productId) => {
    setState(prev => {
      const exists = prev.wishlist.includes(productId);
      return {
        ...prev,
        wishlist: exists
          ? prev.wishlist.filter(id => id !== productId)
          : [...prev.wishlist, productId]
      };
    });
  };

  // Save-for-later is a UI shelf, not an engine concept — the poll preserves the
  // savedForLater slice. But the item has to actually LEAVE the engine cart, or
  // the next re-projection puts it straight back and it appears in both places.
  const saveForLater = (productId) => {
    if (bridged()) {
      const item = (state.cart || []).find(i => i.productId === productId);
      bridgeAct('shop.remove_product', { product_id: productId })
        .then(r => {
          applyEngine(setState, r);
          if (item) setState(prev => ({ ...prev,
            savedForLater: [...(prev.savedForLater || []), item] }));
        });
      return;
    }
    setState(prev => {
      const cartItem = prev.cart.find(item => item.productId === productId);
      if (!cartItem) return prev;

      const newCart = prev.cart.filter(item => item.productId !== productId);
      const newSaved = [...(prev.savedForLater || []), cartItem];

      return { ...prev, cart: newCart, savedForLater: newSaved };
    });
  };

  const moveToCart = (productId) => {
    if (bridged()) {
      const item = (state.savedForLater || []).find(i => i.productId === productId);
      bridgeAct('shop.add_to_cart', { product_id: productId, quantity: item?.quantity || 1 })
        .then(r => {
          applyEngine(setState, r);
          setState(prev => ({ ...prev,
            savedForLater: (prev.savedForLater || []).filter(i => i.productId !== productId) }));
        });
      return;
    }
    setState(prev => {
      const savedItem = prev.savedForLater.find(item => item.productId === productId);
      if (!savedItem) return prev;

      const newSaved = prev.savedForLater.filter(item => item.productId !== productId);
      const existingCartItem = prev.cart.find(item => item.productId === productId);

      let newCart;
      if (existingCartItem) {
        newCart = prev.cart.map(item =>
          item.productId === productId
            ? { ...item, quantity: item.quantity + savedItem.quantity }
            : item
        );
      } else {
        newCart = [...prev.cart, savedItem];
      }

      return { ...prev, cart: newCart, savedForLater: newSaved };
    });
  };

  const removeSavedItem = (productId) => {
    setState(prev => ({
      ...prev,
      savedForLater: (prev.savedForLater || []).filter(item => item.productId !== productId)
    }));
  };

  const addToRecentSearches = (term) => {
    setState(prev => {
      const filtered = prev.recentSearches.filter(t => t.toLowerCase() !== term.toLowerCase());
      return { ...prev, recentSearches: [term, ...filtered].slice(0, 10) };
    });
  };

  const clearBrowsingHistory = () => {
    setState(prev => ({ ...prev, recentlyViewed: [] }));
  };

  const addToRecentlyViewed = (productId) => {
    setState(prev => {
      const filtered = prev.recentlyViewed.filter(id => id !== productId);
      return { ...prev, recentlyViewed: [productId, ...filtered].slice(0, 10) };
    });
  };

  const placeOrder = (orderData) => {
    if (bridged()) {
      return bridgeAct('shop.place_order', { payment_id: orderData?.paymentMethod?.id })
        .then(r => {
          applyEngine(setState, r);
          const os = (r.apps && r.apps[APP] && r.apps[APP].orders) || [];
          return os.length ? os[os.length - 1].id : undefined;
        });
    }
    const newOrder = {
      id: `ord-${Date.now()}`,
      date: new Date(gymNow(state)).toISOString(),
      status: 'Processing',
      ...orderData
    };
    setState(prev => {
      // Decrement stock for each ordered line so "Only N left" stays truthful
      // after the order (the engine does this in bridged mode).
      const ordered = {};
      (orderData.items || prev.cart || []).forEach(it => {
        ordered[it.productId] = (ordered[it.productId] || 0) + (it.quantity || 1);
      });
      return {
        ...prev,
        // Only decrement products that TRACK stock (a numeric stockCount). A null
        // stockCount means "unlimited" — leave it untouched, or every order would
        // wrongly drop the whole no-limit catalog to 0.
        products: (prev.products || []).map(p => (ordered[p.id] && p.stockCount != null)
          ? { ...p, stockCount: Math.max(0, p.stockCount - ordered[p.id]) }
          : p),
        orders: [newOrder, ...prev.orders],
        cart: [],
        appliedPromoCode: null
      };
    });
    return newOrder.id;
  };

  const addReview = (review) => {
    setState(prev => ({
      ...prev,
      reviews: [...prev.reviews, { ...review, id: `rev-${Date.now()}`, date: new Date(gymNow(state)).toISOString(), helpful: 0 }]
    }));
  };

  const cancelOrder = (orderId) => {
    if (bridged()) {
      return bridgeAct('shop.cancel_order', { order_id: orderId })
        .then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => ({
      ...prev,
      orders: prev.orders.map(order =>
        order.id === orderId ? { ...order, status: 'Cancelled' } : order
      )
    }));
  };

  const changeOrderAddress = (orderId, addressId, reason) => {
    if (bridged()) {
      return bridgeAct('shop.change_order_address', {
        order_id: orderId,
        address_id: addressId,
        reason: reason || '',
      }).then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => {
      const addr = (prev.user.addresses || []).find(a => a.id === addressId);
      if (!addr) return prev;
      return {
        ...prev,
        orders: prev.orders.map(order =>
          order.id === orderId ? { ...order, shippingAddress: addr } : order
        ),
      };
    });
  };

  const voteHelpful = (reviewId) => {
    setState(prev => ({
      ...prev,
      reviews: prev.reviews.map(r =>
        r.id === reviewId ? { ...r, helpful: (r.helpful || 0) + 1 } : r
      )
    }));
  };

  const updateUserProfile = (profileData) => {
    setState(prev => ({
      ...prev,
      user: { ...prev.user, ...profileData }
    }));
  };

  const addAddress = (address) => {
    if (bridged()) {
      bridgeAct('shop.add_address', {
        label: address.label || address.name || 'Address',
        full_name: address.fullName || address.full_name || address.name || '',
        line1: address.line1 || address.street || address.address || '',
        line2: address.line2 || address.street2 || '',
        city: address.city || '', state: address.state || '',
        zip: address.zip || address.zipCode || address.postalCode || '',
        set_default: !!address.isDefault,
      }).then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => {
      const newAddr = { ...address, id: `addr-${Date.now()}` };
      const addresses = [...(prev.user.addresses || [prev.user.address]), newAddr];
      return { ...prev, user: { ...prev.user, addresses } };
    });
  };

  const setDefaultAddress = (addressId) => {
    if (bridged()) {
      bridgeAct('shop.set_default_address', { address_id: addressId })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => {
      const addresses = (prev.user.addresses || [prev.user.address]).map(a => ({ ...a, isDefault: a.id === addressId }));
      const defaultAddr = addresses.find(a => a.isDefault) || addresses[0];
      return { ...prev, user: { ...prev.user, addresses, address: defaultAddr } };
    });
  };

  const addPaymentMethod = (pm) => {
    if (bridged()) {
      bridgeAct('shop.add_payment', {
        label: pm.label || pm.brand || 'Card', kind: pm.kind || 'credit_card',
        card_number: pm.cardNumber || pm.card_number || pm.number || '',
        expires: pm.expires || pm.expiry || '', cvv: pm.cvv || '',
        nickname: pm.nickname || pm.name || '', set_default: !!pm.isDefault,
      }).then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => {
      const newPm = { ...pm, id: `pm-${Date.now()}` };
      const paymentMethods = [...(prev.user.paymentMethods || [prev.user.paymentMethod]), newPm];
      return { ...prev, user: { ...prev.user, paymentMethods } };
    });
  };

  const setDefaultPaymentMethod = (pmId) => {
    if (bridged()) {
      bridgeAct('shop.set_default_payment', { payment_id: pmId })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => {
      const paymentMethods = (prev.user.paymentMethods || [prev.user.paymentMethod]).map(p => ({ ...p, isDefault: p.id === pmId }));
      const defaultPm = paymentMethods.find(p => p.isDefault) || paymentMethods[0];
      return { ...prev, user: { ...prev.user, paymentMethods, paymentMethod: defaultPm } };
    });
  };

  // Returns the engine's verdict in bridged mode, like addToCart, so a caller
  // that needs to know whether the option actually landed can wait for it. Cart
  // edits happen on a line already on screen and ignore it; the Gift Cards page
  // writes the gift note immediately after creating the line, and must not
  // confirm a message the engine refused.
  const setLineOptions = (productId, opts = {}) => {
    if (bridged()) {
      return bridgeAct('shop.set_line_options', { product_id: productId, ...opts })
        .then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => ({
      ...prev,
      cart: prev.cart.map(item =>
        item.productId === productId ? { ...item, ...opts } : item
      )
    }));
    return Promise.resolve({ ok: true });
  };

  const createSubscription = ({ productId, cadence = 'monthly', deliveries = 4, quantity = 1 }) => {
    if (bridged()) {
      bridgeAct('shop.create_subscription', {
        product_id: productId, cadence, deliveries, quantity,
      }).then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => ({
      ...prev,
      _gym_subscriptions: [...(prev._gym_subscriptions || []), {
        id: `SUB-${Date.now()}`, product_id: productId, cadence,
        deliveries_remaining: deliveries, quantity, status: 'active',
        next_delivery_date: null,
      }],
    }));
  };

  // Pause keeps the plan but skips deliveries until resumed.
  const pauseSubscription = (subscriptionId) => {
    if (bridged()) {
      bridgeAct('shop.pause_subscription', { subscription_id: subscriptionId })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => ({
      ...prev,
      _gym_subscriptions: (prev._gym_subscriptions || []).map(s =>
        s.id === subscriptionId ? { ...s, status: 'paused' } : s),
    }));
  };

  // Cancelling is irreversible for the plan; prefer pause when only skipping a window.
  const cancelSubscription = (subscriptionId) => {
    if (bridged()) {
      bridgeAct('shop.cancel_subscription', { subscription_id: subscriptionId })
        .then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => ({
      ...prev,
      _gym_subscriptions: (prev._gym_subscriptions || []).map(s =>
        s.id === subscriptionId ? { ...s, status: 'cancelled' } : s),
    }));
  };

  const changeOrderShipping = (orderId, shippingSpeed, estimatedDelivery = '') => {
    if (bridged()) {
      return bridgeAct('shop.change_order_shipping', {
        order_id: orderId,
        shipping_speed: shippingSpeed,
        estimated_delivery: estimatedDelivery || '',
      }).then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => ({
      ...prev,
      orders: prev.orders.map(order =>
        order.id === orderId
          ? {
              ...order,
              shippingSpeed,
              estimatedDelivery: estimatedDelivery || order.estimatedDelivery,
            }
          : order
      ),
    }));
    return Promise.resolve({ ok: true });
  };

  const changeOrderItemVariant = (orderId, itemId, variantId) => {
    if (bridged()) {
      return bridgeAct('shop.change_order_item_variant', {
        order_id: orderId, item_id: itemId, variant_id: variantId,
      }).then(r => { applyEngine(setState, r); return r; });
    }
    setState(prev => ({
      ...prev,
      orders: (prev.orders || []).map(order =>
        order.id !== orderId ? order : {
          ...order,
          items: (order.items || []).map(it =>
            it.id === itemId ? { ...it, variantId, variantLabel: variantId } : it),
        }),
    }));
    return Promise.resolve({ ok: true });
  };

  // Filing a return is an irreversible commit, so it has to leave a record —
  // the stock modal only set component state, which meant a filed return was
  // invisible to anything reading the session afterwards.
  const createReturn = ({ orderId, productId, reason, refundMethod = 'original', notes = '' }) => {
    if (bridged()) {
      // The engine validates item_ids against ORDER-ITEM ids (the projected
      // order.items[].id), not product ids, and only accepts 'original_payment'
      // or 'store_credit'. Map both so a filed return actually persists.
      const order = (state.orders || []).find(o => o.id === orderId);
      const item = order && (order.items || []).find(i => i.productId === productId);
      const itemId = (item && item.id) || productId;
      const rm = refundMethod === 'original' ? 'original_payment' : refundMethod;
      // item_ids MUST be a list. A bare string + doseq=True shreds the id into
      // per-character keys and gym initiate_return never persists (mp_104 FN).
      bridgeAct('shop.create_return', {
        order_id: orderId, item_ids: itemId ? [itemId] : [], reason,
        refund_method: rm, notes,
      }).then(r => applyEngine(setState, r));
      return;
    }
    setState(prev => ({
      ...prev,
      returns: [...(prev.returns || []), {
        id: `ret-${Date.now()}`, orderId, productId, reason,
        refundMethod, notes, status: 'Requested',
        createdAt: new Date(gymNow(state)).toISOString(),
      }],
      orders: (prev.orders || []).map(o =>
        o.id === orderId ? { ...o, status: 'Returned' } : o),
    }));
  };

  // Customer Service Contact-us — must leave a durable SupportTicket (same
  // class of bug as the old returns modal that only flipped local React state).
  const createSupportTicket = ({ subject, body, channel = 'customer_service_form' }) => {
    if (bridged()) {
      return bridgeAct('shop.create_support_ticket', {
        subject, body, channel,
      }).then(r => {
        applyEngine(setState, r);
        return r;
      });
    }
    const ticket = {
      id: `TKT-${Date.now()}`,
      user_id: (state.user && state.user.id) || 'u_alice',
      subject, body, channel,
      status: 'submitted',
      created_at: new Date(gymNow(state)).toISOString(),
    };
    setState(prev => ({
      ...prev,
      _gym_support_tickets: [...(prev._gym_support_tickets || []), ticket],
    }));
    return Promise.resolve({ ok: true, ticket_id: ticket.id });
  };

  const enableTwoFa = (code) => {
    if (bridged()) {
      // Return the engine's real verdict (it only accepts code '123456') so the
      // caller can show success/failure instead of an unconditional toast.
      return bridgeAct('shop.enable_two_fa', { code })
        .then(r => {
          applyEngine(setState, r);
          return !!(r && r.apps && r.apps.shop && r.apps.shop.user && r.apps.shop.user.two_fa_enabled);
        });
    }
    setState(prev => ({
      ...prev,
      user: { ...prev.user, two_fa_enabled: true }
    }));
    return Promise.resolve(true);
  };

  const applyPromo = (code) => {
    if (bridged()) {
      // Return the engine's verdict so the Cart shows the REAL outcome
      // (accepted/rejected + the engine's own discount) instead of a hardcoded
      // guess. applyEngine adopts the advanced cart, so _gym_cart_detail
      // .applied_promo becomes authoritative right after this resolves.
      return bridgeAct('shop.apply_promo', { code })
        .then(r => { applyEngine(setState, r); return r; });
    }
    // Demo (no engine): validate against the known promo list and store the
    // applied code in GLOBAL state, so Checkout (a separate component) applies
    // the SAME discount the Cart shows instead of taxing the full subtotal.
    const norm = (code || '').trim().toUpperCase();
    const def = DEMO_PROMOS.find(p => (p.code || '').toUpperCase() === norm);
    if (def) setState(prev => ({ ...prev, appliedPromoCode: def.code }));
    return { ok: !!def, code: def ? def.code : null };
  };

  // Helper to get diff for /go endpoint
  const getStateDiff = () => {
    const diff = {};
    Object.keys(state).forEach(key => {
      if (JSON.stringify(state[key]) !== JSON.stringify(initialState[key])) {
        diff[key] = {
          from: initialState[key],
          to: state[key]
        };
      }
    });
    return diff;
  };

  if (loadError) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: '12px',
        padding: '24px', textAlign: 'center', background: '#fff', color: '#0F1111',
        fontFamily: 'Arial, Helvetica, sans-serif'
      }}>
        <div style={{ fontSize: '48px', lineHeight: 1 }}>⚠️</div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0 }}>
          Could not load session {loadError} from the state server.
        </h1>
        <p style={{ fontSize: '14px', color: '#565959', maxWidth: '520px', margin: 0 }}>
          The session was requested by URL but no seed state was returned. This
          page is not showing demo data. Verify the session id and that the state
          server is reachable, then reload.
        </p>
      </div>
    );
  }

  return (
    <StoreContext.Provider value={{
      state,
      initialState,
      getStateDiff,
      addToCart,
      removeFromCart,
      updateCartQty,
      toggleWishlist,
      saveForLater,
      moveToCart,
      removeSavedItem,
      addToRecentSearches,
      addToRecentlyViewed,
      clearBrowsingHistory,
      placeOrder,
      addReview,
      cancelOrder,
      changeOrderAddress,
      changeOrderShipping,
      changeOrderItemVariant,
      voteHelpful,
      updateUserProfile,
      addAddress,
      setDefaultAddress,
      addPaymentMethod,
      setDefaultPaymentMethod,
      setLineOptions,
      createSubscription,
      pauseSubscription,
      cancelSubscription,
      createReturn,
      createSupportTicket,
      enableTwoFa,
      applyPromo,
    }}>
      {children}
    </StoreContext.Provider>
  );
};
