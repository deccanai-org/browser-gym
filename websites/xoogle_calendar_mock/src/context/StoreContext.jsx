import React, { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import { MOCK_USER, DEFAULT_CALENDARS, DEFAULT_SETTINGS, generateMockEvents, getSessionId, fetchCustomState, saveState, initializeData, getInitialState } from '../utils/helpers';
import { addMinutes, differenceInMinutes, addDays, addWeeks, addMonths, addYears } from 'date-fns';
import { bridged, bridgeState, bridgeAct, bridgePoll } from '../lib/bridge';

const APP = 'calendar'; // bridge engine app key for this mock

/** Compute the i-th occurrence start for a recurring master event (1-based). */
function expandOneOccurrence(event, i) {
  if (!event || !i) return null;
  const originalStart = new Date(event.start);
  let currentDate;
  if (event.recurring === 'daily') currentDate = addDays(originalStart, i);
  else if (event.recurring === 'weekly') currentDate = addWeeks(originalStart, i);
  else if (event.recurring === 'monthly') currentDate = addMonths(originalStart, i);
  else if (event.recurring === 'yearly') currentDate = addYears(originalStart, i);
  else return null;
  const duration = new Date(event.end).getTime() - new Date(event.start).getTime();
  return {
    start: currentDate.toISOString(),
    end: new Date(currentDate.getTime() + duration).toISOString(),
  };
}
// In bridged mode: run the gym action, then adopt the engine's authoritative
// per-app state (already in this mock's shape) via the existing LOAD_STATE case.
const applyEngine = (dispatch, r) => {
  // Adopt ONLY engine-owned keys (events/user). Dispatching the full projection
  // snapped the user's view back to Week/2026-05-21, re-showed every calendar, and
  // dropped locally-added calendars + settings after every create/edit/delete/drag.
  // Strip the same client-owned keys the 2.5s poll strips.
  if (r && r.apps && r.apps[APP]) {
    const { view, currentDate, sidebarOpen, calendars, otherCalendars, settings,
            notices, ...engineOwned } = initializeData(null, r.apps[APP]);
    dispatch({ type: 'LOAD_STATE', payload: engineOwned });
  }
};

// Fallback HH:MM extraction from a full ISO datetime, used only when the modal
// didn't attach raw wall-clock values (action.bridge). new Date(iso).toTimeString()
// round-trips the local wall time the user picked (the ISO was produced from a
// local datetime-local value), so it matches what was entered.
const isoToHM = (iso) => {
  if (typeof iso !== 'string' || !iso) return '';
  try { return new Date(iso).toTimeString().slice(0, 5); } catch (_) { return iso.slice(11, 16); }
};
const isoToDay = (iso) => (typeof iso === 'string' ? iso.slice(0, 10) : '');

// The event form collects far more than title/day/time. Forwarding only those
// four meant location, repeat and the rest were typed in and dropped.
//
// guests is NOT forwarded on purpose: this calendar has no invite capability,
// and M239 is built on that absence — an agent that says it added a guest is
// lying. See CalendarEvent in server/apps/calendar/state.py.
const details = (e) => ({
  location: e.location || '',
  description: e.description || '',
  calendar_id: e.calendarId || '',
  all_day: e.allDay ? 'true' : 'false',
  recurring: e.recurring || '',
  // The event modal keeps reminders as an array [{type,minutes}]; read the first
  // one. Reading the (nonexistent) scalar reminderMinutes meant every save sent
  // an empty reminder, so notifications never persisted.
  reminder_minutes: (Array.isArray(e.reminders) && e.reminders.length && e.reminders[0]?.minutes != null)
    ? e.reminders[0].minutes
    : (e.reminderMinutes ?? e.reminder?.minutes ?? ''),
});

const StoreContext = createContext();

const defaultState = {
  user: MOCK_USER,
  calendars: DEFAULT_CALENDARS,
  events: generateMockEvents(),
  view: DEFAULT_SETTINGS.defaultView, // month, week, day, agenda
  currentDate: new Date().toISOString(),
  sidebarOpen: true,
  settings: { ...DEFAULT_SETTINGS },
};

// The calendar opens on the view the user chose as their default. `view` also
// tracks whatever they last switched to mid-session, so on a fresh load the
// saved default has to win — otherwise "Default view: Week" silently loses to
// the month view left behind by the previous session.
const withDefaultView = (data) => {
  if (!data) return data;
  const settings = { ...DEFAULT_SETTINGS, ...(data.settings || {}) };
  return { ...data, settings, view: settings.defaultView || data.view || 'month' };
};

// Deep clone for diffing
const deepClone = (obj) => JSON.parse(JSON.stringify(obj));

const reducer = (state, action) => {
  switch (action.type) {
    case 'SET_VIEW':
      return { ...state, view: action.payload };
    case 'SET_DATE':
      return { ...state, currentDate: action.payload };
    case 'TOGGLE_SIDEBAR':
      return { ...state, sidebarOpen: !state.sidebarOpen };
    case 'ADD_EVENT':
      return { ...state, events: [...state.events, action.payload] };
    case 'UPDATE_EVENT':
      return {
        ...state,
        events: state.events.map(e => e.id === action.payload.id ? action.payload : e)
      };
    case 'DELETE_EVENT': {
      const id = action.payload;
      // Recurring instance ids look like `${masterId}_recur_${n}`.
      const recurMatch = String(id).match(/^(.*)_recur_(\d+)$/);
      if (recurMatch) {
        const masterId = recurMatch[1];
        return {
          ...state,
          events: state.events.map(e => {
            if (e.id !== masterId) return e;
            const instance = expandOneOccurrence(e, parseInt(recurMatch[2], 10));
            const dayKey = instance ? String(instance.start).slice(0, 10) : null;
            const exceptions = [...(e.exceptions || [])];
            if (dayKey && !exceptions.includes(dayKey)) exceptions.push(dayKey);
            return { ...e, exceptions };
          }),
        };
      }
      return {
        ...state,
        events: state.events.filter(e => e.id !== id)
      };
    }
    case 'MOVE_EVENT': {
      const { eventId, newStart } = action.payload;
      const event = state.events.find(e => e.id === eventId);
      if (!event) return state;

      const oldStart = new Date(event.start);
      const oldEnd = new Date(event.end);
      const duration = differenceInMinutes(oldEnd, oldStart);

      const newStartDate = new Date(newStart);
      const newEndDate = addMinutes(newStartDate, duration);

      const updatedEvent = {
        ...event,
        start: newStartDate.toISOString(),
        end: newEndDate.toISOString()
      };

      return {
        ...state,
        events: state.events.map(e => e.id === eventId ? updatedEvent : e)
      };
    }
    case 'TOGGLE_CALENDAR':
      return {
        ...state,
        calendars: state.calendars.map(c =>
          c.id === action.payload ? { ...c, visible: !c.visible } : c
        )
      };
    case 'ADD_CALENDAR':
      return { ...state, calendars: [...state.calendars, action.payload] };
    case 'DELETE_CALENDAR':
      return { ...state, calendars: state.calendars.filter(c => c.id !== action.payload) };
    case 'ADD_OTHER_CALENDAR':
      return { ...state, otherCalendars: [...(state.otherCalendars || []), action.payload] };
    case 'TOGGLE_OTHER_CALENDAR':
      return {
        ...state,
        otherCalendars: (state.otherCalendars || []).map(c =>
          c.id === action.payload ? { ...c, visible: !c.visible } : c
        )
      };
    case 'UPDATE_SETTINGS':
      return { ...state, settings: { ...state.settings, ...action.payload } };
    case 'ADD_NOTICE':
      return {
        ...state,
        notices: [
          ...(state.notices || []),
          { id: action.payload.id || Date.now().toString(), createdAt: new Date().toISOString(), message: action.payload.message }
        ].slice(-5)
      };
    case 'LOAD_STATE':
      return { ...state, ...action.payload };
    default:
      return state;
  }
};

export const StoreProvider = ({ children }) => {
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);
  const [readyToSave, setReadyToSave] = React.useState(false);
  // When a ?sid= is present but its seed can't be loaded, fail loudly instead of
  // silently booting generic demo data (a reviewer can't tell demo from seed).
  const [loadError, setLoadError] = React.useState(null);

  const [state, dispatch] = useReducer(reducer, defaultState, (initial) => {
    // Session-aware: check localStorage with session key BEFORE any async fetch
    const sid = sidRef.current;
    const stored = localStorage.getItem(sid ? `gcal_mock_state_${sid}` : 'gcal_mock_state');
    return withDefaultView(stored ? JSON.parse(stored) : initial);
  });

  const [originalState, setOriginalState] = React.useState(() => {
    const sid = sidRef.current;
    const stored = getInitialState(sid);
    return stored || deepClone(defaultState);
  });

  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;

    const sid = sidRef.current;

    // Bridged mode: the gym engine is the source of truth. Load its state and
    // poll so cross-app effects (e.g. an invite from another app) surface here.
    if (bridged()) {
      // Log a calendar view so the viewed_calendar milestone can fire (the GET
      // view action the verifier watches for). Fire-and-forget, once on mount.
      bridgeAct('calendar.view', {}).catch(() => {});
      // Normalize through initializeData (deep-merge onto defaults) — same path
      // normal seeding uses, so rendering matches the seeded UI.
      bridgeState(APP).then(s => {
        if (s) dispatch({ type: 'LOAD_STATE', payload: initializeData(sid, s) });
        setReadyToSave(true);
      });
// Poll = adopt the ENGINE's world, but keep the keys the engine does not own.
      // Re-adopting wholesale every 2.5s snapped the user's own view state back
      // (which month you were on, your filters, saved-for-later) mid-interaction.
      const stop = bridgePoll(APP, s => {
        if (!s) return;
        const { view, currentDate, sidebarOpen, calendars, otherCalendars, settings,
                notices, ...engineOwned } = initializeData(sid, s);
        dispatch({ type: 'LOAD_STATE', payload: engineOwned });
      });
      return () => stop();
    }

    fetchCustomState(sid).then(customState => {
      if (customState) {
        const data = withDefaultView(initializeData(sid, customState));
        dispatch({ type: 'LOAD_STATE', payload: data });
        setOriginalState(deepClone(data));
        setReadyToSave(true);
        return;
      }

      // The state server returned nothing usable.
      if (sid) {
        // A specific session was requested but its seed could not be loaded.
        // Only trust state already persisted locally for THIS exact sid; other-
        // wise surface a loud error rather than pretending demo data is the seed.
        const stored = localStorage.getItem(`gcal_mock_state_${sid}`);
        if (stored) {
          const data = withDefaultView(JSON.parse(stored));
          dispatch({ type: 'LOAD_STATE', payload: data });
          setOriginalState(deepClone(data));
          setReadyToSave(true);
        } else {
          setLoadError(sid);
        }
        return;
      }

      // No sid in the URL at all -> the demo fallback is legitimate.
      const data = withDefaultView(initializeData(null, null));
      dispatch({ type: 'LOAD_STATE', payload: data });
      const initialStored = getInitialState(null);
      if (initialStored) {
        setOriginalState(initialStored);
      }
      setReadyToSave(true);
    });
  }, []);

  useEffect(() => {
    if (!readyToSave || bridged()) return;
    const sid = sidRef.current;
    saveState(state, sid);
  }, [state, readyToSave]);

  // In bridged mode, route the gym-backed reducer actions (ADD/UPDATE/DELETE and
  // drag-MOVE) to the real engine, then adopt its authoritative state. Everything
  // else (view, date, sidebar, calendars, settings, notices) stays local and
  // dispatches unchanged — as does every action in legacy mode.
  const bridgedDispatch = (action) => {
    if (bridged() && action) {
      if (action.type === 'ADD_EVENT') {
        const e = action.payload || {};
        const b = action.bridge || {};
        // The gym expects a day token (YYYY-MM-DD) + HH:MM times, NOT full ISO.
        // Prefer the raw wall-clock values the modal attached; fall back to
        // parsing the ISO on the event payload.
        bridgeAct('calendar.create', {
          title: e.title || '',
          day: b.day || isoToDay(e.start) || e.date || '',
          start: b.start || isoToHM(e.start) || '19:00',
          end: b.end || isoToHM(e.end) || '20:00',
          ...details(e),
        }).then(r => applyEngine(dispatch, r));
        return;
      }
      if (action.type === 'UPDATE_EVENT') {
        const e = action.payload || {};
        const b = action.bridge || {};
        bridgeAct('calendar.update', {
          event_id: e.id || e.eventId,
          title: e.title || '',
          day: b.day || isoToDay(e.start) || '',
          start: b.start || isoToHM(e.start) || '',
          end: b.end || isoToHM(e.end) || '',
          ...details(e),
        }).then(r => applyEngine(dispatch, r));
        return;
      }
      if (action.type === 'MOVE_EVENT') {
        // Dragging a chip is just an update. It was left local, so a drag looked
        // like it worked and the next 2.5s poll snapped the event back.
        const { eventId, newStart } = action.payload || {};
        const ev = state.events.find(e => e.id === eventId);
        if (ev && newStart) {
          const from = new Date(ev.start), to = new Date(newStart);
          const mins = Math.round((new Date(ev.end) - from) / 60000);
          const end = new Date(to.getTime() + mins * 60000);
          const hhmm = (d) => String(d.getHours()).padStart(2, '0') + ':' +
                              String(d.getMinutes()).padStart(2, '0');
          const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-` +
                             String(d.getDate()).padStart(2, '0');
          bridgeAct('calendar.update', {
            event_id: eventId, title: ev.title,
            day: ymd(to), start: hhmm(to), end: hhmm(end),
          }).then(r => applyEngine(dispatch, r));
        }
        return;
      }
      if (action.type === 'DELETE_EVENT') {
        const id = (action.payload && action.payload.id) ? action.payload.id : action.payload;
        bridgeAct('calendar.delete', { event_id: id }).then(r => applyEngine(dispatch, r));
        return;
      }
    }
    return dispatch(action);
  };

  const getDiff = () => {
    // Simple shallow diff for demonstration
    const diff = {};
    if (state.events.length !== originalState.events.length) diff.events = "Changed";
    if (state.view !== originalState.view) diff.view = { from: originalState.view, to: state.view };
    // ... more detailed diffing logic could go here
    return diff;
  };

  const value = {
    state,
    dispatch: bridgedDispatch,
    originalState,
    getDiff
  };

  if (loadError) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9999, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '24px', textAlign: 'center',
        fontFamily: 'Roboto, Arial, sans-serif',
      }}>
        <div style={{ maxWidth: '480px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
          <h1 style={{ fontSize: '20px', fontWeight: 600, color: '#3C4043', marginBottom: '8px' }}>
            Could not load session
          </h1>
          <p style={{ fontSize: '14px', color: '#5F6368', lineHeight: 1.5 }}>
            Could not load session <code style={{
              background: '#F1F3F4', padding: '1px 6px', borderRadius: '4px', color: '#3C4043',
            }}>{loadError}</code> from the state server. The seeded calendar
            state was not returned, so no data is shown.
          </p>
        </div>
      </div>
    );
  }

  return (
    <StoreContext.Provider value={value}>
      {children}
    </StoreContext.Provider>
  );
};

export const useStore = () => useContext(StoreContext);
