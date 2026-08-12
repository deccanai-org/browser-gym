import React, { useState } from 'react';
import { useStore } from '../context/StoreContext';
import { startOfMonth, endOfMonth, startOfWeek, endOfWeek, startOfDay, eachDayOfInterval, isSameMonth, isSameDay, format, isWithinInterval, parseISO, setHours, setMinutes, addDays, addWeeks, addMonths, addYears, getISOWeek } from 'date-fns';
import clsx from 'clsx';
import { gymNow, formatTime, overlapsDay } from '../utils/helpers';

const WEEKDAY_LABELS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

export default function MonthView({ onEventClick, onDateClick }) {
  const { state, dispatch } = useStore();
  const [notice, setNotice] = useState('');
  const currentDate = new Date(state.currentDate);

  // "Week starts on" / "Time format" / "Show week numbers" come from Settings;
  // the grid used to be hardcoded to a Sunday start with 24h chips.
  const weekStartsOn = Number(state.settings?.weekStart ?? 0);
  const timeFormat = state.settings?.timeFormat || '12h';
  const showWeekNumbers = !!state.settings?.showWeekNumbers;

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const startDate = startOfWeek(monthStart, { weekStartsOn });
  const endDate = endOfWeek(monthEnd, { weekStartsOn });

  const days = eachDayOfInterval({ start: startDate, end: endDate });
  const weekdayLabels = [...WEEKDAY_LABELS.slice(weekStartsOn), ...WEEKDAY_LABELS.slice(0, weekStartsOn)];
  const weekStarts = days.filter((_, i) => i % 7 === 0);

  // Filter events for this view (My calendars + Other calendars visibility)
  const visibleCalendars = new Set([
    ...state.calendars.filter(c => c.visible).map(c => c.id),
    ...(state.otherCalendars || []).filter(c => c.visible).map(c => c.id),
  ]);
  const rawEvents = state.events.filter(e => visibleCalendars.has(e.calendarId));

  // Expand recurring events from original start + n (no short-month drift)
  const events = [];
  rawEvents.forEach(event => {
    const exceptions = new Set((event.exceptions || []).map(d => String(d).slice(0, 10)));
    if (!exceptions.has(String(event.start).slice(0, 10))) events.push(event);

    if (event.recurring && event.recurring !== 'none') {
      const originalStart = new Date(event.start);
      const viewEnd = addMonths(endDate, 1);
      for (let i = 1; i < 365; i++) {
        let currentEventDate;
        if (event.recurring === 'daily') currentEventDate = addDays(originalStart, i);
        else if (event.recurring === 'weekly') currentEventDate = addWeeks(originalStart, i);
        else if (event.recurring === 'biweekly') currentEventDate = addWeeks(originalStart, i * 2);
        else if (event.recurring === 'monthly') currentEventDate = addMonths(originalStart, i);
        else if (event.recurring === 'yearly') currentEventDate = addYears(originalStart, i);
        else break;
        if (currentEventDate > viewEnd) break;
        if (exceptions.has(currentEventDate.toISOString().slice(0, 10))) continue;
        const duration = new Date(event.end).getTime() - new Date(event.start).getTime();
        events.push({
          ...event,
          id: `${event.id}_recur_${i}`,
          start: currentEventDate.toISOString(),
          end: new Date(currentEventDate.getTime() + duration).toISOString(),
          originalEventId: event.id
        });
      }
    }
  });

  // Named Tailwind color -> hex, so seeded events (which may carry either a hex
  // like "#33B679" or a class like "bg-green-500") always resolve to a real
  // color. Applying the raw class as a className silently broke Month view: a
  // hex became an invalid class and the chip rendered white-on-white.
  const NAMED_COLORS = {
    'bg-blue-500': '#039BE5',
    'bg-green-500': '#33B679',
    'bg-purple-500': '#8E24AA',
    'bg-yellow-500': '#F6BF26',
    'bg-red-500': '#E67C73',
    'bg-orange-500': '#F4511E',
    'bg-indigo-500': '#3F51B5',
    'bg-teal-500': '#009688',
    'bg-pink-500': '#E67C73',
  };

  const getEventColor = (event) => {
    if (event.color && event.color.startsWith('#')) return event.color;
    if (event.color && NAMED_COLORS[event.color]) return NAMED_COLORS[event.color];
    const cal = state.calendars.find(c => c.id === event.calendarId);
    if (cal?.color) {
      if (cal.color.startsWith('#')) return cal.color;
      if (NAMED_COLORS[cal.color]) return NAMED_COLORS[cal.color];
    }
    return '#039BE5';
  };

  const getEventsForDay = (day) => {
    // Plain overlap against the day's half-open range. The old test excluded
    // any event whose end fell on this day, which hid the tail of anything
    // crossing midnight, while still correctly dropping multi-day events whose
    // exclusive end is this day's 00:00.
    const dayStart = startOfDay(day);
    return events.filter(event => overlapsDay(event, dayStart));
  };

  const handleDragStart = (e, eventId) => {
    e.dataTransfer.setData('eventId', eventId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, day) => {
    e.preventDefault();
    const eventId = e.dataTransfer.getData('eventId');
    if (eventId) {
      // Check if it's a virtual recurring instance
      if (eventId.includes('_recur_')) {
        const message = 'Open the recurring event and edit the series to reschedule it.';
        setNotice(message);
        dispatch({ type: 'ADD_NOTICE', payload: { message } });
        return;
      }

      // Preserve the original time, just change the date
      const event = state.events.find(ev => ev.id === eventId);
      if (event) {
        const originalStart = new Date(event.start);
        const newStart = new Date(day);
        newStart.setHours(originalStart.getHours());
        newStart.setMinutes(originalStart.getMinutes());
        
        dispatch({
          type: 'MOVE_EVENT',
          payload: { eventId, newStart: newStart.toISOString() }
        });
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {notice && (
        <div className="flex items-center justify-between px-4 py-2 bg-amber-50 border-b border-amber-200 text-sm text-amber-900">
          <span>{notice}</span>
          <button onClick={() => setNotice('')} className="text-amber-700 hover:text-amber-950">Dismiss</button>
        </div>
      )}
      <div className="flex border-b border-google-border">
        {showWeekNumbers && (
          <div className="w-10 flex-shrink-0 py-2 text-center text-xs font-medium text-text-secondary" title="Week number">
            WK
          </div>
        )}
        <div className="flex-1 grid grid-cols-7">
          {weekdayLabels.map(day => (
            <div key={day} className="py-2 text-center text-xs font-medium text-text-secondary">
              {day}
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 flex">
        {showWeekNumbers && (
          <div className="w-10 flex-shrink-0 grid grid-rows-5 lg:grid-rows-6 border-r border-google-border">
            {weekStarts.map(weekStart => (
              <div
                key={weekStart.toString()}
                className="flex items-start justify-center pt-2 text-[11px] text-text-secondary border-b border-google-border"
              >
                {getISOWeek(weekStart)}
              </div>
            ))}
          </div>
        )}
        <div className="flex-1 grid grid-cols-7 grid-rows-5 lg:grid-rows-6">
        {days.map((day, idx) => {
          const dayEvents = getEventsForDay(day);
          const isToday = isSameDay(day, gymNow());
          
          return (
            <div 
              key={day.toString()} 
              className={clsx(
                "border-b border-r border-google-border min-h-[100px] p-1 transition-colors hover:bg-gray-50 cursor-pointer",
                !isSameMonth(day, currentDate) && "bg-gray-50/50"
              )}
              onClick={() => onDateClick(day)}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, day)}
            >
              <div className="flex justify-center mb-1">
                <span className={clsx(
                  "text-xs w-6 h-6 flex items-center justify-center rounded-full",
                  isToday ? "bg-primary text-white" : "text-text-primary",
                  !isSameMonth(day, currentDate) && !isToday && "text-text-secondary"
                )}>
                  {format(day, 'd')}
                </span>
              </div>
              
              <div className="space-y-1 overflow-hidden max-h-[90px]">
                {dayEvents.slice(0, 4).map(event => (
                  <div
                    key={event.id}
                    draggable={!event.id.includes('_recur_')} // Only original events draggable for simplicity
                    onDragStart={(e) => !event.id.includes('_recur_') && handleDragStart(e, event.id)}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Pass event object AND click event for popover positioning
                      const targetEvent = event.originalEventId 
                        ? state.events.find(ev => ev.id === event.originalEventId) 
                        : event;
                      onEventClick(targetEvent, e);
                    }}
                    style={{
                      backgroundColor: (event.status || '').toLowerCase() === 'cancelled' ? '#9AA0A6' : getEventColor(event),
                      textDecoration: (event.status || '').toLowerCase() === 'cancelled' ? 'line-through' : undefined,
                      opacity: (event.status || '').toLowerCase() === 'cancelled' ? 0.75 : undefined,
                    }}
                    data-event-status={event.status || 'confirmed'}
                    className={clsx(
                      "text-xs px-2 py-0.5 rounded truncate cursor-pointer shadow-sm hover:opacity-80 text-white",
                      event.allDay && "font-medium"
                    )}
                  >
                    {/* Hide time for all-day events */}
                    {!event.allDay && `${formatTime(event.start, timeFormat)} `}
                    {(event.status || '').toLowerCase() === 'cancelled'
                      ? `Cancelled · ${event.title || '(No title)'}`
                      : (event.title || '(No title)')}
                  </div>
                ))}
                {dayEvents.length > 4 && (
                  <div className="text-xs text-text-secondary pl-1 hover:text-text-primary">
                    {dayEvents.length - 4} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
        </div>
      </div>
    </div>
  );
}
