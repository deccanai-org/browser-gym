import { v4 as uuidv4 } from 'uuid';
import SEED_DEFAULT from './seedDefault.json';
import { addHours, startOfToday, addDays, subDays } from 'date-fns';

export const generateId = () => uuidv4();

export const MOCK_USER = {
  id: 'u1',
  username: 'Alice Anderson',
  email: 'alice@shopgym.com',
  avatar: null
};

export const DEFAULT_CALENDARS = [
  { id: 'c1', name: 'Personal', color: 'bg-blue-500', textColor: 'text-white', visible: true, userId: 'u1' },
  { id: 'c2', name: 'Work', color: 'bg-green-500', textColor: 'text-white', visible: true, userId: 'u1' },
  { id: 'c3', name: 'Family', color: 'bg-purple-500', textColor: 'text-white', visible: true, userId: 'u1' },
  { id: 'c4', name: 'Holidays', color: 'bg-yellow-500', textColor: 'text-white', visible: true, userId: 'u1' }
];

// Google-style event/calendar color palette. Consumed by AddCalendarModal's
// swatch picker (each entry needs id/name/hex).
export const EVENT_COLORS = [
  { id: 'peacock', name: 'Peacock', hex: '#039BE5' },
  { id: 'basil', name: 'Basil', hex: '#33B679' },
  { id: 'grape', name: 'Grape', hex: '#8E24AA' },
  { id: 'tangerine', name: 'Tangerine', hex: '#F4511E' },
  { id: 'flamingo', name: 'Flamingo', hex: '#E67C73' },
  { id: 'banana', name: 'Banana', hex: '#F6BF26' },
  { id: 'sage', name: 'Sage', hex: '#0B8043' },
];

export const generateMockEvents = () => {
  const today = startOfToday();

  return [
    {
      id: generateId(),
      calendarId: 'c2',
      title: 'Team Standup',
      start: addHours(today, 10).toISOString(),
      end: addHours(today, 11).toISOString(),
      allDay: false,
      location: 'Conference Room A',
      description: 'Daily sync with the team',
      guests: ['alice@example.com', 'bob@example.com'],
      color: 'bg-green-500'
    },
    {
      id: generateId(),
      calendarId: 'c1',
      title: 'Lunch with Sarah',
      start: addHours(today, 12).toISOString(),
      end: addHours(today, 13).toISOString(),
      allDay: false,
      location: 'Downtown Cafe',
      description: '',
      guests: [],
      color: 'bg-blue-500'
    },
    {
      id: generateId(),
      calendarId: 'c3',
      title: 'Family Dinner',
      start: addHours(today, 19).toISOString(),
      end: addHours(today, 21).toISOString(),
      allDay: false,
      location: 'Home',
      description: 'Pizza night',
      guests: [],
      color: 'bg-purple-500'
    },
    {
      id: generateId(),
      calendarId: 'c2',
      title: 'Project Review',
      start: addDays(addHours(today, 14), 1).toISOString(),
      end: addDays(addHours(today, 16), 1).toISOString(),
      allDay: false,
      location: 'Zoom',
      description: 'Q3 Review',
      guests: [],
      color: 'bg-green-500'
    },
    {
      id: generateId(),
      calendarId: 'c4',
      title: 'Vacation',
      start: subDays(today, 2).toISOString(),
      end: today.toISOString(),
      allDay: true,
      location: 'Hawaii',
      description: 'Relaxing',
      guests: [],
      color: 'bg-yellow-500'
    }
  ];
};

export const getContrastColor = (hexColor) => {
  // Simple check for mock purposes - assuming standard tailwind colors mapped
  return 'white';
};

// --- Session-based state isolation ---

const BASE_STORAGE_KEY = 'gcal_mock_state';
const BASE_INITIAL_KEY = 'gcal_mock_state_initialState';

function storageKey(sid) {
  return sid ? `${BASE_STORAGE_KEY}_${sid}` : BASE_STORAGE_KEY;
}

function initialKey(sid) {
  return sid ? `${BASE_INITIAL_KEY}_${sid}` : BASE_INITIAL_KEY;
}

export const getSessionId = () => {
  const params = new URLSearchParams(window.location.search);
  const urlSid = params.get('sid');
  if (urlSid) {
    sessionStorage.setItem('mock_sid', urlSid);
    return urlSid;
  }
  return sessionStorage.getItem('mock_sid') || null;
};

export const fetchCustomState = async (sid = null) => {
  try {
    const url = sid ? `/state?sid=${encodeURIComponent(sid)}` : '/state';
    const resp = await fetch(url);
    if (resp.ok) {
      const d = await resp.json();
      if (d.has_custom_state && d.stored_state) return d.stored_state;
    }
  } catch (e) {
    console.warn('No custom state available, using defaults');
  }
  return null;
};

