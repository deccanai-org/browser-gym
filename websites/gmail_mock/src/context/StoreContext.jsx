import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { INITIAL_STATE, DEFAULT_SETTINGS, getSessionId, fetchCustomState, saveState, initializeData } from '../data/mockData';
import { generateId, formatDate } from '../lib/utils';
import { bridged, bridgeState, bridgeAct, bridgePoll } from '../lib/bridge';

const APP = 'mail'; // bridge engine app key for this mock
// In bridged mode: run the gym action, then adopt the engine's authoritative
// per-app state (already in this mock's shape). Merge so UI-only fields survive.
const applyEngine = (setState, r) => {
  // Normalize through initializeData (deep-merge onto defaults) so the adopted
  // state matches the seeded shape — same path normal seeding uses.
  if (r && r.apps && r.apps[APP]) setState(prev => ({ ...prev, ...initializeData(null, r.apps[APP]) }));
};

const StoreContext = createContext();

const INITIAL_KEY_PREFIX = 'xmail-clone-initialState';

export const useStore = () => {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error("useStore must be used within a StoreProvider");
  }
  return context;
};

export const StoreProvider = ({ children }) => {
  const [initialState, setInitialState] = useState(() => JSON.parse(JSON.stringify(INITIAL_STATE)));
  const [state, setState] = useState(() => INITIAL_STATE);
  const [loading, setLoading] = useState(true);
  // When a sid is in the URL but its seed state can't be loaded, fail loudly
  // instead of silently booting generic demo data (which a reviewer can't tell
  // apart from a real seeded session).
  const [loadError, setLoadError] = useState(null);
  const sidRef = useRef(getSessionId());
  const initDone = useRef(false);

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEmails, setSelectedEmails] = useState([]);
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState('primary');
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [currentDraftId, setCurrentDraftId] = useState(null);
  const [composePreFill, setComposePreFill] = useState(null);
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [focusedEmailIndex, setFocusedEmailIndex] = useState(-1);
  const [showShortcutsModal, setShowShortcutsModal] = useState(false);

  // Session-aware initialization
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    const sid = sidRef.current;

    // Bridged mode: the gym engine is the source of truth. Load its state and
    // poll so cross-app effects (e.g. an order confirmation email) surface here too.
    if (bridged()) {
      bridgeState(APP).then(s => {
        if (s) { const data = initializeData(sid, s); setState(data); setInitialState(JSON.parse(JSON.stringify(data))); }
        setLoading(false);
      });
// Poll = adopt the ENGINE's world, but keep the keys the engine does not own.
      // Re-adopting wholesale every 2.5s snapped the user's own view state back
      // (which month you were on, your filters, saved-for-later) mid-interaction.
      const stop = bridgePoll(APP, s => setState(prev => {
        if (!s) return prev;
        const { settings, labels, ...engineOwned } = initializeData(sid, s);
        // The mail engine carries no label DEFINITIONS and no draft authoring, so
        // adopting engineOwned wholesale wiped a just-created label and a draft
        // being composed every 2.5s. Keep both client-owned: per-email label
        // membership still round-trips via mail.toggle_label; drafts are ours
        // until sent. A discarded draft stays gone because it's dropped from prev.
        const keepLabels = prev?.labels ?? labels;
        const localDrafts = (prev?.emails || []).filter(e => e && e.folder === 'drafts');
        const engineEmails = engineOwned.emails || [];
        const engineIds = new Set(engineEmails.map(e => e && e.id));
        const emails = [...engineEmails, ...localDrafts.filter(d => !engineIds.has(d.id))];
        return { ...prev, ...engineOwned, emails, labels: keepLabels };
      }));
      return () => stop();
    }

    if (sid) {
      const sessionKey = `${INITIAL_KEY_PREFIX}_${sid}`;
      const isRefresh = localStorage.getItem(sessionKey) !== null;
      if (isRefresh) {
        const data = initializeData(sid);
        setState(data);
        const storedInitial = localStorage.getItem(sessionKey);
        setInitialState(storedInitial ? JSON.parse(storedInitial) : data);
        setLoading(false);
      } else {
        fetchCustomState(sid).then(customState => {
          // A sid was requested but the state server had no seed for it (or the
          // fetch failed). Surface it loudly rather than falling back to demo data.
          if (!customState) {
            setLoadError(sid);
            setLoading(false);
            return;
          }
          const data = initializeData(sid, customState);
          setState(data);
          setInitialState(JSON.parse(JSON.stringify(data)));
          setLoading(false);
        });
      }
    } else {
      fetchCustomState().then(customState => {
        if (customState) {
          const data = initializeData(null, customState);
          setState(data);
          setInitialState(JSON.parse(JSON.stringify(data)));
        } else {
          const data = initializeData();
          setState(data);
          setInitialState(JSON.parse(JSON.stringify(data)));
        }
        setLoading(false);
      });
    }
  }, []);

  // Save state on changes (session-aware)
  useEffect(() => {
    if (loading || bridged()) return;
    try {
      saveState(state, sidRef.current, initialState);
    } catch (e) {
      console.error("Failed to save state to local storage", e);
    }
  }, [state, loading]);

  // Every folder move, read flag and label change in this app funnels through
  // these two. Bridging HERE rather than at each of the ~12 call sites means a
  // spam/trash/archive move actually reaches the engine — before, it repainted
  // locally and the next poll silently put the mail back.
  //
  // The mailbox's own folder names don't all match the engine's: 'all-mail' is
  // what this UI calls archive.
  const FOLDER_TO_ENGINE = { 'all-mail': 'archive', archive: 'archive', trash: 'trash',
                             spam: 'spam', inbox: 'inbox' };

  const bridgeEmailUpdates = (emailIds, updates) => {
    const calls = [];
    for (const id of emailIds) {
      if (updates.folder !== undefined) {
        const folder = FOLDER_TO_ENGINE[updates.folder] || updates.folder;
        calls.push(bridgeAct('mail.set_folder', { email_id: id, folder }));
      }
      // read:true is "the agent opened it" — the signal several tasks gate on.
      if (updates.read === true) calls.push(bridgeAct('mail.open', { email_id: id }));
      if (updates.starred !== undefined)
        calls.push(bridgeAct('mail.toggle_label', { email_id: id, label: 'starred' }));
      if (updates.important !== undefined)
        calls.push(bridgeAct('mail.toggle_label', { email_id: id, label: 'important' }));
      if (Array.isArray(updates.labels))
        calls.push(bridgeAct('mail.toggle_label', { email_id: id, label: updates.labels.at(-1) }));
    }
    if (!calls.length) return false;
    Promise.all(calls).then(rs => applyEngine(setState, rs[rs.length - 1]));
    return true;
  };

  // read:false has no engine counterpart — the engine only records that a mail
  // was OPENED (read:true via mail.open), never "un-read". A bridged mark-as-unread
  // would fall through to a local-only setState that the 2.5s poll instantly
  // reverts (snapping the row back), i.e. a control that fakes a success. Treat a
  // pure mark-as-unread as not-available in bridged mode instead.
  const isMarkUnreadOnly = (updates) => {
    if (updates.read !== false) return false;
    const engineKeys = ['folder', 'starred', 'important', 'labels'];
    return !engineKeys.some(k => updates[k] !== undefined);
  };

  const updateEmail = (emailId, updates) => {
    if (bridged() && isMarkUnreadOnly(updates)) {
      showToast("Marking as unread isn't available in this workspace");
      return;
    }
    if (bridged() && bridgeEmailUpdates([emailId], updates)) return;
    setState(prev => ({
      ...prev,
      emails: prev.emails.map(email =>
        email.id === emailId ? { ...email, ...updates } : email
      )
    }));
  };

  const bulkUpdateEmails = (emailIds, updates) => {
    if (bridged() && isMarkUnreadOnly(updates)) {
      showToast("Marking as unread isn't available in this workspace");
      setSelectedEmails([]);
      return;
    }
    if (bridged() && bridgeEmailUpdates(emailIds, updates)) { setSelectedEmails([]); return; }
    setState(prev => ({
      ...prev,
      emails: prev.emails.map(email =>
        emailIds.includes(email.id) ? { ...email, ...updates } : email
      )
    }));
    setSelectedEmails([]);
  };

  const deleteEmails = (emailIds) => {
    if (bridged()) {
      Promise.all((emailIds || []).map(id =>
        bridgeAct('mail.set_folder', { email_id: id, folder: 'trash' })))
        .then(rs => applyEngine(setState, rs[rs.length - 1]));
      showToast('Conversation moved to Trash');
      return;
    }
    setState(prev => {
      const emailsToUpdate = prev.emails.filter(e => emailIds.includes(e.id));
      const trashIds = emailsToUpdate.filter(e => e.folder === 'trash').map(e => e.id);
      const nonTrashIds = emailsToUpdate.filter(e => e.folder !== 'trash').map(e => e.id);
      const snapshot = prev.emails;

      let newEmails = prev.emails;

      if (trashIds.length > 0) {
        newEmails = newEmails.filter(e => !trashIds.includes(e.id));
      }

      if (nonTrashIds.length > 0) {
        newEmails = newEmails.map(e =>
          nonTrashIds.includes(e.id) ? { ...e, folder: 'trash' } : e
        );
      }

      showToast(
        trashIds.length > 0 ? 'Conversation deleted forever' : 'Conversation moved to Trash',
        () => setState(s => ({ ...s, emails: snapshot }))
      );

      return { ...prev, emails: newEmails };
    });
    setSelectedEmails([]);
  };

  const archiveEmails = (emailIds) => {
    if (bridged()) {
      Promise.all((emailIds || []).map(id =>
        bridgeAct('mail.set_folder', { email_id: id, folder: 'archive' })))
        .then(rs => applyEngine(setState, rs[rs.length - 1]));
      showToast('Conversation archived');
      return;
    }
    setState(prev => {
      const snapshot = prev.emails;
      showToast('Conversation archived', () => setState(s => ({ ...s, emails: snapshot })));
      return {
        ...prev,
        emails: prev.emails.map(e => emailIds.includes(e.id) ? { ...e, folder: 'all-mail' } : e)
      };
    });
    setSelectedEmails([]);
  }

  const parseRecipients = (str) => {
    if (!str) return [];
    return str.split(',').map(e => {
      const trimmed = e.trim();
      return trimmed ? { name: trimmed, email: trimmed } : null;
    }).filter(Boolean);
  };

  const sendEmail = (emailData) => {
    if (bridged()) {
      // Cc/Bcc render in the composer and were being dropped on the floor, so
      // "copy Dana" was unsatisfiable.
      const flat = (v) => (Array.isArray(v) ? v.join(',') : (v || ''));
      bridgeAct('mail.send', {
        to: flat(emailData.to),
        cc: flat(emailData.cc),
        bcc: flat(emailData.bcc),
        subject: emailData.subject || '',
        body: emailData.body || emailData.text || '',
      }).then(r => {
        applyEngine(setState, r);
        // The 2s compose autosave left a local Drafts copy; drop it after send or
        // the poll's local-draft preserve resurrects a ghost draft of the sent mail.
        if (currentDraftId) {
          setState(prev => ({ ...prev, emails: prev.emails.filter(e => e.id !== currentDraftId) }));
          setCurrentDraftId(null);
        }
      });
      return;
    }
    const newEmail = {
      id: generateId(),
      threadId: generateId(),
      from: { name: state.user.username, email: state.user.email, avatar: state.user.avatar },
      to: parseRecipients(emailData.to),
      cc: parseRecipients(emailData.cc),
      bcc: parseRecipients(emailData.bcc),
      subject: emailData.subject,
      body: emailData.body,
      snippet: emailData.body.replace(/<[^>]*>?/gm, '').substring(0, 100),
      timestamp: new Date().toISOString(),
      read: true,
      starred: false,
      important: false,
      labels: [],
      category: 'primary',
      folder: 'sent',
      attachments: emailData.attachments || []
    };

    setState(prev => ({
      ...prev,
      emails: [
        newEmail,
        ...prev.emails.filter(email => email.id !== currentDraftId)
      ]
    }));

    if (currentDraftId) {
      setCurrentDraftId(null);
    }
  };

  const saveDraft = (draftData) => {
      // If no content, don't save
      if (!draftData.to && !draftData.subject && !draftData.body) return;

      if (currentDraftId) {
          // Update existing draft
          setState(prev => ({
              ...prev,
              emails: prev.emails.map(e => e.id === currentDraftId ? {
                  ...e,
                  to: parseRecipients(draftData.to),
                  cc: parseRecipients(draftData.cc),
                  bcc: parseRecipients(draftData.bcc),
                  subject: draftData.subject || '(no subject)',
                  body: draftData.body,
                  snippet: draftData.body.replace(/<[^>]*>?/gm, '').substring(0, 100),
                  attachments: draftData.attachments || [],
                  timestamp: new Date().toISOString()
              } : e)
          }));
      } else {
          // Create new draft
          const newDraftId = generateId();
          const newDraft = {
              id: newDraftId,
              threadId: generateId(),
              from: { name: state.user.username, email: state.user.email, avatar: state.user.avatar },
              to: parseRecipients(draftData.to),
              cc: parseRecipients(draftData.cc),
              bcc: parseRecipients(draftData.bcc),
              subject: draftData.subject || '(no subject)',
              body: draftData.body,
              snippet: draftData.body.replace(/<[^>]*>?/gm, '').substring(0, 100),
              timestamp: new Date().toISOString(),
              read: true,
              starred: false,
              important: false,
              labels: [],
              category: 'primary',
              folder: 'drafts',
              attachments: draftData.attachments || []
          };

          setState(prev => ({
              ...prev,
              emails: [newDraft, ...prev.emails]
          }));
          setCurrentDraftId(newDraftId);
      }
  }

  const deleteDraft = (id) => {
      setState(prev => ({
          ...prev,
          emails: prev.emails.filter(e => e.id !== id)
      }));
  }

  const replyToEmail = (originalEmail, body, isReplyAll = false, attachments = []) => {
    if (bridged()) {
      // Reply-all has to carry the other recipients, or it is just a reply.
      const addrs = (list) => (list || []).map(r => r.email || r).filter(Boolean).join(',');
      bridgeAct('mail.send', {
        to: originalEmail.from?.email || originalEmail.from || originalEmail.fromEmail || '',
        cc: isReplyAll ? [addrs(originalEmail.to), addrs(originalEmail.cc)].filter(Boolean).join(',') : '',
        subject: 'Re: ' + (originalEmail.subject || ''),
        body: body || '',
      }).then(r => applyEngine(setState, r));
      return;
    }
     const newEmail = {
      id: generateId(),
      threadId: originalEmail.threadId,
      from: { name: state.user.username, email: state.user.email, avatar: state.user.avatar },
      to: [originalEmail.from, ...(isReplyAll ? originalEmail.to : [])].filter(r => r.email !== state.user.email),
      cc: isReplyAll ? originalEmail.cc : [],
      bcc: [],
      subject: originalEmail.subject.startsWith('Re:') ? originalEmail.subject : `Re: ${originalEmail.subject}`,
      body: body,
      snippet: body.replace(/<[^>]*>?/gm, '').substring(0, 100),
      timestamp: new Date().toISOString(),
      read: true,
      starred: false,
      important: false,
      labels: [],
      category: 'primary',
      folder: 'sent',
      attachments: attachments
    };

    setState(prev => ({
        ...prev,
        emails: [...prev.emails, newEmail]
    }));
  }

  // Starred/Important are labels on the engine side — the same labels the seed
  // projection reads back to set these flags — so a toggle round-trips instead
  // of living only in this tab.
  const toggleStar = (emailId) => {
    const email = state.emails.find(e => e.id === emailId);
    updateEmail(emailId, { starred: !(email && email.starred) });
  };

  const toggleImportant = (emailId) => {
    const email = state.emails.find(e => e.id === emailId);
    updateEmail(emailId, { important: !(email && email.important) });
  };

  const toggleRead = (emailId, status) => {
      updateEmail(emailId, { read: status });
  }

  // Opening a thread reads its emails. In bridged mode, log the open to the gym
  // engine (mail.open marks the email read server-side — some tasks require the
  // agent to actually OPEN a confirmation email) and adopt the authoritative
  // state. Legacy behavior is unchanged: mark unread thread emails read locally.
  const openThread = (threadId) => {
    const threadEmails = state.emails.filter(e => e.threadId === threadId);
    if (bridged()) {
      threadEmails.forEach(e => {
        bridgeAct('mail.open', { email_id: e.id }).then(r => applyEngine(setState, r));
      });
      return;
    }
    const unreadIds = threadEmails.filter(e => !e.read).map(e => e.id);
    if (unreadIds.length > 0) {
      bulkUpdateEmails(unreadIds, { read: true });
    }
  };

  const addLabel = (emailId, labelId) => {
    const email = state.emails.find(e => e.id === emailId);
    if (email && !email.labels.includes(labelId)) {
      updateEmail(emailId, { labels: [...email.labels, labelId] });
    }
  };

  const removeLabel = (emailId, labelId) => {
      const email = state.emails.find(e => e.id === emailId);
      if(email) {
          updateEmail(emailId, { labels: email.labels.filter(l => l !== labelId) });
      }
  }

  const createLabel = (name, color) => {
      const newLabel = { id: generateId(), name, color };
      setState(prev => ({
          ...prev,
          labels: [...prev.labels, newLabel]
      }));
  }

  const updateLabel = (labelId, updates) => {
      setState(prev => ({
          ...prev,
          labels: prev.labels.map(l => l.id === labelId ? { ...l, ...updates } : l)
      }));
  };

  const deleteLabel = (labelId) => {
      setState(prev => ({
          ...prev,
          labels: prev.labels.filter(l => l.id !== labelId),
          // Remove the label from all emails
          emails: prev.emails.map(e => ({
              ...e,
              labels: e.labels.filter(lid => lid !== labelId)
          }))
      }));
  };

  const updateSettings = (newSettings) => {
      setState(prev => ({
          ...prev,
          settings: { ...(prev.settings || DEFAULT_SETTINGS), ...newSettings }
      }));
  };

  const showToast = useCallback((message, undoAction) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message, undoAction });
    toastTimerRef.current = setTimeout(() => setToast(null), 5000);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(null);
  }, []);

  const forwardEmail = (originalEmail) => {
    const cleanBody = originalEmail.body.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '');
    const fwdBody = `---------- Forwarded message ---------\nFrom: ${originalEmail.from.name} <${originalEmail.from.email}>\nDate: ${formatDate(originalEmail.timestamp)}\nSubject: ${originalEmail.subject}\nTo: ${originalEmail.to.map(t => t.email).join(', ')}\n\n${cleanBody}`;
    setComposePreFill({
      to: '',
      cc: '',
      bcc: '',
      subject: `Fwd: ${originalEmail.subject}`,
      body: fwdBody,
      attachments: originalEmail.attachments || []
    });
    setCurrentDraftId(null);
    setIsComposeOpen(true);
  };

  const openDraft = (emailId) => {
    const draft = state.emails.find(e => e.id === emailId);
    if (!draft) return;
    setComposePreFill({
      to: draft.to.map(t => t.email || t.name).join(', '),
      cc: (draft.cc || []).map(t => t.email || t.name).join(', '),
      bcc: (draft.bcc || []).map(t => t.email || t.name).join(', '),
      subject: draft.subject,
      body: draft.body,
      attachments: draft.attachments || []
    });
    setCurrentDraftId(emailId);
    setIsComposeOpen(true);
  };

  const snoozeEmail = (emailId, snoozedUntil) => {
    // No engine snooze action exists; a local move would be undone by the next
    // poll, faking success — so in bridged mode this is honestly not-available.
    if (bridged()) {
      showToast("Snooze isn't available in this workspace");
      return;
    }
    setState(prev => {
      const snapshot = prev.emails;
      showToast('Conversation snoozed', () => setState(s => ({ ...s, emails: snapshot })));
      return {
        ...prev,
        emails: prev.emails.map(e =>
          e.id === emailId ? { ...e, folder: 'snoozed', snoozedUntil } : e
        )
      };
    });
  };

  // Check for unsnoozed emails on mount and periodically
  useEffect(() => {
    if (loading) return;
    // In bridged mode the engine owns folders and snooze is disabled; every
    // seeded snoozedUntil is in the past vs the real clock, so this would yank
    // all 21 snoozed emails into the inbox each tick. Leave them to the engine.
    if (bridged()) return;
    const checkSnoozed = () => {
      const now = new Date();
      setState(prev => {
        const hasExpired = prev.emails.some(e => e.folder === 'snoozed' && e.snoozedUntil && new Date(e.snoozedUntil) <= now);
        if (!hasExpired) return prev;
        return {
          ...prev,
          emails: prev.emails.map(e =>
            e.folder === 'snoozed' && e.snoozedUntil && new Date(e.snoozedUntil) <= now
              ? { ...e, folder: 'inbox', snoozedUntil: null }
              : e
          )
        };
      });
    };
    checkSnoozed();
    const interval = setInterval(checkSnoozed, 60000);
    return () => clearInterval(interval);
  }, [loading]);

  const emptyTrash = () => {
    // The engine has no destructive endpoint (set_folder only MOVES mail, nothing
    // is destroyed) and permanent deletion is a prohibited action anyway. A local
    // filter would just be undone by the next poll, faking a success — so in
    // bridged mode this is honestly not-available.
    if (bridged()) {
      showToast("Emptying Trash isn't available in this workspace");
      return;
    }
    setState(prev => ({
      ...prev,
      emails: prev.emails.filter(e => e.folder !== 'trash')
    }));
  };

  if (loadError) {
    return (
      <div style={{
        position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', textAlign: 'center',
        padding: '2rem', background: '#fff', color: '#202124',
        fontFamily: 'Roboto, Arial, sans-serif', zIndex: 9999,
      }}>
        <div style={{ fontSize: 48, lineHeight: 1, marginBottom: 16 }}>⚠️</div>
        <h1 style={{ fontSize: 22, fontWeight: 500, margin: '0 0 8px' }}>
          Could not load session
        </h1>
        <p style={{ fontSize: 15, color: '#5f6368', maxWidth: 520, margin: 0 }}>
          Could not load session <code style={{ fontFamily: 'monospace', color: '#d93025' }}>{loadError}</code> from the state server.
        </p>
        <p style={{ fontSize: 13, color: '#80868b', maxWidth: 520, marginTop: 12 }}>
          The seed state for this session was not found. This session was not started with generic demo data.
        </p>
      </div>
    );
  }

  return (
    <StoreContext.Provider value={{
      state,
      initialState,
      searchQuery,
      setSearchQuery,
      selectedEmails,
      setSelectedEmails,
      isComposeOpen,
      setIsComposeOpen,
      activeCategory,
      setActiveCategory,
      isSearchModalOpen,
      setIsSearchModalOpen,
      currentDraftId,
      setCurrentDraftId,
      updateEmail,
      bulkUpdateEmails,
      deleteEmails,
      archiveEmails,
      sendEmail,
      saveDraft,
      deleteDraft,
      replyToEmail,
      toggleStar,
      toggleImportant,
      toggleRead,
      openThread,
      addLabel,
      removeLabel,
      createLabel,
      updateLabel,
      deleteLabel,
      updateSettings,
      settings: state.settings || DEFAULT_SETTINGS,
      emptyTrash,
      forwardEmail,
      openDraft,
      snoozeEmail,
      composePreFill,
      setComposePreFill,
      toast,
      showToast,
      dismissToast,
      sidebarCollapsed,
      setSidebarCollapsed,
      focusedEmailIndex,
      setFocusedEmailIndex,
      showShortcutsModal,
      setShowShortcutsModal
    }}>
      {children}
    </StoreContext.Provider>
  );
};
