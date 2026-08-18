import React, { useState } from 'react';
import { useStore } from '../context/StoreContext';
import { Plus, Eye, EyeOff, Trash2 } from 'lucide-react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, startOfWeek, endOfWeek } from 'date-fns';
import clsx from 'clsx';
import AddCalendarModal from './AddCalendarModal';
import { gymNow } from '../utils/helpers';

// Named Tailwind color -> hex so a swatch renders whether a calendar carries a
// hex ("#039BE5") or a class ("bg-green-500").
const NAMED_COLORS = {
  'bg-blue-500': '#039BE5',
  'bg-green-500': '#33B679',
  'bg-purple-500': '#8E24AA',
  'bg-yellow-500': '#F6BF26',
  'bg-red-500': '#E67C73',
  'bg-indigo-500': '#3F51B5',
};
const swatchColor = (c) => !c ? '#039BE5' : c.startsWith('#') ? c : (NAMED_COLORS[c] || '#039BE5');

const MINI_WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

export default function Sidebar({ onCreateEvent }) {
  const { state, dispatch } = useStore();
  const [calendarToDelete, setCalendarToDelete] = useState(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addModalMode, setAddModalMode] = useState('my');
  const openAddModal = (mode) => { setAddModalMode(mode); setAddModalOpen(true); };
  React.useEffect(() => {
    if (!calendarToDelete) return;
    const handleEscape = (e) => {
      if (e.key === 'Escape') setCalendarToDelete(null);
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [calendarToDelete]);

  // Mini Calendar Logic
  const weekStartsOn = Number(state.settings?.weekStart ?? 0);
  const miniDate = new Date(state.currentDate);
  const monthStart = startOfMonth(miniDate);
  const monthEnd = endOfMonth(miniDate);
  const startDate = startOfWeek(monthStart, { weekStartsOn });
  const endDate = endOfWeek(monthEnd, { weekStartsOn });

  const calendarDays = eachDayOfInterval({ start: startDate, end: endDate });
  const miniWeekdays = [...MINI_WEEKDAYS.slice(weekStartsOn), ...MINI_WEEKDAYS.slice(0, weekStartsOn)];

  return (
    <aside className={clsx(
      "w-64 flex-shrink-0 flex flex-col border-r border-google-border bg-white transition-all duration-300 overflow-y-auto",
      !state.sidebarOpen && "-ml-64"
    )}>
      <div className="p-4 flex-1">
        <button 
          onClick={onCreateEvent}
          className="flex items-center gap-3 px-4 py-3 bg-white border border-google-border shadow-sm hover:shadow-md rounded-full transition-all mb-6"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-500 via-yellow-500 to-green-500 flex items-center justify-center">
            <Plus className="text-white" size={20} />
          </div>
          <span className="font-medium text-text-primary">Create</span>
        </button>

        {/* Mini Calendar */}
        <div className="mb-6">
          <div className="flex justify-between mb-2 pl-2">
            <span className="text-sm font-medium text-text-primary">
              {format(miniDate, 'MMMM yyyy')}
            </span>
          </div>
          <div className="grid grid-cols-7 text-center text-xs mb-2 text-text-secondary">
            {miniWeekdays.map((d, i) => (
              <div key={`${d}-${i}`} className="h-6 flex items-center justify-center">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 text-center text-xs gap-y-1">
            {calendarDays.map((day, idx) => (
              <button
                key={idx}
                onClick={() => dispatch({ type: 'SET_DATE', payload: day.toISOString() })}
                className={clsx(
                  "h-7 w-7 rounded-full flex items-center justify-center mx-auto hover:bg-gray-100",
                  !isSameMonth(day, miniDate) && "text-gray-300",
                  isSameDay(day, gymNow()) && "bg-primary text-white hover:bg-primary-hover",
                  isSameDay(day, miniDate) && !isSameDay(day, gymNow()) && "bg-blue-100 text-primary"
                )}
              >
                {format(day, 'd')}
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-google-border pt-4">
          <div className="flex items-center justify-between mb-2 px-2">
            <h3 className="text-sm font-medium text-text-primary">My calendars</h3>
            <button
              onClick={() => openAddModal('my')}
              className="text-text-secondary hover:bg-gray-100 p-1 rounded"
              title="Create new calendar"
              aria-label="Create new calendar"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="space-y-1">
            {state.calendars.map(cal => (
              <div key={cal.id} className="group flex items-center justify-between px-2 py-1 hover:bg-gray-100 rounded cursor-pointer">
                <div 
                  className="flex items-center gap-3 flex-1"
                  onClick={() => dispatch({ type: 'TOGGLE_CALENDAR', payload: cal.id })}
                >
                  <div
                    className="w-4 h-4 rounded border flex items-center justify-center"
                    style={{
                      backgroundColor: cal.visible ? swatchColor(cal.color) : 'transparent',
                      borderColor: cal.visible ? swatchColor(cal.color) : '#70757A',
                    }}
                  >
                    {cal.visible && <div className="w-2 h-2 bg-white rounded-full opacity-0" />}
                    {cal.visible && <span className="text-white text-xs">✓</span>}
                  </div>
                  <span className="text-sm text-text-primary truncate">{cal.name}</span>
                </div>
                
                <div className="flex items-center gap-1">
                   <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      dispatch({ type: 'TOGGLE_CALENDAR', payload: cal.id });
                    }}
                    className="p-1 text-gray-400 hover:text-gray-600"
                    title={cal.visible ? "Hide from calendar" : "Show on calendar"}
                    aria-label={cal.visible ? "Hide calendar" : "Show calendar"}
                  >
                    {cal.visible ? <Eye size={16} /> : <EyeOff size={16} />}
                  </button>
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      setCalendarToDelete(cal);
                    }}
                    className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete calendar"
                    aria-label="Delete calendar"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Other calendars — subscribed / shared calendars, seeded separately
              from "My calendars". Each row has an eye toggle wired to
              TOGGLE_OTHER_CALENDAR. */}
          <div className="mt-4 border-t border-google-border pt-4">
            <div className="flex items-center justify-between mb-2 px-2">
              <h3 className="text-sm font-medium text-text-primary">Other calendars</h3>
              <button
                onClick={() => openAddModal('other')}
                className="text-text-secondary hover:bg-gray-100 p-1 rounded"
                title="Subscribe to calendar"
                aria-label="Subscribe to calendar"
              >
                <Plus size={16} />
              </button>
            </div>

            <div className="space-y-1">
              {(state.otherCalendars || []).map(cal => (
                <div key={cal.id} className="group flex items-center justify-between px-2 py-1 hover:bg-gray-100 rounded cursor-pointer">
                  <div
                    className="flex items-center gap-3 flex-1"
                    onClick={() => dispatch({ type: 'TOGGLE_OTHER_CALENDAR', payload: cal.id })}
                  >
                    <div
                      className="w-4 h-4 rounded border flex items-center justify-center"
                      style={{
                        backgroundColor: cal.visible ? swatchColor(cal.color) : 'transparent',
                        borderColor: cal.visible ? swatchColor(cal.color) : '#70757A',
                      }}
                    >
                      {cal.visible && <span className="text-white text-xs">✓</span>}
                    </div>
                    <span className="text-sm text-text-primary truncate">{cal.name}</span>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        dispatch({ type: 'TOGGLE_OTHER_CALENDAR', payload: cal.id });
                      }}
                      className="p-1 text-gray-400 hover:text-gray-600"
                      title={cal.visible ? "Hide from calendar" : "Show on calendar"}
                      aria-label={cal.visible ? "Hide calendar" : "Show calendar"}
                    >
                      {cal.visible ? <Eye size={16} /> : <EyeOff size={16} />}
                    </button>
                  </div>
                </div>
              ))}
              {(!state.otherCalendars || state.otherCalendars.length === 0) && (
                <p className="px-2 text-xs text-text-secondary">No other calendars.</p>
              )}
            </div>
          </div>

          {calendarToDelete && (
            <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40">
              <div className="w-full max-w-sm rounded-lg bg-white p-5 shadow-xl border border-gray-200">
                <h3 className="text-base font-medium text-gray-900 mb-2">Delete calendar?</h3>
                <p className="text-sm text-gray-600 mb-5">Events assigned to "{calendarToDelete.name}" remain in state but the calendar list entry is removed.</p>
                <div className="flex justify-end gap-2">
                  <button onClick={() => setCalendarToDelete(null)} className="px-4 py-2 text-sm rounded hover:bg-gray-100">Cancel</button>
                  <button
                    onClick={() => {
                      dispatch({ type: 'DELETE_CALENDAR', payload: calendarToDelete.id });
                      setCalendarToDelete(null);
                    }}
                    className="px-4 py-2 text-sm rounded bg-red-600 text-white hover:bg-red-700"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
          
          <div className="mt-4 px-2 text-xs text-text-secondary border-t border-google-border pt-2">
            <p className="flex items-center gap-1 mb-2">
              <span className="font-medium">Tip:</span> Drag and drop events to reschedule.
            </p>
          </div>
        </div>
      </div>

      <AddCalendarModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        mode={addModalMode}
      />
    </aside>
  );
}
