import React, { useState, useEffect, useRef } from 'react';
import { X, Clock, MapPin, AlignLeft, Bell, Trash2, Copy, Repeat, User } from 'lucide-react';
import { useStore } from '../context/StoreContext';
import { generateId } from '../utils/helpers';
import { format } from 'date-fns';
import clsx from 'clsx';
import { gymNow, toLocalInput } from '../utils/helpers';

export default function EventModal({ isOpen, onClose, event, selectedDate }) {
  const { state, dispatch } = useStore();
  const [formData, setFormData] = useState({
    title: '',
    start: '',
    end: '',
    allDay: false,
    location: '',
    description: '',
    calendarId: '',
    color: 'bg-blue-500',
    recurring: 'none',
    reminders: []
  });
  
  const [deletePending, setDeletePending] = useState(false);

  useEffect(() => {
    if (isOpen) {
      if (event) {
        // Edit mode. Stored times are UTC ISO strings; slicing them raw showed
        // the UTC wall time in a local-time input (an event saved for 9:00 AM
        // reopened at 3:30 AM).
        setFormData({
          ...event,
          start: toLocalInput(event.start),
          end: toLocalInput(event.end),
          recurring: event.recurring || 'none',
          reminders: event.reminders || [],
          guestsText: (event.guests || []).join(', '),
        });
      } else {
        // Create mode. Honor the slot that was actually clicked: week/day view
        // passes the clicked time, month view and the Create button pass a bare
        // day, which starts at the next whole hour.
        const clicked = selectedDate ? new Date(selectedDate) : null;
        const defaultStart = clicked || new Date();
        const clickedCarriesTime = !!clicked &&
          (clicked.getHours() !== 0 || clicked.getMinutes() !== 0);
        if (!clickedCarriesTime) {
          const now = new Date();
          defaultStart.setHours(now.getHours() + 1, 0, 0, 0);
        }
        const duration = state.settings?.defaultDuration || 60;
        const defaultEnd = new Date(defaultStart.getTime() + duration * 60000);
        const reminder = state.settings?.defaultReminder || { type: 'popup', minutes: 10 };

        setFormData({
          title: '',
          start: toLocalInput(defaultStart),
          end: toLocalInput(defaultEnd),
          allDay: false,
          location: '',
          description: '',
          calendarId: state.calendars[0]?.id || '',
          color: 'bg-blue-500',
          recurring: 'none',
          reminders: [reminder],
          guestsText: '',
        });
      }
      setDeletePending(false);
    }
  }, [isOpen, event, selectedDate, state.calendars, state.settings]);

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e) => {
      if (e.key !== 'Escape') return;
      if (deletePending) setDeletePending(false);
      else onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [deletePending, isOpen, onClose]);

  if (!isOpen) return null;

  const startDate = (formData.start || '').slice(0, 10);
  const startTime = (formData.start || '').slice(11, 16) || '09:00';
  const endDate = (formData.end || '').slice(0, 10);
  const endTime = (formData.end || '').slice(11, 16) || '10:00';

  const setStartPart = (date, time) => {
    setFormData({ ...formData, start: `${date}T${time}` });
  };
  const setEndPart = (date, time) => {
    setFormData({ ...formData, end: `${date}T${time}` });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const startMs = new Date(formData.start).getTime();
    const endMs = new Date(formData.end).getTime();
    if (!(endMs > startMs)) {
      alert('End time must be after start time.');
      return;
    }
    const guests = String(formData.guestsText || '')
      .split(/[,;\s]+/)
      .map(s => s.trim())
      .filter(Boolean);
    const newEvent = {
      ...formData,
      guests,
      id: event ? event.id : generateId(),
      start: new Date(formData.start).toISOString(),
      end: new Date(formData.end).toISOString()
    };
    delete newEvent.guestsText;

    // Raw wall-clock date + HH:MM straight from the datetime-local inputs,
    // BEFORE the ISO conversion above. Carried on a sibling `bridge` field so
    // bridgedDispatch can forward the shape the gym expects (day + HH:MM)
    // without re-parsing/timezone-shifting the ISO string. The legacy reducer
    // ignores `action.bridge`, so the persisted event stays unchanged.
    const bridge = {
      day: formData.start.slice(0, 10),   // "YYYY-MM-DD"
      start: formData.start.slice(11, 16), // "HH:MM"
      end: formData.end.slice(11, 16),     // "HH:MM"
    };

    if (event) {
      dispatch({ type: 'UPDATE_EVENT', payload: newEvent, bridge });
    } else {
      dispatch({ type: 'ADD_EVENT', payload: newEvent, bridge });
    }
    onClose();
  };

  const handleDelete = () => {
    if (event) setDeletePending(true);
  };

  const confirmDelete = () => {
    if (!event) return;
    dispatch({ type: 'DELETE_EVENT', payload: event.id });
    setDeletePending(false);
    onClose();
  };

  const handleDuplicate = () => {
    if (event) {
      const newEvent = {
        ...formData,
        id: generateId(),
        title: `${formData.title} (Copy)`,
        start: new Date(formData.start).toISOString(),
        end: new Date(formData.end).toISOString(),
      };
      const bridge = {
        day: formData.start.slice(0, 10),
        start: formData.start.slice(11, 16),
        end: formData.end.slice(11, 16),
      };
      dispatch({ type: 'ADD_EVENT', payload: newEvent, bridge });
      onClose();
    }
  };

  // Helper to detect the best display unit for a reminder's minutes value
  const getBestUnit = (minutes) => {
    if (minutes > 0 && minutes % 10080 === 0) return 'weeks';
    if (minutes > 0 && minutes % 1440 === 0) return 'days';
    if (minutes > 0 && minutes % 60 === 0) return 'hours';
    return 'minutes';
  };

  // Helper to get the display value for a given minutes total and unit
  const getDisplayValue = (minutes, unit) => {
    switch (unit) {
      case 'weeks': return minutes / 10080;
      case 'days': return minutes / 1440;
      case 'hours': return minutes / 60;
      default: return minutes;
    }
  };

  // Helper to convert a display value and unit back to total minutes
  const toMinutes = (value, unit) => {
    switch (unit) {
      case 'weeks': return value * 10080;
      case 'days': return value * 1440;
      case 'hours': return value * 60;
      default: return value;
    }
  };

  const addReminder = () => {
    setFormData({
      ...formData,
      reminders: [...formData.reminders, { type: 'popup', minutes: 10 }]
    });
  };

  const removeReminder = (index) => {
    const newReminders = [...formData.reminders];
    newReminders.splice(index, 1);
    setFormData({ ...formData, reminders: newReminders });
  };

  const updateReminder = (index, field, value) => {
    const newReminders = [...formData.reminders];
    newReminders[index] = { ...newReminders[index], [field]: value };
    setFormData({ ...formData, reminders: newReminders });
  };

  // Update reminder when the numeric value changes (convert using current unit)
  const updateReminderValue = (index, displayValue, unit) => {
    const newMinutes = toMinutes(parseInt(displayValue) || 0, unit);
    updateReminder(index, 'minutes', newMinutes);
  };

  // Update reminder when the unit changes (keep same display value, recalculate minutes)
  const updateReminderUnit = (index, newUnit, currentMinutes) => {
    const currentUnit = getBestUnit(currentMinutes);
    const currentDisplayValue = getDisplayValue(currentMinutes, currentUnit);
    const newMinutes = toMinutes(currentDisplayValue, newUnit);
    updateReminder(index, 'minutes', newMinutes);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-100">
          <div className="flex gap-2">
            {event && (
              <>
                <button onClick={handleDelete} className="p-2 hover:bg-gray-200 rounded text-gray-600" title="Delete">
                  <Trash2 size={18} />
                </button>
                <button onClick={handleDuplicate} className="p-2 hover:bg-gray-200 rounded text-gray-600" title="Duplicate">
                  <Copy size={18} />
                </button>
              </>
            )}
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
          <input
            type="text"
            placeholder="Add title"
            required
            className="w-full text-2xl border-b-2 border-gray-200 focus:border-primary outline-none py-1"
            value={formData.title}
            onChange={e => setFormData({ ...formData, title: e.target.value })}
          />

          <div className="flex items-start gap-4">
            <Clock className="text-gray-400 mt-2" size={20} />
            <div className="flex-1 space-y-2">
              {/* Split date + time so CUA agents can set HH:MM without fighting
                  Chromium's segmented datetime-local control (random-looking times). */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <label className="text-xs text-gray-500 w-10">Start</label>
                  <input
                    type="date"
                    required
                    aria-label="Start date"
                    data-test-id="input-edit-start-date"
                    className="border rounded p-1 text-sm"
                    value={startDate}
                    onChange={e => setStartPart(e.target.value, startTime)}
                  />
                  {!formData.allDay && (
                    <input
                      type="time"
                      required
                      aria-label="Start time"
                      data-test-id="input-edit-start"
                      className="border rounded p-1 text-sm"
                      value={startTime}
                      onChange={e => setStartPart(startDate, e.target.value)}
                    />
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <label className="text-xs text-gray-500 w-10">End</label>
                  <input
                    type="date"
                    required
                    aria-label="End date"
                    data-test-id="input-edit-end-date"
                    className="border rounded p-1 text-sm"
                    value={endDate}
                    onChange={e => setEndPart(e.target.value, endTime)}
                  />
                  {!formData.allDay && (
                    <input
                      type="time"
                      required
                      aria-label="End time"
                      data-test-id="input-edit-end"
                      className="border rounded p-1 text-sm"
                      value={endTime}
                      onChange={e => setEndPart(endDate, e.target.value)}
                    />
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input
                    type="checkbox"
                    checked={formData.allDay}
                    onChange={e => setFormData({ ...formData, allDay: e.target.checked })}
                  />
                  All day
                </label>
                
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Repeat size={14} />
                  <select 
                    className="border-none bg-transparent focus:ring-0 cursor-pointer"
                    value={formData.recurring}
                    onChange={e => setFormData({ ...formData, recurring: e.target.value })}
                  >
                    <option value="none">Does not repeat</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Every 2 weeks</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="w-5" /> {/* Spacer for icon alignment */}
            <select
              className="w-full border rounded p-2 text-sm"
              value={formData.calendarId}
              onChange={e => setFormData({ ...formData, calendarId: e.target.value })}
            >
              {state.calendars.map(cal => (
                <option key={cal.id} value={cal.id}>{cal.name}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-4">
            <User className="text-gray-400" size={20} />
            <input
              type="text"
              placeholder="Add guests (comma-separated emails)"
              className="w-full border-b border-gray-200 focus:border-primary outline-none py-1 text-sm"
              value={formData.guestsText || ''}
              onChange={e => setFormData({ ...formData, guestsText: e.target.value })}
            />
          </div>

          <div className="flex items-center gap-4">
            <MapPin className="text-gray-400" size={20} />
            <input
              type="text"
              placeholder="Add location"
              className="w-full border-b border-gray-200 focus:border-primary outline-none py-1 text-sm"
              value={formData.location}
              onChange={e => setFormData({ ...formData, location: e.target.value })}
            />
          </div>

          <div className="flex items-start gap-4">
            <Bell className="text-gray-400 mt-1" size={20} />
            <div className="flex-1 space-y-2">
              {formData.reminders.map((reminder, idx) => {
                const unit = getBestUnit(reminder.minutes);
                const displayValue = getDisplayValue(reminder.minutes, unit);
                return (
                  <div key={idx} className="flex items-center gap-2 text-sm">
                    <select
                      className="border rounded p-1"
                      value={reminder.type}
                      onChange={e => updateReminder(idx, 'type', e.target.value)}
                    >
                      <option value="popup">Notification</option>
                      <option value="email">Email</option>
                    </select>
                    <input
                      type="number"
                      min="0"
                      className="border rounded p-1 w-16"
                      value={displayValue}
                      onChange={e => updateReminderValue(idx, e.target.value, unit)}
                    />
                    <select
                      className="border rounded p-1"
                      value={unit}
                      onChange={e => updateReminderUnit(idx, e.target.value, reminder.minutes)}
                    >
                      <option value="minutes">minutes</option>
                      <option value="hours">hours</option>
                      <option value="days">days</option>
                      <option value="weeks">weeks</option>
                    </select>
                    <span>before</span>
                    <button type="button" onClick={() => removeReminder(idx)} className="text-gray-400 hover:text-gray-600">
                      <X size={14} />
                    </button>
                  </div>
                );
              })}
              <button
                type="button"
                onClick={addReminder}
                className="text-sm text-primary hover:text-primary-hover font-medium"
              >
                Add notification
              </button>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <AlignLeft className="text-gray-400 mt-1" size={20} />
            <textarea
              placeholder="Add description"
              className="w-full border rounded p-2 text-sm h-24 resize-none focus:border-primary outline-none"
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              data-test-id={event ? 'btn-update-event' : 'btn-save-event'}
              className="px-6 py-2 bg-primary text-white rounded hover:bg-primary-hover font-medium"
            >
              Save
            </button>
          </div>
        </form>
      </div>
      {deletePending && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-5 shadow-xl border border-gray-200">
            <h3 className="text-base font-medium text-gray-900 mb-2">Delete event?</h3>
            <p className="text-sm text-gray-600 mb-5">This removes "{formData.title || 'Untitled event'}" from the local calendar state.</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setDeletePending(false)} className="px-4 py-2 text-sm rounded hover:bg-gray-100">Cancel</button>
              <button type="button" onClick={confirmDelete} className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
