import React, { createContext, useContext, useReducer, useEffect, useRef, useState } from 'react';
import { INITIAL_STATE, getSessionId, fetchCustomState, saveState, initializeData } from '../data/mockData';
import { bridged, bridgeState, bridgeAct, bridgePoll } from '../lib/bridge';

const APP = 'market'; // bridge engine app key for this mock
// In bridged mode: run the gym action, then adopt the engine's authoritative
// per-app state (already in this mock's shape). Merge so UI-only fields survive.
const applyEngine = (dispatch, r) => {
  // Normalize through initializeData so the adopted state matches the seeded shape.
  if (r && r.apps && r.apps[APP]) dispatch({ type: 'SET_STATE', payload: initializeData(null, r.apps[APP]) });
};

const StoreContext = createContext();

const ACTIONS = {
  PLACE_BID: 'PLACE_BID',
  BUY_NOW: 'BUY_NOW',
  ADD_WATCHLIST: 'ADD_WATCHLIST',
  REMOVE_WATCHLIST: 'REMOVE_WATCHLIST',
  SEND_MESSAGE: 'SEND_MESSAGE',
  MARK_MESSAGE_READ: 'MARK_MESSAGE_READ',
  CREATE_LISTING: 'CREATE_LISTING',
  EDIT_LISTING: 'EDIT_LISTING',
  END_LISTING: 'END_LISTING',
  LEAVE_FEEDBACK: 'LEAVE_FEEDBACK',
  INCREMENT_VIEWS: 'INCREMENT_VIEWS',
  ADD_TO_CART: 'ADD_TO_CART',
  UPDATE_QTY: 'UPDATE_QTY',
  REMOVE_FROM_CART: 'REMOVE_FROM_CART',
  CLEAR_CART: 'CLEAR_CART',
  APPLY_COUPON: 'APPLY_COUPON',
  REMOVE_COUPON: 'REMOVE_COUPON',
  CHECKOUT: 'CHECKOUT',
  MARK_NOTIFICATION_READ: 'MARK_NOTIFICATION_READ',
  MARK_ALL_NOTIFICATIONS_READ: 'MARK_ALL_NOTIFICATIONS_READ',
  SET_STATE: 'SET_STATE',
  RESET: 'RESET'
};

const BASE_INITIAL_KEY = 'ebay_mock_state_initialState';

