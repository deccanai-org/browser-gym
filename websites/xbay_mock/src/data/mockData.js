import SEED_DEFAULT from './seedDefault.json';
// Self-contained inline-SVG placeholder helpers (no external hosts / picsum).
const initialsAvatar = (initials, bg) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" rx="50" fill="${bg}"/><text x="50" y="50" dy=".35em" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="40" font-weight="bold" fill="#ffffff">${initials}</text></svg>`
  )}`;

const productTile = (label, c1, c2) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs><rect width="400" height="400" fill="url(#g)"/><text x="200" y="205" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="26" font-weight="bold" fill="#ffffff">${label}</text></svg>`
  )}`;

export const INITIAL_STATE = {
  currentUser: {
    id: 'user_1',
    username: 'Alice',
    email: 'alice@xmail.com',
    avatar: initialsAvatar('AA', '#2563eb'),
    feedbackScore: 154,
    feedbackRating: 98.5
  },
  users: [
    {
      id: 'user_1',
      username: 'Alice',
      email: 'alice@xmail.com',
      avatar: initialsAvatar('AA', '#2563eb'),
      feedbackScore: 154,
      feedbackRating: 98.5
    },
    {
      id: 'user_2',
      username: 'RetroGamer99',
      email: 'retro@example.com',
      avatar: initialsAvatar('R', '#16a34a'),
      feedbackScore: 42,
      feedbackRating: 100
    },
    {
      id: 'user_3',
      username: 'CameraPro',
      email: 'camera@example.com',
      avatar: initialsAvatar('C', '#db2777'),
      feedbackScore: 890,
      feedbackRating: 99.2
    }
  ],
  listings: [
    {
      id: 'item_1',
      sellerId: 'user_2',
      title: 'Vintage Nintendo Game Boy Color - Atomic Purple',
      description: 'Authentic Nintendo Game Boy Color in Atomic Purple. Tested and working perfectly. Screen has minor scratches consistent with age. Comes with 2 AA batteries.',
      images: [
        productTile('Game Boy Color', '#7c3aed', '#4c1d95'),
        productTile('Game Boy · Back', '#6d28d9', '#3b0764')
      ],
      type: 'auction',
      startingBid: 40.00,
      currentBid: 55.00,
      buyItNowPrice: 120.00,
      bids: [
        { id: 'bid_1', userId: 'user_3', amount: 45.00, timestamp: Date.now() - 100000, autoBidMax: 45.00 },
        { id: 'bid_2', userId: 'user_1', amount: 55.00, timestamp: Date.now() - 50000, autoBidMax: 60.00 }
      ],
      watchers: ['user_1'],
      views: 124,
      endTime: Date.now() + 86400000 * 2, // 2 days from now
      condition: 'Used',
      shipping: 5.99,
      category: 'Electronics',
      status: 'active'
    },
    {
      id: 'item_2',
      sellerId: 'user_3',
      title: 'Canon EOS R5 Mirrorless Camera Body',
      description: 'Brand new in box. Never opened. Full warranty included.',
      images: [
        productTile('Canon EOS R5', '#111827', '#374151')
      ],
      type: 'fixed',
      price: 3200.00,
      buyItNowPrice: 3200.00,
      bids: [],
      watchers: [],
      views: 45,
      endTime: Date.now() + 86400000 * 5,
      condition: 'New',
      shipping: 0.00,
      category: 'Cameras',
      status: 'active'
    },
    {
      id: 'item_3',
      sellerId: 'user_2',
      title: 'Sony WH-1000XM5 Wireless Noise Canceling Headphones',
      description: 'Used for one flight. Like new condition. Original box and cables included.',
      images: [
        productTile('Sony WH-1000XM5', '#1f2937', '#4b5563')
      ],
      type: 'auction',
      startingBid: 150.00,
      currentBid: 150.00,
      buyItNowPrice: 280.00,
      bids: [],
      watchers: ['user_3'],
      views: 89,
      endTime: Date.now() + 3600000, // 1 hour from now
      condition: 'Open Box',
      shipping: 12.50,
      category: 'Electronics',
      status: 'active'
    },
    {
      id: 'item_4',
      sellerId: 'user_1',
      title: 'Rare First Edition Book - The Hobbit',
      description: 'A collector\'s dream. Good condition considering age. Binding is tight.',
      images: [
        productTile('The Hobbit', '#b45309', '#78350f')
      ],
      type: 'auction',
      startingBid: 500.00,
      currentBid: 500.00,
      buyItNowPrice: null,
      bids: [],
      watchers: ['user_2'],
      views: 312,
      endTime: Date.now() + 86400000 * 7,
      condition: 'Used',
      shipping: 15.00,
      category: 'Books',
      status: 'active'
    }
  ],
  orders: [],
  messages: [
    {
      id: 'msg_1',
      fromId: 'user_2',
      toId: 'user_1',
      listingId: 'item_4',
      subject: 'Question about shipping',
      content: 'Can you ship this internationally?',
      read: false,
      timestamp: Date.now() - 3600000
    }
  ],
  notifications: [],
  feedbacks: [],
  cart: [],
  cartQty: {},
  coupon: null,
  // Ship-to addresses + payment methods on file, so checkout has a real
  // address/payment selection (demo mode; bridged gets these from the engine).
  addresses: [
    { id: 'vm_addr_home', fullName: 'Alice Anderson', street: '100 Park Avenue, Apt 4B', city: 'Brooklyn', state: 'NY', zip: '11201', country: 'United States', isDefault: true },
  ],
  paymentMethods: [
    { id: 'vm_pay_visa', brand: 'Visa', last4: '4242', expiry: '08/27', label: 'Visa •••• 4242', isDefault: true },
    { id: 'vm_pay_mc', brand: 'Mastercard', last4: '5309', expiry: '03/26', label: 'Mastercard •••• 5309', isDefault: false },
    { id: 'vm_pay_paypal', brand: 'PayPal', last4: '', expiry: '', label: 'PayPal', isDefault: false },
  ],
  defaultAddressId: 'vm_addr_home',
  defaultPaymentId: 'vm_pay_visa',
  // Delivery pricing, mirroring the gym engine so demo and bridged charge the
  // same thing: free over the threshold, otherwise the flat fee.
  deliveryFee: 5.99,
  freeDeliveryOver: 35.0
};

// --- Session-based state isolation ---

const BASE_STORAGE_KEY = 'xbay_mock_state';
const BASE_INITIAL_KEY = 'xbay_mock_state_initialState';

function storageKey(sid) { return sid ? `${BASE_STORAGE_KEY}_${sid}` : BASE_STORAGE_KEY; }
function initialKey(sid) { return sid ? `${BASE_INITIAL_KEY}_${sid}` : BASE_INITIAL_KEY; }

export const getSessionId = () => {
  const params = new URLSearchParams(window.location.search);
  const urlSid = params.get('sid');
  if (urlSid) { sessionStorage.setItem('mock_sid', urlSid); return urlSid; }
  return sessionStorage.getItem('mock_sid') || null;
};

export const fetchCustomState = async (sid = null) => {
  try {
    const url = sid ? `/state?sid=${encodeURIComponent(sid)}` : '/state';
    const resp = await fetch(url);
    if (resp.ok) { const d = await resp.json(); if (d.has_custom_state && d.stored_state) return d.stored_state; }
  } catch(e) { console.warn('[xbay_mock] fetchCustomState error:', e); }
  return null;
};

export const saveState = (state, sid = null) => {
  localStorage.setItem(storageKey(sid), JSON.stringify(state));
  const url = sid ? `/post?sid=${encodeURIComponent(sid)}` : '/post';
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'set_current', state }),
  }).catch(e => console.warn('[xbay_mock] saveState server sync error:', e));
};

export const getInitialState = (sid = null) => {
  const s = localStorage.getItem(initialKey(sid)); return s ? JSON.parse(s) : null;
};

function createDefaultData() {
  return { ...INITIAL_STATE };
}

// Identifies WHICH seed a cached store was built from. A browser open across a
// re-seed used to keep serving whatever it cached first — including the
// hardcoded demo listings from before this mock was ever seeded — because the
// cache was returned without being checked, and nothing on screen said so.
const seedFingerprint = (s) => {
  const l = (s && s.listings) || [];
  return `${l.length}:${l[0] ? l[0].id : ''}:${l.length ? l[l.length - 1].id : ''}`;
};

export const initializeData = (sid = null, customState = null) => {
  const sk = storageKey(sid), ik = initialKey(sid);
  if (customState) {
    const data = deepMergeWithDefaults(createDefaultData(), customState);
    data._seedFp = seedFingerprint(customState);
    localStorage.setItem(sk, JSON.stringify(data));
    localStorage.setItem(ik, JSON.stringify(data));
    return data;
  }
  const stored = localStorage.getItem(sk);
  if (stored) {
    const parsed = JSON.parse(stored);
    // Keep the cache only while it belongs to the seed this build ships.
    if (parsed._seedFp === seedFingerprint(SEED_DEFAULT)) {
      if (!localStorage.getItem(ik)) localStorage.setItem(ik, stored);
      return parsed;
    }
    localStorage.removeItem(sk);
    localStorage.removeItem(ik);
  }
  const data = deepMergeWithDefaults(createDefaultData(), SEED_DEFAULT);
  data._seedFp = seedFingerprint(SEED_DEFAULT);
  localStorage.setItem(sk, JSON.stringify(data));
  localStorage.setItem(ik, JSON.stringify(data));
  return data;
};

function normalizeListing(listing, index) {
  // Spread first so projected tip fields (pickupWindow, brand, quantity, …)
  // survive bridge hydrate. A closed whitelist previously dropped them, so the
  // PDP local-pickup shipping row never rendered despite seed→pickupWindow.
  return {
    ...listing,
    id: listing.id || `listing_custom_${index}`,
    sellerId: listing.sellerId || 'user_1',
    title: listing.title || '(No Title)',
    description: listing.description || '',
    images: Array.isArray(listing.images) ? listing.images : [],
    type: listing.type || 'auction',
    startingBid: typeof listing.startingBid === 'number' ? listing.startingBid : 0,
    currentBid: typeof listing.currentBid === 'number' ? listing.currentBid : (typeof listing.startingBid === 'number' ? listing.startingBid : 0),
    buyItNowPrice: listing.buyItNowPrice ?? listing.price ?? null,
    price: listing.price ?? listing.buyItNowPrice ?? null,
    bids: Array.isArray(listing.bids) ? listing.bids : [],
    watchers: Array.isArray(listing.watchers) ? listing.watchers : [],
    views: typeof listing.views === 'number' ? listing.views : 0,
    endTime: listing.endTime || (Date.now() + 86400000 * 7),
    condition: listing.condition || 'Used',
    shipping: typeof listing.shipping === 'number' ? listing.shipping : (typeof listing.shippingCost === 'number' ? listing.shippingCost : (typeof listing.shipping === 'object' && listing.shipping?.cost != null ? listing.shipping.cost : 0)),
    category: listing.category || 'Other',
    status: listing.status || 'active',
    // Explicit keep so callers/tests can see the contract even if spread is
    // later tightened again.
    ...(listing.pickupWindow ? { pickupWindow: listing.pickupWindow } : {}),
    ...(listing.brand ? { brand: listing.brand } : {}),
  };
}

function deepMergeWithDefaults(defaults, custom) {
  if (!custom) return defaults;
  const result = { ...defaults };
  for (const key in custom) {
    if (custom[key] !== null && custom[key] !== undefined) {
      if (key === 'listings' && Array.isArray(custom[key])) {
        result[key] = custom[key].map((l, i) => normalizeListing(l, i));
      } else if (typeof custom[key] === 'object' && !Array.isArray(custom[key]) && typeof defaults[key] === 'object' && !Array.isArray(defaults[key])) {
        result[key] = deepMergeWithDefaults(defaults[key], custom[key]);
      } else { result[key] = custom[key]; }
    }
  }
  return result;
}
