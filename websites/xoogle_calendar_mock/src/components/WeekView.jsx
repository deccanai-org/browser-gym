import React, { useRef, useEffect, useState } from 'react';
import { useStore } from '../context/StoreContext';
import { startOfWeek, endOfWeek, eachDayOfInterval, format, isSameDay, addMinutes, startOfDay, endOfDay, differenceInMinutes, addDays, addWeeks, addMonths, addYears } from 'date-fns';
import { gymNow, formatTime, formatHour, overlapsDay } from '../utils/helpers';

const HOUR_HEIGHT = 60; // px per hour

function expandRecurringEvents(rawEvents, viewStart, viewEnd) {
  const events = [];
  const extendedEnd = addDays(viewEnd, 7);

  rawEvents.forEach(event => {
    const exceptions = new Set((event.exceptions || []).map(d => String(d).slice(0, 10)));
    const startKey = String(event.start).slice(0, 10);
    if (!exceptions.has(startKey)) events.push(event);

    if (event.recurring && event.recurring !== 'none') {
      const originalStart = new Date(event.start);
      for (let i = 1; i < 200; i++) {
        let currentDate;
        if (event.recurring === 'daily') currentDate = addDays(originalStart, i);
        else if (event.recurring === 'weekly') currentDate = addWeeks(originalStart, i);
        else if (event.recurring === 'biweekly') currentDate = addWeeks(originalStart, i * 2);
        else if (event.recurring === 'monthly') currentDate = addMonths(originalStart, i);
        else if (event.recurring === 'yearly') currentDate = addYears(originalStart, i);
        else break;

        if (currentDate > extendedEnd) break;

        const dayKey = currentDate.toISOString().slice(0, 10);
        if (exceptions.has(dayKey)) continue;

        const duration = new Date(event.end).getTime() - new Date(event.start).getTime();
        events.push({
          ...event,
          id: `${event.id}_recur_${i}`,
          start: currentDate.toISOString(),
          end: new Date(currentDate.getTime() + duration).toISOString(),
          originalEventId: event.id
        });
      }
    }
  });
  return events;
}

// Compute overlap groups and assign columns
function computeEventLayout(dayEvents) {
  if (dayEvents.length === 0) return [];

  const sorted = [...dayEvents].sort((a, b) => new Date(a.start) - new Date(b.start));
  const groups = [];
  let currentGroup = [];

  for (const event of sorted) {
    const eventStart = new Date(event.start).getTime();
    const eventEnd = new Date(event.end).getTime();

    if (currentGroup.length === 0) {
      currentGroup = [event];
    } else {
      const groupEnd = Math.max(...currentGroup.map(e => new Date(e.end).getTime()));
      if (eventStart < groupEnd) {
        currentGroup.push(event);
      } else {
        groups.push([...currentGroup]);
        currentGroup = [event];
      }
    }
  }
  if (currentGroup.length > 0) groups.push(currentGroup);

  const result = [];
  for (const group of groups) {
    const n = group.length;
    group.forEach((event, idx) => {
      result.push({ event, col: idx, totalCols: n });
    });
  }
  return result;
}

// H-06: Helper to snap minutes to 30-minute grid
function snapTo30Min(minutes) {
  return Math.round(minutes / 30) * 30;
}

