import { v4 as uuidv4 } from 'uuid';
import SEED_DEFAULT from './seedDefault.json';
import { addHours, startOfToday, addDays, subDays } from 'date-fns';
import { bridged } from '../lib/bridge';

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

// Every setting the Settings dialog exposes needs a default here, or the
// control renders uncontrolled and its value is silently dropped on save.
export const DEFAULT_SETTINGS = {
  weekStart: 0,
  defaultView: 'month',
  timeFormat: '12h',
  defaultDuration: 60,
  defaultReminder: { type: 'popup', minutes: 10 },
  showWeekNumbers: false,
  showDeclinedEvents: false,
};

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
    settings: { ...DEFAULT_SETTINGS },
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

// "Today" is the REAL current date. The seed ships events around a fixed
// authoring day (_gym_today); rather than freezing the clock to that day —
// which made the calendar drift further out of date every day it stayed
// deployed — the seed events are shifted onto the current week at load time
// (see rebaseSeedToToday). Bridged mode is exempt: there the engine owns the
// world and its own dates must be shown verbatim.
let _gymTodayIso = null;
export const setGymToday = (iso) => { if (iso) _gymTodayIso = iso; };
export const gymNow = () => (_gymTodayIso ? new Date(_gymTodayIso) : new Date());

/** Local-time 'YYYY-MM-DDTHH:mm' for <input type="datetime-local">.
 *  toISOString() would convert to UTC and shift the day/hour the user sees. */
export const toLocalInput = (date) => {
  const d = new Date(date);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};

/** Local 'YYYY-MM-DD' day key (toISOString() rolls over the date near midnight). */
export const toLocalDay = (date) => toLocalInput(date).slice(0, 10);

/**
 * Does an event occupy any part of the day starting at `dayStart`?
 * Half-open on purpose: an event ending exactly at midnight belongs to the day
 * before, but one ending at 12:30 AM has to show on both days.
 */
export const overlapsDay = (event, dayStart) => {
  const dayEnd = new Date(dayStart).getTime() + 86400000;
  return new Date(event.start).getTime() < dayEnd &&
         new Date(event.end).getTime() > new Date(dayStart).getTime();
};

/** Format a time honoring the user's 12h/24h setting. */
export const formatTime = (date, timeFormat = '12h') => {
  const d = new Date(date);
  const p = (n) => String(n).padStart(2, '0');
  if (timeFormat === '24h') return `${p(d.getHours())}:${p(d.getMinutes())}`;
  const h = d.getHours();
  return `${h % 12 || 12}:${p(d.getMinutes())} ${h < 12 ? 'AM' : 'PM'}`;
};

/** Hour-gutter label ("1 PM" / "13:00"). */
export const formatHour = (hour, timeFormat = '12h') => {
  if (timeFormat === '24h') return `${String(hour).padStart(2, '0')}:00`;
  return `${hour % 12 || 12} ${hour < 12 ? 'AM' : 'PM'}`;
};

const DAY_MS = 24 * 60 * 60 * 1000;

/** Whole-day distance between two dates, ignoring time-of-day. */
const dayDelta = (from, to) => {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b - a) / DAY_MS);
};

/**
 * Slide seeded events from the seed's authoring day onto today, preserving each
 * event's offset from that day and its time of day. Without this the calendar
 * opens on a real "today" that has no events on it.
 */
export function rebaseSeedToToday(data) {
  if (!data || !data._gym_today || !Array.isArray(data.events)) return data;
  const seedToday = new Date(data._gym_today);
  if (isNaN(seedToday)) return data;
  const offset = dayDelta(seedToday, new Date());
  if (offset === 0) return data;

  const shift = (iso) => {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    d.setDate(d.getDate() + offset);
    return d.toISOString();
  };

  return {
    ...data,
    _gym_today: new Date().toISOString(),
    currentDate: new Date().toISOString(),
    events: data.events.map(e => ({
      ...e,
      start: shift(e.start),
      end: shift(e.end),
      exceptions: Array.isArray(e.exceptions)
        ? e.exceptions.map(day => toLocalDay(shift(`${String(day).slice(0, 10)}T12:00:00`)))
        : e.exceptions,
    })),
  };
}

// Identifies WHICH seed a cached calendar was built from — see the cache check
// below. Keyed on the events plus the frozen day, since a re-seed can move
// "today" without changing the event count. The real calendar day is folded in
// too: a cache rebased onto yesterday must not be reused today.
const seedFingerprint = (s) => {
  const e = (s && s.events) || [];
  return `${e.length}:${e[0] ? e[0].id : ''}:${(s && s._gym_today) || ''}:r${toLocalDay(new Date())}`;
};

/** Seeded (non-bridged) state is slid onto the real current week. */
const prepareSeed = (data) => (bridged() ? data : rebaseSeedToToday(data));

export const initializeData = (sid = null, customState = null) => {
  const sk = storageKey(sid);
  const ik = initialKey(sid);

  if (customState) {
    const data = prepareSeed(deepMergeWithDefaults(createDefaultData(), customState));
    data._seedFp = seedFingerprint(customState);
    // Only the engine's world gets a pinned clock; seeded state uses real time.
    if (bridged()) setGymToday(data._gym_today);
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
      if (bridged()) setGymToday(p._gym_today);
      if (!localStorage.getItem(ik)) localStorage.setItem(ik, stored);
      return p;
    }
    localStorage.removeItem(sk);
    localStorage.removeItem(ik);
  }

  const data = prepareSeed(deepMergeWithDefaults(createDefaultData(), SEED_DEFAULT));
  data._seedFp = seedFingerprint(SEED_DEFAULT);
  if (bridged()) setGymToday(data._gym_today);
  localStorage.setItem(sk, JSON.stringify(data));
  localStorage.setItem(ik, JSON.stringify(data));
  return data;
};

/** Wipe this session's persisted calendar so the next load re-seeds. */
export const resetSession = (sid = null) => {
  try {
    localStorage.removeItem(storageKey(sid));
    localStorage.removeItem(initialKey(sid));
    sessionStorage.removeItem('mock_sid');
  } catch (_) { /* storage unavailable */ }
};