export const saveState = (state, sid = null) => {
  localStorage.setItem(storageKey(sid), JSON.stringify(state));
  const url = sid ? `/post?sid=${encodeURIComponent(sid)}` : '/post';
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'set_current', state, merge: false })
  }).catch(() => {});
};

export const getInitialState = (sid = null) => {
  const s = localStorage.getItem(initialKey(sid));
  return s ? JSON.parse(s) : null;
};

function createDefaultData() {
  return {
    user: MOCK_USER,
    calendars: DEFAULT_CALENDARS,
    events: generateMockEvents(),
    view: 'month',
    currentDate: new Date().toISOString(),
    sidebarOpen: true,
    settings: {
      weekStart: 0,
      defaultDuration: 60,
    }
  };
}

// Includes c5 (Birthdays) + a few spares; the projection ships a 5th calendar
// and force-reassigning its events to c1 silently moved them to Personal.
const VALID_CALENDAR_IDS = new Set(['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8']);

function normalizeEvent(event, index) {
  const calendarId = VALID_CALENDAR_IDS.has(event.calendarId) ? event.calendarId : 'c1';
  const calendarColors = { c1: 'bg-blue-500', c2: 'bg-green-500', c3: 'bg-purple-500', c4: 'bg-yellow-500',
    c5: 'bg-pink-500', c6: 'bg-red-500', c7: 'bg-indigo-500', c8: 'bg-teal-500' };
  return {
    id: event.id || generateId(),
    calendarId,
    title: event.title || '(No Title)',
    start: event.start || event.startTime || new Date().toISOString(),
    end: event.end || event.endTime || addHours(new Date(), 1).toISOString(),
    allDay: event.allDay ?? false,
    location: event.location || '',
    description: event.description || '',
    guests: Array.isArray(event.guests) ? event.guests : [],
    color: event.color || calendarColors[calendarId] || 'bg-blue-500',
    recurring: event.recurring || 'none',
    reminders: Array.isArray(event.reminders) && event.reminders.length
      ? event.reminders
      : (event.reminderMinutes != null && event.reminderMinutes !== ''
          ? [{ type: 'popup', minutes: Number(event.reminderMinutes) }]
          : []),
  };
}

function deepMergeWithDefaults(defaults, custom) {
  if (!custom) return defaults;
  const result = { ...defaults };
  for (const key in custom) {
    if (custom[key] !== null && custom[key] !== undefined) {
      if (key === 'events' && Array.isArray(custom[key])) {
        result[key] = custom[key].map((e, i) => normalizeEvent(e, i));
      } else if (typeof custom[key] === 'object' && !Array.isArray(custom[key]) && typeof defaults[key] === 'object' && !Array.isArray(defaults[key])) {
        result[key] = deepMergeWithDefaults(defaults[key], custom[key]);
      } else {
        result[key] = custom[key];
      }
    }
  }
  return result;
}

// The gym's frozen "today". Captured from the projection's _gym_today so every
// today()/now() reference uses the frozen clock (2026-05-21, where the seed
// events live) instead of the real system date. Falls back to real time in demo.
let _gymTodayIso = null;
export const setGymToday = (iso) => { if (iso) _gymTodayIso = iso; };
export const gymNow = () => (_gymTodayIso ? new Date(_gymTodayIso) : new Date());

// Identifies WHICH seed a cached calendar was built from — see the cache check
// below. Keyed on the events plus the frozen day, since a re-seed can move
// "today" without changing the event count.
const seedFingerprint = (s) => {
  const e = (s && s.events) || [];
  return `${e.length}:${e[0] ? e[0].id : ''}:${(s && s._gym_today) || ''}`;
};

export const initializeData = (sid = null, customState = null) => {
  const sk = storageKey(sid);
  const ik = initialKey(sid);

  if (customState) {
    const data = deepMergeWithDefaults(createDefaultData(), customState);
    data._seedFp = seedFingerprint(customState);
    setGymToday(data._gym_today);
    localStorage.setItem(sk, JSON.stringify(data));
    localStorage.setItem(ik, JSON.stringify(data));
    return data;
  }

  const stored = localStorage.getItem(sk);
  if (stored) {
    const p = JSON.parse(stored);
    // Keep the cache only while it belongs to the seed this build ships. A
    // browser open across a re-seed used to keep serving its first cache —
    // including the demo calendar from before this mock was ever seeded.
    if (p._seedFp === seedFingerprint(SEED_DEFAULT)) {
      setGymToday(p._gym_today);
      if (!localStorage.getItem(ik)) localStorage.setItem(ik, stored);
      return p;
    }
    localStorage.removeItem(sk);
    localStorage.removeItem(ik);
  }

  const data = deepMergeWithDefaults(createDefaultData(), SEED_DEFAULT);
  data._seedFp = seedFingerprint(SEED_DEFAULT);
  setGymToday(data._gym_today);
  localStorage.setItem(sk, JSON.stringify(data));
  localStorage.setItem(ik, JSON.stringify(data));
  return data;
};