export default function WeekView({ onEventClick, onDateClick }) {
  const { state, dispatch } = useStore();
  const currentDate = new Date(state.currentDate);
  const scrollRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(() => gymNow());
  useEffect(() => {
    const tick = () => setCurrentTime(gymNow());
    tick();
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, []);

  // H-06: Drag-to-create state
  const [dragCreate, setDragCreate] = useState(null); // { day, startMinutes, endMinutes, dayIndex }
  const dragCreateRef = useRef(null);
  const isDraggingCreate = useRef(false);

  // "Week starts on" and "Time format" are user settings; both were hardcoded.
  const weekStartsOn = Number(state.settings?.weekStart ?? 0);
  const timeFormat = state.settings?.timeFormat || '12h';

  // Determine date range based on view type
  let days;
  if (state.view === 'day') {
    days = [currentDate];
  } else {
    const start = startOfWeek(currentDate, { weekStartsOn });
    const end = endOfWeek(currentDate, { weekStartsOn });
    days = eachDayOfInterval({ start, end });
  }

  // Scroll to 7 AM on mount
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 7 * HOUR_HEIGHT;
    }
  }, [state.view]);


  const visibleCalendars = new Set([
    ...state.calendars.filter(c => c.visible).map(c => c.id),
    ...(state.otherCalendars || []).filter(c => c.visible).map(c => c.id),
  ]);
  const rawEvents = state.events.filter(e => visibleCalendars.has(e.calendarId));
  const allEvents = expandRecurringEvents(rawEvents, startOfDay(days[0]), endOfDay(days[days.length - 1]));

  // Separate all-day and timed events
  const allDayEvents = allEvents.filter(e => e.allDay);
  const timedEvents = allEvents.filter(e => !e.allDay);

  // Scroll so the frozen now-line stays near the top AND today's next timed
  // event (often evening — e.g. Team Meeting 6:30 PM) remains in the viewport.
  // Old fixed scroll-to-7am hid evening blocks on week view (~8h tall).
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const apply = () => {
      const now = gymNow();
      const nowHour = now.getHours() + now.getMinutes() / 60;
      const h = el.clientHeight;
      const viewportHours = Math.max(6, (h || 480) / HOUR_HEIGHT);
      let coverUntil = Math.max(nowHour + 2, 19);
      for (const ev of timedEvents) {
        const start = new Date(ev.start);
        if (!isSameDay(start, now)) continue;
        const startHour = start.getHours() + start.getMinutes() / 60;
        if (startHour >= nowHour - 0.5) {
          coverUntil = Math.max(coverUntil, startHour + 0.75);
        }
      }
      const preferNow = Math.max(0, nowHour - 1);
      const preferCover = Math.max(0, coverUntil - viewportHours + 0.35);
      const scrollHour = Math.max(preferNow, preferCover);
      el.scrollTop = scrollHour * HOUR_HEIGHT;
    };
    apply();
    if (el.clientHeight < 80) {
      const id = requestAnimationFrame(apply);
      return () => cancelAnimationFrame(id);
    }
  }, [state.view, state._gym_today, state._gym_now, timedEvents]);

  const timeSlots = Array.from({ length: 24 }, (_, i) => i);

  const getEventColor = (event) => {
    if (event.color && event.color.startsWith('#')) return event.color;
    const cal = state.calendars.find(c => c.id === event.calendarId);
    return cal?.color || '#039BE5';
  };

  const getEventStyle = (event, dayStart) => {
    const start = new Date(event.start);
    const end = new Date(event.end);
    const startMinutes = differenceInMinutes(start, dayStart);
    const durationMinutes = Math.max(differenceInMinutes(end, start), 30);

    return {
      top: `${(startMinutes / 60) * HOUR_HEIGHT}px`,
      height: `${(durationMinutes / 60) * HOUR_HEIGHT}px`,
    };
  };

  // Current time line position (minutes from midnight)
  const currentTimeMinutes = currentTime.getHours() * 60 + currentTime.getMinutes();
  const currentTimeTop = (currentTimeMinutes / 60) * HOUR_HEIGHT;

  const handleDragStart = (e, eventId) => {
    e.dataTransfer.setData('eventId', eventId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, day, hour) => {
    e.preventDefault();
    const eventId = e.dataTransfer.getData('eventId');
    if (eventId) {
      // M-14: Guard against dropping recurring event instances
      if (eventId.includes('_recur_')) return;
      const event = state.events.find(ev => ev.id === eventId);
      if (event) {
        // M-13: Snap to nearest 30-minute mark using cursor position within slot
        const slotRect = e.currentTarget.getBoundingClientRect();
        const relY = e.clientY - slotRect.top;
        const slotFraction = Math.max(0, Math.min(1, relY / HOUR_HEIGHT));
        const minutes = slotFraction >= 0.5 ? 30 : 0;
        const newStart = new Date(day);
        newStart.setHours(hour, minutes, 0, 0);
        dispatch({ type: 'MOVE_EVENT', payload: { eventId, newStart: newStart.toISOString() } });
      }
    }
  };

  const isDayView = state.view === 'day';
  const labelWidth = '56px';

  // H-06: Drag-to-create mouse handlers
  // Helper: compute minutes from midnight given a Y offset within the column container
  const getMinutesFromY = (colEl, clientY) => {
    const rect = colEl.getBoundingClientRect();
    const relY = clientY - rect.top;
    const rawMinutes = (relY / HOUR_HEIGHT) * 60;
    return Math.max(0, Math.min(23 * 60 + 59, rawMinutes));
  };

  const handleGridMouseDown = (e, day, dayIndex) => {
    // Only initiate on left-click on the background (not on event chips)
    if (e.button !== 0) return;
    if (e.target.closest('[data-event-chip]')) return;
    e.preventDefault();

    const startMinutes = snapTo30Min(getMinutesFromY(e.currentTarget, e.clientY));
    const endMinutes = startMinutes + 60;

    const newDragCreate = { day, startMinutes, endMinutes, dayIndex };
    dragCreateRef.current = newDragCreate;
    isDraggingCreate.current = false;
    setDragCreate(newDragCreate);

    const onMouseMove = (moveEvt) => {
      const colEls = document.querySelectorAll('[data-day-col]');
      const colEl = colEls[dayIndex];
      if (!colEl) return;
      const curMinutes = snapTo30Min(getMinutesFromY(colEl, moveEvt.clientY));
      const start = Math.min(dragCreateRef.current.startMinutes, curMinutes);
      const end = Math.max(dragCreateRef.current.startMinutes + 30, curMinutes + 30);
      isDraggingCreate.current = true;
      const updated = { ...dragCreateRef.current, endMinutes: end, startMinutes: start };
      dragCreateRef.current = updated;
      setDragCreate({ ...updated });
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);

      const created = dragCreateRef.current;
      if (!isDraggingCreate.current) {
        // A plain click (no drag) opens quick-create at the slot that was
        // clicked. This used to just bail, so clicking an empty slot in Week or
        // Day did nothing at all — only drag-to-create and the sidebar worked.
        setDragCreate(null);
        dragCreateRef.current = null;
        if (created && onDateClick) {
          const at = new Date(created.day);
          at.setHours(Math.floor(created.startMinutes / 60),
                      created.startMinutes % 60, 0, 0);
          onDateClick(at);
        }
        return;
      }

      // Build new event from drag selection and open full modal
      if (created) {
        const startDate = new Date(created.day);
        startDate.setHours(Math.floor(created.startMinutes / 60), created.startMinutes % 60, 0, 0);
        onDateClick(startDate);
      }
      setDragCreate(null);
      dragCreateRef.current = null;
      isDraggingCreate.current = false;
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Day headers */}
      <div className="flex flex-shrink-0" style={{ borderBottom: '1px solid #DADCE0', marginLeft: labelWidth }}>
        {days.map(day => {
          const isToday = isSameDay(day, gymNow());
          return (
            <div
              key={day.toString()}
              className="flex-1 text-center py-2"
              style={{ borderLeft: '1px solid #DADCE0' }}
            >
              <div style={{ fontSize: '11px', fontWeight: 500, color: isToday ? '#1A73E8' : '#70757A', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {format(day, isDayView ? 'EEEE' : 'EEE')}
              </div>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  margin: '2px auto 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '50%',
                  fontSize: '22px',
                  fontWeight: 400,
                  color: isToday ? '#fff' : '#3C4043',
                  backgroundColor: isToday ? '#1A73E8' : 'transparent',
                  cursor: 'pointer',
                }}
                onClick={() => onDateClick(day)}
                onMouseEnter={e => { if (!isToday) e.currentTarget.style.backgroundColor = '#F1F3F4'; }}
                onMouseLeave={e => { if (!isToday) e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                {format(day, 'd')}
              </div>
            </div>
          );
        })}
      </div>

      {/* All-day events section */}
      {allDayEvents.length > 0 && (
        <div className="flex flex-shrink-0" style={{ borderBottom: '1px solid #DADCE0', minHeight: '28px' }}>
          <div style={{ width: labelWidth, flexShrink: 0, borderRight: '1px solid #DADCE0', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: '6px' }}>
            <span style={{ fontSize: '10px', color: '#70757A' }}>all-day</span>
          </div>
          {days.map(day => {
            const dayAllDay = allDayEvents.filter(e => {
              const start = new Date(e.start);
              const end = new Date(e.end);
              return isSameDay(day, start) ||
                (day >= startOfDay(start) && day < startOfDay(end));
            });
            return (
              <div
                key={day.toString()}
                className="flex-1 relative"
                style={{ borderLeft: '1px solid #DADCE0', padding: '2px', minHeight: '28px' }}
              >
                {dayAllDay.map(event => {
                  const color = getEventColor(event);
                  const cancelled = (event.status || '').toLowerCase() === 'cancelled';
                  return (
                    <div
                      key={event.id}
                      data-event-chip
                      data-event-status={event.status || 'confirmed'}
                      role="button"
                      tabIndex={0}
                      aria-label={`Open event: ${(event && event.title) || '(No title)'}`}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}
                      onClick={(e) => {
                        e.stopPropagation();
                        const targetEvent = event.originalEventId
                          ? state.events.find(ev => ev.id === event.originalEventId)
                          : event;
                        onEventClick(targetEvent, e);
                      }}
                      style={{
                        height: '20px',
                        borderRadius: '2px',
                        padding: '0 6px',
                        marginBottom: '2px',
                        backgroundColor: cancelled ? '#9AA0A6' : color,
                        color: 'white',
                        fontSize: '11px',
                        fontWeight: 500,
                        display: 'flex',
                        alignItems: 'center',
                        cursor: 'pointer',
                        overflow: 'hidden',
                        whiteSpace: 'nowrap',
                        textOverflow: 'ellipsis',
                        textDecoration: cancelled ? 'line-through' : 'none',
                        opacity: cancelled ? 0.75 : 1,
                      }}
                      onMouseEnter={e => e.currentTarget.style.filter = 'brightness(0.92)'}
                      onMouseLeave={e => e.currentTarget.style.filter = 'none'}
                    >
                      {cancelled ? `Cancelled · ${event.title}` : event.title}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Time grid */}
      <div className="flex-1 overflow-y-auto relative" ref={scrollRef}>
        <div className="flex relative" style={{ minHeight: `${24 * HOUR_HEIGHT}px` }}>
          {/* Time labels */}
          <div
            className="flex-shrink-0 sticky left-0 z-10 bg-white"
            style={{ width: labelWidth, borderRight: '1px solid #DADCE0' }}
          >
            {timeSlots.map(hour => (
              <div
                key={hour}
                style={{ height: `${HOUR_HEIGHT}px`, display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end', paddingRight: '6px', paddingTop: '2px' }}
              >
                {hour !== 0 && (
                  <span style={{ fontSize: '10px', color: '#70757A', marginTop: '-6px' }}>
                    {formatHour(hour, timeFormat)}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Day columns */}
          <div className="flex-1 flex relative">
            {/* Horizontal grid lines */}
            <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 0 }}>
              {timeSlots.map(hour => (
                <React.Fragment key={hour}>
                  <div style={{ height: `${HOUR_HEIGHT}px`, borderBottom: '1px solid #DADCE0', width: '100%' }} />
                </React.Fragment>
              ))}
            </div>

            {/* 30-min dashed lines */}
            <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 0 }}>
              {timeSlots.map(hour => (
                <div
                  key={hour}
                  style={{
                    position: 'absolute',
                    top: `${hour * HOUR_HEIGHT + HOUR_HEIGHT / 2}px`,
                    left: 0,
                    right: 0,
                    borderTop: '1px dashed #E8EAED',
                  }}
                />
              ))}
            </div>

            {days.map((day, dayIndex) => {
              const dayStart = startOfDay(day);
              const isToday = isSameDay(day, gymNow());
              // An event running past midnight belongs to both columns. Matching
              // on the start day alone made the tail (e.g. 11:30 PM–12:30 AM)
              // vanish from the day it actually ends on, so overlap is clipped
              // per column instead.
              const dayEndExclusive = addDays(dayStart, 1);
              const dayTimedEvents = timedEvents.flatMap(e => {
                if (!overlapsDay(e, dayStart)) return [];
                const s = new Date(e.start);
                const en = new Date(e.end);
                if (s >= dayStart && en <= dayEndExclusive) return [e];
                return [{
                  ...e,
                  start: (s < dayStart ? dayStart : s).toISOString(),
                  end: (en > dayEndExclusive ? dayEndExclusive : en).toISOString(),
                  // Keep a handle on the real event so clicking a clipped
                  // segment edits the whole event, not just the visible slice.
                  clippedFrom: e,
                }];
              });
              const layoutItems = computeEventLayout(dayTimedEvents);

              // H-06: Check if there's an active drag-create preview for this day column
              const showDragPreview = dragCreate && isSameDay(dragCreate.day, day);
              const dragPreviewTop = showDragPreview ? `${(dragCreate.startMinutes / 60) * HOUR_HEIGHT}px` : '0';
              const dragPreviewHeight = showDragPreview ? `${((dragCreate.endMinutes - dragCreate.startMinutes) / 60) * HOUR_HEIGHT}px` : '0';

              return (
                <div
                  key={day.toString()}
                  data-day-col
                  className="flex-1 relative"
                  style={{ borderLeft: '1px solid #DADCE0', userSelect: 'none' }}
                  onMouseDown={(e) => handleGridMouseDown(e, day, dayIndex)}
                >
                  {/* Click/drop zones */}
                  {timeSlots.map(hour => (
                    <div
                      key={hour}
                      style={{
                        position: 'absolute',
                        top: `${hour * HOUR_HEIGHT}px`,
                        left: 0,
                        right: 0,
                        height: `${HOUR_HEIGHT}px`,
                        zIndex: 1,
                      }}
                      onDragOver={handleDragOver}
                      onDrop={(e) => handleDrop(e, day, hour)}
                      onMouseEnter={e => { if (!dragCreate) e.currentTarget.style.backgroundColor = 'rgba(26,115,232,0.04)'; }}
                      onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                    />
                  ))}

                  {/* H-06: Drag-to-create preview overlay */}
                  {showDragPreview && (
                    <div
                      style={{
                        position: 'absolute',
                        top: dragPreviewTop,
                        left: '2px',
                        right: '2px',
                        height: dragPreviewHeight,
                        zIndex: 10,
                        backgroundColor: 'rgba(26,115,232,0.25)',
                        border: '2px solid #1A73E8',
                        borderRadius: '4px',
                        pointerEvents: 'none',
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '3px 6px',
                        overflow: 'hidden',
                      }}
                    >
                      <span style={{ fontSize: '11px', fontWeight: 600, color: '#1A73E8', whiteSpace: 'nowrap' }}>
                        {(() => {
                          const sh = Math.floor(dragCreate.startMinutes / 60);
                          const sm = dragCreate.startMinutes % 60;
                          const eh = Math.floor(dragCreate.endMinutes / 60);
                          const em = dragCreate.endMinutes % 60;
                          const fmt = (h, m) => timeFormat === '24h'
                            ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
                            : `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
                          return `${fmt(sh, sm)} – ${fmt(eh, em)}`;
                        })()}
                      </span>
                    </div>
                  )}

                  {/* Current time red line */}
                  {isToday && (
                    <div
                      style={{
                        position: 'absolute',
                        top: `${currentTimeTop}px`,
                        left: 0,
                        right: 0,
                        zIndex: 5,
                        display: 'flex',
                        alignItems: 'center',
                        pointerEvents: 'none',
                      }}
                    >
                      <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#EA4335', flexShrink: 0, marginLeft: '-5px' }} />
                      <div style={{ flex: 1, height: '2px', backgroundColor: '#EA4335' }} />
                    </div>
                  )}

                  {/* Event blocks */}
                  {layoutItems.map(({ event, col, totalCols }) => {
                    const color = getEventColor(event);
                    const style = getEventStyle(event, dayStart);
                    const width = `calc(${100 / totalCols}% - 4px)`;
                    const left = `calc(${(col / totalCols) * 100}% + 2px)`;
                    const isOriginalId = !event.id.includes('_recur_') && !event.clippedFrom;
                    const cancelled = (event.status || '').toLowerCase() === 'cancelled';
                    const chipColor = cancelled ? '#9AA0A6' : color;

                    return (
                      <div
                        key={event.id}
                        data-event-chip
                        data-event-status={event.status || 'confirmed'}
                        data-test-id={cancelled ? `event-chip-cancelled-${event.id}` : `event-chip-${event.id}`}
                        role="button"
                        tabIndex={0}
                        aria-label={`Open event: ${event.title || '(No title)'}`}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}
                        draggable={isOriginalId && !cancelled}
                        onDragStart={(e) => {
                          e.stopPropagation();
                          isOriginalId && !cancelled && handleDragStart(e, event.id);
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          const source = event.clippedFrom || event;
                          const targetEvent = source.originalEventId
                            ? state.events.find(ev => ev.id === source.originalEventId)
                            : source;
                          onEventClick(targetEvent, e);
                        }}
                        style={{
                          position: 'absolute',
                          top: style.top,
                          height: style.height,
                          width,
                          left,
                          zIndex: 3,
                          backgroundColor: chipColor,
                          borderRadius: '4px',
                          padding: '3px 6px',
                          overflow: 'hidden',
                          cursor: 'pointer',
                          borderLeft: `3px solid ${darkenColor(chipColor, 20)}`,
                          opacity: cancelled ? 0.7 : 0.9,
                          textDecoration: cancelled ? 'line-through' : 'none',
                        }}
                        onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                        onMouseLeave={e => e.currentTarget.style.opacity = cancelled ? '0.7' : '0.9'}
                      >
                        <div style={{ fontSize: '11px', fontWeight: 600, color: 'white', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textDecoration: cancelled ? 'line-through' : 'none' }}>
                          {cancelled ? `Cancelled · ${event.title || '(No title)'}` : (event.title || '(No title)')}
                        </div>
                        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.85)', lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {formatTime(event.start, timeFormat)} – {formatTime(event.end, timeFormat)}
                        </div>
                        {event.location && parseFloat(style.height) > 50 && (
                          <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.75)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {event.location}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Darken a hex color by a percentage
function darkenColor(hex, percent) {
  if (!hex || !hex.startsWith('#')) return hex;
  let r = parseInt(hex.slice(1, 3), 16);
  let g = parseInt(hex.slice(3, 5), 16);
  let b = parseInt(hex.slice(5, 7), 16);
  r = Math.max(0, Math.floor(r * (1 - percent / 100)));
  g = Math.max(0, Math.floor(g * (1 - percent / 100)));
  b = Math.max(0, Math.floor(b * (1 - percent / 100)));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}
