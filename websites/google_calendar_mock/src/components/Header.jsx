import React, { useState, useRef, useEffect } from 'react';
import { useStore } from '../context/StoreContext';
import { Menu, ChevronLeft, ChevronRight, Search, Settings, HelpCircle, User, ChevronDown, Plus, X, LogOut } from 'lucide-react';
import { format, addMonths, subMonths, addWeeks, subWeeks, addDays, subDays, addHours } from 'date-fns';
import { generateId, getSessionId, resetSession } from '../utils/helpers';
import SettingsModal from './SettingsModal';
import { gymNow } from '../utils/helpers';

export default function Header({ onSearch, searchQuery = '' }) {
  const { state, dispatch } = useStore();
  const [isViewMenuOpen, setIsViewMenuOpen] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [quickAddText, setQuickAddText] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const menuRef = useRef(null);
  const quickAddRef = useRef(null);
  const accountRef = useRef(null);
  const date = new Date(state.currentDate);

  const handleSignOut = () => {
    resetSession(getSessionId());
    window.location.href = window.location.pathname;
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsViewMenuOpen(false);
      }
      if (quickAddRef.current && !quickAddRef.current.contains(event.target)) {
        setQuickAddOpen(false);
      }
      if (accountRef.current && !accountRef.current.contains(event.target)) {
        setAccountOpen(false);
      }
      // Settings now opens a full-screen SettingsModal which manages its own
      // dismissal (overlay click / Cancel / Escape); no outside-click branch here
      // or every click inside the modal would immediately close it.
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsViewMenuOpen(false);
        setQuickAddOpen(false);
        setSettingsOpen(false);
        setAccountOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const handlePrev = () => {
    let newDate;
    if (state.view === 'month') newDate = subMonths(date, 1);
    else if (state.view === 'week') newDate = subWeeks(date, 1);
    else newDate = subDays(date, 1);
    dispatch({ type: 'SET_DATE', payload: newDate.toISOString() });
  };

  const handleNext = () => {
    let newDate;
    if (state.view === 'month') newDate = addMonths(date, 1);
    else if (state.view === 'week') newDate = addWeeks(date, 1);
    else newDate = addDays(date, 1);
    dispatch({ type: 'SET_DATE', payload: newDate.toISOString() });
  };

  const handleToday = () => {
    dispatch({ type: 'SET_DATE', payload: gymNow().toISOString() });
  };

  const handleViewChange = (view) => {
    dispatch({ type: 'SET_VIEW', payload: view });
    setIsViewMenuOpen(false);
  };

  const handleQuickAdd = (e) => {
    e.preventDefault();
    e.stopPropagation(); // Prevent bubbling
    
    if (!quickAddText.trim()) return;

    // Simple parser logic for demo
    let start = new Date(gymNow());
    let title = quickAddText;

    // Basic date parsing — always against the gym clock (no split with wall clock).
    if (quickAddText.toLowerCase().includes('tomorrow')) {
      start = new Date(gymNow());
      start.setDate(start.getDate() + 1);
      start.setHours(9, 0, 0, 0);
      title = title.replace(/\btomorrow\b/i, '').trim();
    } else if (quickAddText.toLowerCase().includes('next monday')) {
       // Simple logic for "next monday"
       const day = start.getDay();
       const diff = start.getDate() - day + (day === 0 ? -6 : 1) + 7; // Adjust for next Monday
       start.setDate(diff);
       start.setHours(9, 0, 0, 0); // Default to 9am
       title = title.replace(/\bnext monday\b/i, '').trim();
    }
    
    // Check for time (e.g., "2pm", "14:00", "3:30pm")
    const timeMatch = title.match(/(\d{1,2})(:(\d{2}))?\s*(am|pm)?/i);
    if (timeMatch) {
      let hours = parseInt(timeMatch[1]);
      const minutes = timeMatch[3] ? parseInt(timeMatch[3]) : 0;
      const meridiem = timeMatch[4]?.toLowerCase();

      if (meridiem === 'pm' && hours < 12) hours += 12;
      if (meridiem === 'am' && hours === 12) hours = 0;

      start.setHours(hours, minutes, 0, 0);
      
      // Remove the time string from title roughly
      title = title.replace(timeMatch[0], '').trim();
    } else {
      // Default to next hour if no time specified
      if (!quickAddText.toLowerCase().includes('tomorrow') && !quickAddText.toLowerCase().includes('next monday')) {
         start.setHours(start.getHours() + 1, 0, 0, 0);
      }
    }

    // Clean up title
    title = title.replace(/\bat\b/i, '').trim(); // Remove standalone "at"
    if (!title) title = "New Event";

    // "Default event duration" applies to Quick Add too — it was hardcoded to
    // one hour, so a 2-hour default still produced 1-hour events.
    const duration = state.settings?.defaultDuration || 60;
    const end = new Date(start.getTime() + duration * 60000);
    const reminder = state.settings?.defaultReminder;

    const newEvent = {
      id: generateId(),
      calendarId: state.calendars[0]?.id,
      title: title,
      start: start.toISOString(),
      end: end.toISOString(),
      allDay: false,
      location: '',
      description: `Created via Quick Add from: "${quickAddText}"`,
      guests: [],
      color: 'bg-blue-500',
      recurring: 'none',
      reminders: reminder ? [reminder] : []
    };

    dispatch({ type: 'ADD_EVENT', payload: newEvent });
    setQuickAddText('');
    setQuickAddOpen(false);
    
    // Jump to date if it's in the future so user sees it
    dispatch({ type: 'SET_DATE', payload: start.toISOString() });
  };

  const currentMonthTitle = format(date, 'MMMM yyyy');

  const viewLabels = {
    month: 'Month',
    week: 'Week',
    day: 'Day',
    agenda: 'Schedule'
  };

  return (
    <header className="h-16 border-b border-google-border flex items-center px-4 justify-between bg-white z-20 relative">
      <div className="flex items-center gap-2 min-w-[240px]">
        <button 
          onClick={() => dispatch({ type: 'TOGGLE_SIDEBAR' })}
          className="p-2 hover:bg-gray-100 rounded-full text-text-secondary"
        >
          <Menu size={24} />
        </button>
        <div className="flex items-center gap-1 text-text-secondary">
          <div className="w-8 h-8 bg-primary rounded text-white flex items-center justify-center font-bold text-lg">
            31
          </div>
          <span className="text-xl text-text-secondary hidden sm:block">GymCal</span>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-1">
        <button 
          onClick={handleToday}
          className="px-4 py-2 border border-google-border rounded hover:bg-gray-50 text-sm font-medium"
        >
          Today
        </button>
        <div className="flex items-center gap-1">
          <button onClick={handlePrev} className="p-1 hover:bg-gray-100 rounded-full">
            <ChevronLeft size={20} />
          </button>
          <button onClick={handleNext} className="p-1 hover:bg-gray-100 rounded-full">
            <ChevronRight size={20} />
          </button>
        </div>
        <h2 className="text-xl text-text-primary min-w-[150px]">{currentMonthTitle}</h2>
      </div>

      <div className="flex items-center gap-3">
        {/* Quick Add Toggle */}
        <div className="relative" ref={quickAddRef}>
          <button 
            onClick={() => setQuickAddOpen(!quickAddOpen)}
            className={`p-2 rounded-full transition-colors ${quickAddOpen ? 'bg-blue-100 text-primary' : 'hover:bg-gray-100 text-text-secondary'}`}
            title="Quick add event"
            aria-label="Quick add event"
          >
            <Plus size={24} />
          </button>
          
          {quickAddOpen && (
            <div className="absolute top-full right-0 mt-2 w-80 bg-white shadow-xl border border-gray-200 rounded-lg p-3 z-50 animate-in fade-in zoom-in duration-100 origin-top-right">
              <form onSubmit={handleQuickAdd}>
                <div className="mb-2">
                  <label htmlFor="quick-add-input" className="block text-xs font-medium text-gray-700 mb-1">
                    Quick Add Event
                  </label>
                  <input
                    id="quick-add-input"
                    autoFocus
                    type="text"
                    placeholder="e.g. Meeting tomorrow 2pm"
                    className="w-full border border-gray-300 rounded p-2 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none"
                    value={quickAddText}
                    onChange={e => setQuickAddText(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setQuickAddOpen(false)}
                    className="px-3 py-1.5 text-gray-600 text-sm hover:bg-gray-100 rounded"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    className="px-3 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-hover font-medium"
                  >
                    Add Event
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        <div className="relative hidden md:block">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={20} className="text-gray-400" />
          </div>
          <input
            type="text"
            placeholder="Search"
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            aria-label="Search events"
            className="pl-10 pr-9 py-2 bg-google-gray rounded-lg focus:outline-none focus:bg-white focus:shadow-md transition-all w-64"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearch('')}
              title="Clear search"
              aria-label="Clear search"
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-gray-800"
            >
              <X size={16} />
            </button>
          )}
        </div>
        
        {/* Custom View Dropdown */}
        <div className="relative" ref={menuRef}>
          <button 
            onClick={() => setIsViewMenuOpen(!isViewMenuOpen)}
            aria-label="Change calendar view"
            className="flex items-center gap-2 px-3 py-2 border border-google-border rounded hover:bg-gray-50 text-sm font-medium min-w-[100px] justify-between"
          >
            <span>{viewLabels[state.view]}</span>
            <ChevronDown size={16} className="text-gray-500" />
          </button>

          {isViewMenuOpen && (
            <div className="absolute top-full right-0 mt-1 w-48 bg-white border border-google-border rounded shadow-lg py-1 z-50">
              {Object.entries(viewLabels).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => handleViewChange(key)}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 text-text-primary flex items-center justify-between"
                >
                  {label}
                  {state.view === key && <span className="text-primary">✓</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 ml-2">
          <button
            onClick={() => setSettingsOpen(true)}
            className="p-2 hover:bg-gray-100 rounded-full text-text-secondary"
            title="Settings"
            aria-label="Settings"
          >
            <Settings size={20} />
          </button>
          <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

          <div className="relative" ref={accountRef}>
            <button
              onClick={() => setAccountOpen(o => !o)}
              title="Account"
              aria-label="Account"
              aria-haspopup="menu"
              aria-expanded={accountOpen}
              className="block rounded-full focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {state.user.avatar ? (
                <img
                  src={state.user.avatar}
                  alt="User"
                  className="w-8 h-8 rounded-full border border-google-border"
                />
              ) : (
                <div className="w-8 h-8 rounded-full border border-google-border bg-primary text-white flex items-center justify-center text-sm font-medium">
                  {(state.user.username || 'U').trim().charAt(0).toUpperCase()}
                </div>
              )}
            </button>

            {accountOpen && (
              <div role="menu" className="absolute top-full right-0 mt-2 w-64 bg-white border border-google-border rounded-lg shadow-xl py-2 z-50">
                <div className="px-4 py-2 border-b border-google-border">
                  <div className="text-sm font-medium text-text-primary">{state.user.username}</div>
                  <div className="text-xs text-text-secondary truncate">{state.user.email}</div>
                </div>
                <button
                  role="menuitem"
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-primary hover:bg-gray-100"
                >
                  <LogOut size={16} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