function reducer(state, action) {
  switch (action.type) {
    case ACTIONS.PLACE_BID: {
      const { listingId, amount, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];

      // Basic validation
      if (amount <= listing.currentBid) return state;

      const currentHighBidderId = listing.bids.length > 0 ? listing.bids[0].userId : null;
      const currentHighBidderMax = listing.bids.length > 0 ? (listing.bids[0].autoBidMax || listing.bids[0].amount) : 0;

      const increment = 1.00;

      let newCurrentBid = listing.currentBid;
      let newBids = [...listing.bids];
      let notifications = [...state.notifications];

      // Scenario 1: No previous bids
      if (listing.bids.length === 0) {
        newCurrentBid = listing.startingBid;

        const newBid = {
          id: `bid_${Date.now()}`,
          userId,
          amount: newCurrentBid,
          autoBidMax: amount,
          timestamp: Date.now()
        };
        newBids = [newBid, ...newBids];
      }
      // Scenario 2: New bid is higher than current price but LOWER than current leader's max
      else if (amount <= currentHighBidderMax && userId !== currentHighBidderId) {
        newCurrentBid = Math.min(amount + increment, currentHighBidderMax);

        const failedBid = {
          id: `bid_${Date.now()}_failed`,
          userId,
          amount: amount,
          autoBidMax: amount,
          timestamp: Date.now()
        };

        const autoBid = {
          id: `bid_${Date.now()}_auto`,
          userId: currentHighBidderId,
          amount: newCurrentBid,
          autoBidMax: currentHighBidderMax,
          timestamp: Date.now() + 1
        };

        newBids = [autoBid, failedBid, ...newBids];

        notifications.push({
          id: `notif_${Date.now()}`,
          userId: userId,
          message: `You were outbid by an automatic bid on ${listing.title}`,
          read: false
        });
      }
      // Scenario 3: New bid is HIGHER than current leader's max
      else if (amount > currentHighBidderMax) {
        newCurrentBid = Math.min(currentHighBidderMax + increment, amount);

        const newBid = {
          id: `bid_${Date.now()}`,
          userId,
          amount: newCurrentBid,
          autoBidMax: amount,
          timestamp: Date.now()
        };

        newBids = [newBid, ...newBids];

        if (currentHighBidderId && currentHighBidderId !== userId) {
          notifications.push({
            id: `notif_${Date.now()}`,
            userId: currentHighBidderId,
            message: `You were outbid on ${listing.title}. Place a higher bid to win!`,
            read: false
          });
        }
      }
      // Scenario 4: Updating own max bid
      else if (userId === currentHighBidderId) {
         const myLatestBid = newBids[0];
         newBids[0] = { ...myLatestBid, autoBidMax: amount };
      }

      const updatedListing = {
        ...listing,
        currentBid: newCurrentBid,
        bids: newBids
      };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      return { ...state, listings: newListings, notifications };
    }

    case ACTIONS.BUY_NOW: {
      const { listingId, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];
      const updatedListing = { ...listing, status: 'sold', endTime: Date.now() };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      const newOrder = {
        id: `order_${Date.now()}`,
        listingId,
        buyerId: userId,
        sellerId: listing.sellerId,
        amount: listing.buyItNowPrice || listing.price,
        date: Date.now(),
        status: 'paid'
      };

      return {
        ...state,
        listings: newListings,
        orders: [...state.orders, newOrder]
      };
    }

    case ACTIONS.ADD_WATCHLIST: {
      const { listingId, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];
      if (listing.watchers.includes(userId)) return state;

      const updatedListing = {
        ...listing,
        watchers: [...listing.watchers, userId]
      };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      return { ...state, listings: newListings };
    }

    case ACTIONS.REMOVE_WATCHLIST: {
      const { listingId, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];
      const updatedListing = {
        ...listing,
        watchers: listing.watchers.filter(id => id !== userId)
      };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      return { ...state, listings: newListings };
    }

    case ACTIONS.SEND_MESSAGE: {
      const { toId, listingId, content, subject } = action.payload;
      const newMessage = {
        id: `msg_${Date.now()}`,
        fromId: state.currentUser.id,
        toId,
        listingId,
        subject,
        content,
        read: false,
        timestamp: Date.now()
      };
      return { ...state, messages: [...state.messages, newMessage] };
    }

    case ACTIONS.MARK_MESSAGE_READ: {
      const { messageId } = action.payload;
      const newMessages = state.messages.map(m =>
        m.id === messageId ? { ...m, read: true } : m
      );
      return { ...state, messages: newMessages };
    }

    case ACTIONS.CREATE_LISTING: {
      const { listing } = action.payload;
      const newListing = {
        ...listing,
        id: `item_${Date.now()}`,
        sellerId: state.currentUser.id,
        bids: [],
        watchers: [],
        views: 0,
        status: 'active'
      };
      return { ...state, listings: [...state.listings, newListing] };
    }

    case ACTIONS.EDIT_LISTING: {
      const { listingId, updates, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;
      const listing = state.listings[listingIndex];
      if (listing.sellerId !== userId) return state;
      const updatedListing = { ...listing, ...updates };
      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;
      return { ...state, listings: newListings };
    }

    case ACTIONS.END_LISTING: {
      const { listingId, userId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];
      if (listing.sellerId !== userId) return state;

      const updatedListing = {
        ...listing,
        status: 'ended',
        endTime: Date.now()
      };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      return { ...state, listings: newListings };
    }

    case ACTIONS.LEAVE_FEEDBACK: {
      const { orderId, rating, comment, fromUserId, toUserId } = action.payload;

      const newFeedback = {
        id: `fb_${Date.now()}`,
        orderId,
        fromUserId,
        toUserId,
        rating,
        comment,
        created: Date.now()
      };

      const userIndex = state.users.findIndex(u => u.id === toUserId);
      let newUsers = [...state.users];

      if (userIndex !== -1) {
        const user = newUsers[userIndex];
        const scoreChange = rating === 'positive' ? 1 : (rating === 'negative' ? -1 : 0);
        newUsers[userIndex] = {
          ...user,
          feedbackScore: user.feedbackScore + scoreChange
        };
      }

      let currentUser = state.currentUser;
      if (currentUser.id === toUserId) {
        const scoreChange = rating === 'positive' ? 1 : (rating === 'negative' ? -1 : 0);
        currentUser = { ...currentUser, feedbackScore: currentUser.feedbackScore + scoreChange };
      }

      return {
        ...state,
        users: newUsers,
        currentUser: currentUser,
        feedbacks: [...(state.feedbacks || []), newFeedback]
      };
    }

    case ACTIONS.INCREMENT_VIEWS: {
      const { listingId } = action.payload;
      const listingIndex = state.listings.findIndex(l => l.id === listingId);
      if (listingIndex === -1) return state;

      const listing = state.listings[listingIndex];
      const updatedListing = { ...listing, views: (listing.views || 0) + 1 };

      const newListings = [...state.listings];
      newListings[listingIndex] = updatedListing;

      return { ...state, listings: newListings };
    }

    case ACTIONS.ADD_TO_CART: {
      const { listingId, quantity = 1 } = action.payload;
      const qty = Math.max(1, parseInt(quantity, 10) || 1);
      const cart = state.cart || [];
      const cartQty = state.cartQty || {};
      // Already in cart -> accumulate the quantity, matching the engine's
      // add_to_cart. Otherwise append the id and record its quantity.
      if (cart.includes(listingId)) {
        return { ...state, cartQty: { ...cartQty, [listingId]: (cartQty[listingId] || 1) + qty } };
      }
      return {
        ...state,
        cart: [...cart, listingId],
        cartQty: { ...cartQty, [listingId]: qty }
      };
    }

    case ACTIONS.UPDATE_QTY: {
      const { listingId, quantity } = action.payload;
      const cart = state.cart || [];
      if (!cart.includes(listingId)) return state;
      const qty = Math.max(1, parseInt(quantity, 10) || 1);
      return { ...state, cartQty: { ...(state.cartQty || {}), [listingId]: qty } };
    }

    case ACTIONS.REMOVE_FROM_CART: {
      const { listingId } = action.payload;
      const cart = state.cart || [];
      const { [listingId]: _dropped, ...cartQty } = state.cartQty || {};
      return { ...state, cart: cart.filter(id => id !== listingId), cartQty };
    }

    case ACTIONS.CLEAR_CART: {
      return { ...state, cart: [], cartQty: {} };
    }

    case ACTIONS.APPLY_COUPON: {
      const { code } = action.payload;
      if (!code) return state;
      return { ...state, coupon: code };
    }

    case ACTIONS.REMOVE_COUPON: {
      return { ...state, coupon: null };
    }

    case ACTIONS.CHECKOUT: {
      const cart = state.cart || [];
      if (cart.length === 0) return state;
      const userId = state.currentUser.id;
      const newOrders = [];
      const newListings = state.listings.map(l => {
        if (!cart.includes(l.id)) return l;
        newOrders.push({
          id: `order_${Date.now()}_${l.id}`,
          listingId: l.id,
          buyerId: userId,
          sellerId: l.sellerId,
          amount: l.buyItNowPrice || l.price || l.currentBid || 0,
          date: Date.now(),
          status: 'paid'
        });
        return { ...l, status: 'sold', endTime: Date.now() };
      });
      return {
        ...state,
        listings: newListings,
        orders: [...state.orders, ...newOrders],
        cart: [],
        cartQty: {},
        coupon: null
      };
    }

    case ACTIONS.MARK_NOTIFICATION_READ: {
      const { notifId } = action.payload;
      const newNotifications = state.notifications.map(n =>
        n.id === notifId ? { ...n, read: true } : n
      );
      return { ...state, notifications: newNotifications };
    }

    case ACTIONS.MARK_ALL_NOTIFICATIONS_READ: {
      const newNotifications = state.notifications.map(n => ({ ...n, read: true }));
      return { ...state, notifications: newNotifications };
    }

    case ACTIONS.SET_STATE:
      return { ...state, ...action.payload };

    case ACTIONS.RESET:
      return INITIAL_STATE;

    default:
      return state;
  }
}

export const StoreProvider = ({ children }) => {
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);
  const [hydrated, setHydrated] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const [state, dispatch] = useReducer(reducer, INITIAL_STATE, (initial) => {
    return initial;
  });

  // Session-aware initialization
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    const sid = sidRef.current;

    // Bridged mode: the gym engine is the source of truth. Load its state and
    // poll so cross-app effects (e.g. an order email) surface here too.
    if (bridged()) {
      // Normalize engine state through initializeData (deep-merge onto defaults)
      // — the SAME path normal seeding uses, so rendering matches the seeded UI.
      bridgeState(APP).then(s => {
        if (s) dispatch({ type: ACTIONS.SET_STATE, payload: initializeData(sid, s) });
        setHydrated(true);
      });
// Poll = adopt the ENGINE's world, but keep the keys the engine does not own.
      // Re-adopting wholesale every 2.5s snapped the user's own view state back
      // (which month you were on, your filters, saved-for-later) mid-interaction.
      const stop = bridgePoll(APP, s => {
        if (!s) return;
        const { searchQuery, filters, ...engineOwned } = initializeData(sid, s);
        dispatch({ type: ACTIONS.SET_STATE, payload: engineOwned });
      });
      return () => stop();
    }

    if (sid) {
      const sessionKey = `${BASE_INITIAL_KEY}_${sid}`;
      const isRefresh = localStorage.getItem(sessionKey) !== null;
      if (isRefresh) {
        const data = initializeData(sid);
        dispatch({ type: ACTIONS.SET_STATE, payload: data });
        setHydrated(true);
      } else {
        fetchCustomState(sid).then(customState => {
          // Loud failure: a sid was requested but no seed state could be loaded.
          // Do NOT silently boot generic demo data — a reviewer can't tell.
          if (customState == null) {
            setLoadError(sid);
            setHydrated(true);
            return;
          }
          const data = initializeData(sid, customState);
          dispatch({ type: ACTIONS.SET_STATE, payload: data });
          setHydrated(true);
        });
      }
    } else {
      const data = initializeData();
      dispatch({ type: ACTIONS.SET_STATE, payload: data });
      setHydrated(true);
    }
  }, []);

  // Save to localStorage
  useEffect(() => {
    if (hydrated && !bridged()) {
      saveState(state, sidRef.current);
    }
  }, [state, hydrated]);

  const placeBid = (listingId, amount) => {
    dispatch({ type: ACTIONS.PLACE_BID, payload: { listingId, amount, userId: state.currentUser.id } });
  };

  const buyNow = (listingId) => {
    if (bridged()) {
      // market.checkout has no per-item param — it checks out the ENTIRE cart.
      // Clear first so Buy It Now purchases only this item, never sweeping in
      // whatever else the user happened to have in the cart.
      bridgeAct('market.clear_cart', {})
        .then(() => bridgeAct('market.add_to_cart', { product_id: listingId, quantity: 1 }))
        .then(() => bridgeAct('market.checkout', {}))
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.BUY_NOW, payload: { listingId, userId: state.currentUser.id } });
  };

  const toggleWatchlist = (listingId) => {
    const listing = state.listings.find(l => l.id === listingId);
    if (listing.watchers.includes(state.currentUser.id)) {
      dispatch({ type: ACTIONS.REMOVE_WATCHLIST, payload: { listingId, userId: state.currentUser.id } });
    } else {
      dispatch({ type: ACTIONS.ADD_WATCHLIST, payload: { listingId, userId: state.currentUser.id } });
    }
  };

  const sendMessage = (toId, listingId, subject, content) => {
    dispatch({ type: ACTIONS.SEND_MESSAGE, payload: { toId, listingId, subject, content } });
  };

  const createListing = (listing) => {
    dispatch({ type: ACTIONS.CREATE_LISTING, payload: { listing } });
  };

  const endListing = (listingId) => {
    dispatch({ type: ACTIONS.END_LISTING, payload: { listingId, userId: state.currentUser.id } });
  };

  const leaveFeedback = (orderId, toUserId, rating, comment) => {
    dispatch({ type: ACTIONS.LEAVE_FEEDBACK, payload: {
      orderId,
      toUserId,
      rating,
      comment,
      fromUserId: state.currentUser.id
    }});
  };

  const incrementViews = (listingId) => {
    dispatch({ type: ACTIONS.INCREMENT_VIEWS, payload: { listingId } });
  };

  const markMessageRead = (messageId) => {
    dispatch({ type: ACTIONS.MARK_MESSAGE_READ, payload: { messageId } });
  };

  const editListing = (listingId, updates) => {
    dispatch({ type: ACTIONS.EDIT_LISTING, payload: { listingId, updates, userId: state.currentUser.id } });
  };

  const addToCart = (listingId, quantity = 1) => {
    if (bridged()) {
      bridgeAct('market.add_to_cart', { product_id: listingId, quantity })
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.ADD_TO_CART, payload: { listingId, quantity } });
  };

  const updateQty = (listingId, quantity) => {
    if (bridged()) {
      bridgeAct('market.set_qty', { product_id: listingId, quantity })
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.UPDATE_QTY, payload: { listingId, quantity } });
  };

  const removeFromCart = (listingId) => {
    if (bridged()) {
      bridgeAct('market.remove', { product_id: listingId })
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.REMOVE_FROM_CART, payload: { listingId } });
  };

  const clearCart = () => {
    if (bridged()) {
      bridgeAct('market.clear_cart', {})
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.CLEAR_CART });
  };

  const applyCoupon = (code) => {
    if (bridged()) {
      bridgeAct('market.apply_coupon', { code })
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.APPLY_COUPON, payload: { code } });
  };

  const removeCoupon = () => {
    if (bridged()) {
      bridgeAct('market.remove_coupon', {})
        .then(r => applyEngine(dispatch, r));
      return;
    }
    dispatch({ type: ACTIONS.REMOVE_COUPON });
  };

  const checkout = () => {
    if (bridged()) {
      return bridgeAct('market.checkout', {})
        .then(r => applyEngine(dispatch, r));
    }
    dispatch({ type: ACTIONS.CHECKOUT });
    return Promise.resolve();
  };

  const markNotificationRead = (notifId) => {
    dispatch({ type: ACTIONS.MARK_NOTIFICATION_READ, payload: { notifId } });
  };

  const markAllNotificationsRead = () => {
    dispatch({ type: ACTIONS.MARK_ALL_NOTIFICATIONS_READ });
  };

  if (loadError) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: '12px',
        padding: '24px', textAlign: 'center',
        background: '#fef2f2', color: '#7f1d1d',
        fontFamily: 'Arial, Helvetica, sans-serif'
      }}>
        <div style={{ fontSize: '48px' }}>⚠️</div>
        <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0 }}>
          Could not load session from the state server.
        </h1>
        <p style={{ fontSize: '15px', margin: 0 }}>
          Session <code style={{ fontWeight: 700 }}>{loadError}</code> has no stored state, or the state server is unreachable.
        </p>
      </div>
    );
  }

  return (
    <StoreContext.Provider value={{
      state,
      dispatch,
      placeBid,
      buyNow,
      toggleWatchlist,
      sendMessage,
      markMessageRead,
      createListing,
      editListing,
      endListing,
      leaveFeedback,
      incrementViews,
      addToCart,
      updateQty,
      removeFromCart,
      clearCart,
      applyCoupon,
      removeCoupon,
      checkout,
      markNotificationRead,
      markAllNotificationsRead
    }}>
      {children}
    </StoreContext.Provider>
  );
};

export const useStore = () => useContext(StoreContext);
