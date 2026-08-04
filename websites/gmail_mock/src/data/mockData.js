import SEED_DEFAULT from './seedDefault.json';
// Xmail Mock - Initial State Data
// Uses fixed IDs for reproducible testing

// --- Session-aware storage functions ---
const BASE_STORAGE_KEY = 'xmail-clone-state';
const BASE_INITIAL_KEY = 'xmail-clone-initialState';

function storageKey(sid) {
  return sid ? `${BASE_STORAGE_KEY}_${sid}` : BASE_STORAGE_KEY;
}
function initialKeyFn(sid) {
  return sid ? `${BASE_INITIAL_KEY}_${sid}` : BASE_INITIAL_KEY;
}

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
  } catch (e) { console.log('No custom state'); }
  return null;
};

let _syncTimer = null;

export const saveState = (state, sid = null, initialState = null) => {
  localStorage.setItem(storageKey(sid), JSON.stringify(state));
  clearTimeout(_syncTimer);
  _syncTimer = setTimeout(() => {
    const url = sid ? `/post?sid=${encodeURIComponent(sid)}` : '/post';
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'set_current', state, initial_state: initialState }),
    }).catch(() => {});
  }, 300);
};

export const getInitialStateBySid = (sid = null) => {
  const s = localStorage.getItem(initialKeyFn(sid));
  return s ? JSON.parse(s) : null;
};

export const initializeData = (sid = null, customState = null) => {
  const sk = storageKey(sid);
  const ik = initialKeyFn(sid);
  if (customState) {
    const data = { ...createDefaultData(), ...customState };
    localStorage.setItem(sk, JSON.stringify(data));
    localStorage.setItem(ik, JSON.stringify(data));
    return data;
  }
  const stored = localStorage.getItem(sk);
  if (stored) {
    if (!localStorage.getItem(ik)) localStorage.setItem(ik, stored);
    return JSON.parse(stored);
  }
  const data = { ...createDefaultData(), ...SEED_DEFAULT };
  localStorage.setItem(sk, JSON.stringify(data));
  localStorage.setItem(ik, JSON.stringify(data));
  return data;
};

function normalizeEmail(email, index) {
  return {
    id: email.id || `email_custom_${index}`,
    threadId: email.threadId || email.id || `thread_custom_${index}`,
    from: email.from || { name: 'Unknown', email: 'unknown@example.com' },
    to: email.to || [],
    cc: email.cc || [],
    bcc: email.bcc || [],
    subject: email.subject || '(No Subject)',
    body: email.body || '',
    snippet: email.snippet || (email.body || '').replace(/<[^>]*>/g, '').slice(0, 100),
    timestamp: email.timestamp || email.date || new Date().toISOString(),
    read: email.read ?? false,
    starred: email.starred ?? false,
    important: email.important ?? false,
    labels: email.labels || [],
    category: email.category || 'primary',
    folder: email.folder || 'inbox',
    attachments: email.attachments || [],
  };
}

function deepMergeWithDefaults(defaults, custom) {
  if (!custom) return defaults;
  const result = { ...defaults };
  for (const key in custom) {
    if (custom[key] !== null && custom[key] !== undefined) {
      if (key === 'emails' && Array.isArray(custom[key])) {
        result[key] = custom[key].map((e, i) => normalizeEmail(e, i));
      } else if (typeof custom[key] === 'object' && !Array.isArray(custom[key]) && typeof defaults[key] === 'object' && !Array.isArray(defaults[key])) {
        result[key] = deepMergeWithDefaults(defaults[key], custom[key]);
      } else {
        result[key] = custom[key];
      }
    }
  }
  return result;
}

// --- Default data ---

export const CURRENT_USER = {
  userId: 'u1',
  username: 'Alice Anderson',
  email: 'alice@shopgym.com',
  avatar: null
};

export const LABELS = [
  { id: 'l1', name: 'Work', color: '#ef4444' },     // red
  { id: 'l2', name: 'Personal', color: '#3b82f6' }, // blue
  { id: 'l3', name: 'Travel', color: '#22c55e' },   // green
  { id: 'l4', name: 'Finance', color: '#eab308' },  // yellow
];

// Fixed timestamp base for reproducible data
const BASE_TIME = new Date('2026-02-09T12:00:00Z').getTime();

const generateEmails = () => {
  const emails = [];

  // Thread 1: Project Update (unread, starred, important)
  emails.push({
    id: 'email_1',
    threadId: 'thread_1',
    from: { name: 'Alice Smith', email: 'alice@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Q4 Project Roadmap Update',
    body: 'Hi everyone, <br><br>Here is the updated roadmap for Q4. Please review the attached document.<br><br>Best,<br>Alice',
    snippet: 'Hi everyone, Here is the updated roadmap for Q4. Please review...',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 30).toISOString(), // 30 mins ago
    read: false,
    starred: true,
    important: true,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: [
      { id: 'attach_1', name: 'roadmap_q4.pdf', size: '2.4 KB', type: 'application/pdf', url: '/files/_default/roadmap_q4.pdf' }
    ]
  });

  // Thread 2: Lunch Plans (Conversation with 3 emails)
  emails.push({
    id: 'email_2',
    threadId: 'thread_2',
    from: { name: 'Bob Jones', email: 'bob@friends.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Lunch tomorrow?',
    body: 'Hey! Are we still on for lunch tomorrow at 12?',
    snippet: 'Hey! Are we still on for lunch tomorrow at 12?',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    read: true,
    starred: false,
    important: false,
    labels: ['l2'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_3',
    threadId: 'thread_2',
    from: { name: 'Alice Anderson', email: 'alice@shopgym.com', avatar: CURRENT_USER.avatar },
    to: [{ name: 'Bob Jones', email: 'bob@friends.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Lunch tomorrow?',
    body: 'Yes! Let\'s go to that new burger place.',
    snippet: 'Yes! Let\'s go to that new burger place.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 23).toISOString(), // 23 hours ago
    read: true,
    starred: false,
    important: false,
    labels: ['l2'],
    category: 'primary',
    folder: 'sent',
    attachments: []
  });

  emails.push({
    id: 'email_4',
    threadId: 'thread_2',
    from: { name: 'Bob Jones', email: 'bob@friends.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Lunch tomorrow?',
    body: 'Perfect. See you there!',
    snippet: 'Perfect. See you there!',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    read: false,
    starred: false,
    important: false,
    labels: ['l2'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  // Thread 3: HR Benefits Email (for Task #6 - Benefits Enrollment)
  emails.push({
    id: 'email_hr_benefits',
    threadId: 'thread_hr',
    from: { name: 'HR Department', email: 'HR@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Benefits Enrollment - Action Required',
    body: `Dear Employee,<br><br>
It's time for our annual benefits enrollment! Please complete and return the attached Benefits Form by the end of this month.<br><br>
<strong>Key deadlines:</strong><br>
- Health insurance selection: Feb 28<br>
- 401(k) contribution changes: Feb 28<br>
- FSA enrollment: Feb 28<br><br>
If you have any questions, please contact HR.<br><br>
Best regards,<br>
Human Resources`,
    snippet: "It's time for our annual benefits enrollment! Please complete and return...",
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 5).toISOString(), // 5 hours ago
    read: false,
    starred: false,
    important: true,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: [
      { id: 'attach_benefits', name: 'Benefits_Form.pdf', size: '2.4 KB', type: 'application/pdf', url: '/files/_default/Benefits_Form.pdf' }
    ]
  });

  // Thread 4: Q1 Budget Discussion (for Task #10)
  emails.push({
    id: 'email_budget_1',
    threadId: 'thread_budget',
    from: { name: 'Sarah Manager', email: 'sarah@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Mike', email: 'mike@company.com' }, { name: 'Lisa', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Q1 Budget Discussion',
    body: `Hi team,<br><br>
Let's discuss our Q1 budget allocation. I'm proposing we start with $50,000 for the initial phase.<br><br>
Please share your thoughts and proposed numbers.<br><br>
Sarah`,
    snippet: "Let's discuss our Q1 budget allocation. I'm proposing $50,000...",
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 48).toISOString(), // 2 days ago
    read: true,
    starred: false,
    important: true,
    labels: ['l1', 'l4'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_budget_2',
    threadId: 'thread_budget',
    from: { name: 'Mike Chen', email: 'mike@company.com', avatar: null },
    to: [{ name: 'Sarah Manager', email: 'sarah@company.com' }, { name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Lisa', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Q1 Budget Discussion',
    body: `I think we should allocate $75,000 to cover the expanded scope we discussed.<br><br>
Mike`,
    snippet: 'I think we should allocate $75,000 to cover the expanded scope...',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 36).toISOString(), // 36 hours ago
    read: true,
    starred: false,
    important: false,
    labels: ['l1', 'l4'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_budget_3',
    threadId: 'thread_budget',
    from: { name: 'Lisa Anderson', email: 'lisa@company.com', avatar: null },
    to: [{ name: 'Sarah Manager', email: 'sarah@company.com' }, { name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Mike', email: 'mike@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Q1 Budget Discussion',
    body: `Based on last year's data, I'd recommend $62,500 as a balanced approach.<br><br>
Lisa`,
    snippet: "Based on last year's data, I'd recommend $62,500...",
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 24).toISOString(), // 24 hours ago
    read: true,
    starred: false,
    important: false,
    labels: ['l1', 'l4'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_budget_4',
    threadId: 'thread_budget',
    from: { name: 'Alice Anderson', email: 'alice@shopgym.com', avatar: CURRENT_USER.avatar },
    to: [{ name: 'Sarah Manager', email: 'sarah@company.com' }, { name: 'Mike', email: 'mike@company.com' }, { name: 'Lisa', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Q1 Budget Discussion',
    body: `I agree with Mike. Let's go with $75,000 to be safe.<br><br>
- Alice`,
    snippet: "I agree with Mike. Let's go with $75,000 to be safe.",
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 12).toISOString(), // 12 hours ago
    read: true,
    starred: false,
    important: false,
    labels: ['l1', 'l4'],
    category: 'primary',
    folder: 'sent',
    attachments: []
  });

  // Social Tab
  emails.push({
    id: 'email_social_1',
    threadId: 'thread_social_1',
    from: { name: 'LinkedIn', email: 'notifications@linkedin.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'You appeared in 5 searches this week',
    body: 'People are looking for you. See who viewed your profile.',
    snippet: 'People are looking for you. See who viewed your profile.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 5).toISOString(),
    read: false,
    starred: false,
    important: false,
    labels: [],
    category: 'social',
    folder: 'inbox',
    attachments: []
  });

  // Promotions Tab
  emails.push({
    id: 'email_promo_1',
    threadId: 'thread_promo_1',
    from: { name: 'ShopGym', email: 'store-news@shopgym.example', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Your order has shipped',
    body: 'Your package is on the way. Track your package here.',
    snippet: 'Your package is on the way. Track your package here.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 48).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'promotions',
    folder: 'inbox',
    attachments: []
  });

  // Spam
  emails.push({
    id: 'email_spam_1',
    threadId: 'thread_spam_1',
    from: { name: 'Prince Henry', email: 'money@rich.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'URGENT BUSINESS PROPOSAL',
    body: 'I have 50 million dollars for you...',
    snippet: 'I have 50 million dollars for you...',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 100).toISOString(),
    read: false,
    starred: false,
    important: false,
    labels: [],
    category: 'primary',
    folder: 'spam',
    attachments: []
  });

  // Trash
  emails.push({
    id: 'email_trash_1',
    threadId: 'thread_trash_1',
    from: { name: 'Newsletter', email: 'news@letter.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Weekly Digest',
    body: 'Here is your weekly digest...',
    snippet: 'Here is your weekly digest...',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 200).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'promotions',
    folder: 'trash',
    attachments: []
  });

  // Additional Social emails
  emails.push({
    id: 'email_social_2',
    threadId: 'thread_social_2',
    from: { name: 'Twitter', email: 'notify@twitter.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: '@alice_dev mentioned you in a tweet',
    body: '@alice_dev mentioned you: "Great work by @demouser on the new feature rollout! The UI improvements are fantastic."',
    snippet: '@alice_dev mentioned you: "Great work by @demouser on the new feature rollout!"',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 3).toISOString(),
    read: false,
    starred: false,
    important: false,
    labels: [],
    category: 'social',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_social_3',
    threadId: 'thread_social_3',
    from: { name: 'Facebook', email: 'notification@facebookmail.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'You have 3 new friend requests',
    body: 'You have 3 new friend requests on Facebook. See who wants to connect with you.',
    snippet: 'You have 3 new friend requests on Facebook.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 8).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'social',
    folder: 'inbox',
    attachments: []
  });

  // Additional Promotions emails
  emails.push({
    id: 'email_promo_2',
    threadId: 'thread_promo_2',
    from: { name: 'GymEats', email: 'receipts@gymeats.example', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Your GymEats receipt - $23.45',
    body: 'Thanks for your order from Chipotle Mexican Grill. Your total was $23.45.',
    snippet: 'Thanks for your order from Chipotle Mexican Grill. Total: $23.45',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 36).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'promotions',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_promo_3',
    threadId: 'thread_promo_3',
    from: { name: 'Spotify', email: 'noreply@spotify.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Your Spotify Premium invoice for February 2026',
    body: 'Your Spotify Premium subscription has been renewed. Amount charged: $9.99.',
    snippet: 'Your Spotify Premium subscription has been renewed. Amount: $9.99',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 72).toISOString(),
    read: false,
    starred: false,
    important: false,
    labels: [],
    category: 'promotions',
    folder: 'inbox',
    attachments: []
  });

  // Email with multiple attachments
  emails.push({
    id: 'email_attachments_1',
    threadId: 'thread_attachments_1',
    from: { name: 'David Park', email: 'david@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [{ name: 'Sarah Manager', email: 'sarah@company.com' }],
    bcc: [],
    subject: 'Q4 Reports and Assets',
    body: `Hi,<br><br>
Please find attached the Q4 reports and related assets for your review.<br><br>
- Q4 Financial Report (PDF)<br>
- Team Photo (JPEG)<br>
- Budget Spreadsheet (XLSX)<br>
- Project Presentation (PDF)<br><br>
Let me know if you have any questions.<br><br>
David`,
    snippet: 'Please find attached the Q4 reports and related assets for your review.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 6).toISOString(),
    read: false,
    starred: false,
    important: true,
    labels: ['l1', 'l4'],
    category: 'primary',
    folder: 'inbox',
    attachments: [
      { id: 'attach_q4_1', name: 'Q4_Financial_Report.pdf', size: '3.2 MB', type: 'application/pdf', url: '/files/_default/Q4_Financial_Report.pdf' },
      { id: 'attach_q4_2', name: 'team_photo_q4.jpg', size: '1.8 MB', type: 'image/jpeg', url: '/files/_default/team_photo_q4.jpg' },
      { id: 'attach_q4_3', name: 'Budget_2026.xlsx', size: '456 KB', type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', url: '/files/_default/Budget_2026.xlsx' },
      { id: 'attach_q4_4', name: 'Q4_Presentation.pdf', size: '5.1 MB', type: 'application/pdf', url: '/files/_default/Q4_Presentation.pdf' }
    ]
  });

  // Longer thread (6+ messages) - Team Sprint Discussion
  emails.push({
    id: 'email_sprint_1',
    threadId: 'thread_sprint',
    from: { name: 'Emma Wilson', email: 'emma@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Mike Chen', email: 'mike@company.com' }, { name: 'Lisa Anderson', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Sprint 12 Planning - Input Needed',
    body: `Hi team,<br><br>
Sprint 12 kicks off next Monday. I need everyone's input on the following items by Friday:<br>
1. Feature priorities for this sprint<br>
2. Any technical debt we should address<br>
3. Estimated story points per item<br><br>
Emma`,
    snippet: 'Sprint 12 kicks off next Monday. I need everyone\'s input on the following items.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 96).toISOString(), // 4 days ago
    read: true,
    starred: false,
    important: true,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_sprint_2',
    threadId: 'thread_sprint',
    from: { name: 'Mike Chen', email: 'mike@company.com', avatar: null },
    to: [{ name: 'Emma Wilson', email: 'emma@company.com' }, { name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Lisa Anderson', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Sprint 12 Planning - Input Needed',
    body: `Hi Emma,<br><br>
From my side:<br>
1. Priority should be the authentication refactor and the dashboard improvements<br>
2. The API rate limiting issue has been causing problems — let's tackle that<br>
3. Auth refactor: 8 points, Dashboard: 5 points, Rate limiting: 3 points<br><br>
Mike`,
    snippet: 'Priority should be the authentication refactor and the dashboard improvements.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 90).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_sprint_3',
    threadId: 'thread_sprint',
    from: { name: 'Lisa Anderson', email: 'lisa@company.com', avatar: null },
    to: [{ name: 'Emma Wilson', email: 'emma@company.com' }, { name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Mike Chen', email: 'mike@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Sprint 12 Planning - Input Needed',
    body: `All,<br><br>
I agree with Mike on the priorities. I'd also add:<br>
- The mobile responsiveness fixes (users have been complaining)<br>
- Documentation updates for the new API endpoints<br><br>
Mobile fixes: ~5 points, Docs: 2 points<br><br>
Lisa`,
    snippet: 'I agree with Mike on the priorities. I\'d also add the mobile responsiveness fixes.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 80).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_sprint_4',
    threadId: 'thread_sprint',
    from: { name: 'Alice Anderson', email: 'alice@shopgym.com', avatar: CURRENT_USER.avatar },
    to: [{ name: 'Emma Wilson', email: 'emma@company.com' }, { name: 'Mike Chen', email: 'mike@company.com' }, { name: 'Lisa Anderson', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Sprint 12 Planning - Input Needed',
    body: `Team,<br><br>
Great input! I'll add:<br>
- Performance optimization for the search feature (it's been slow)<br>
- Unit tests coverage improvement (we're at 62%, target 80%)<br><br>
Search perf: 5 points, Tests: 8 points<br><br>
That brings our total to 36 points — we might need to cut something. Let's discuss Monday.<br><br>
- Alice`,
    snippet: 'Great input! I\'ll add: Performance optimization for the search feature.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 72).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'primary',
    folder: 'sent',
    attachments: []
  });

  emails.push({
    id: 'email_sprint_5',
    threadId: 'thread_sprint',
    from: { name: 'Emma Wilson', email: 'emma@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Mike Chen', email: 'mike@company.com' }, { name: 'Lisa Anderson', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Sprint 12 Planning - Input Needed',
    body: `Good call on the 36 points. Our velocity has been 28-32 points. We should cut either the test coverage or documentation.<br><br>
Thoughts? I'm leaning towards deferring docs to sprint 13 since the API is still changing anyway.<br><br>
Emma`,
    snippet: 'Good call on the 36 points. Our velocity has been 28-32 points.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 60).toISOString(),
    read: true,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_sprint_6',
    threadId: 'thread_sprint',
    from: { name: 'Mike Chen', email: 'mike@company.com', avatar: null },
    to: [{ name: 'Emma Wilson', email: 'emma@company.com' }, { name: 'Alice Anderson', email: 'alice@shopgym.com' }, { name: 'Lisa Anderson', email: 'lisa@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Re: Sprint 12 Planning - Input Needed',
    body: `+1 on deferring docs. The API changes next sprint will make any docs we write now outdated anyway.<br><br>
So final list: Auth refactor (8), Dashboard (5), Rate limiting (3), Mobile fixes (5), Search perf (5), Tests (8) = 34 points.<br><br>
That should be doable. See everyone Monday!<br>
Mike`,
    snippet: '+1 on deferring docs. Final list: Auth refactor (8), Dashboard (5), Rate limiting (3)...',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 48).toISOString(),
    read: false,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'primary',
    folder: 'inbox',
    attachments: []
  });

  // Pre-existing draft
  emails.push({
    id: 'email_draft_1',
    threadId: 'thread_draft_1',
    from: { name: 'Alice Anderson', email: 'alice@shopgym.com', avatar: CURRENT_USER.avatar },
    to: [{ name: 'alice@company.com', email: 'alice@company.com' }],
    cc: [],
    bcc: [],
    subject: 'Meeting Notes',
    body: 'Hi Alice,\n\nHere are the notes from our meeting yesterday:\n\n1. Reviewed Q4 roadmap\n2. Discussed timeline for new features\n3. ',
    snippet: 'Hi Alice, Here are the notes from our meeting yesterday: 1. Reviewed Q4 roadmap',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 90).toISOString(), // 90 mins ago
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'primary',
    folder: 'drafts',
    attachments: []
  });

  // Updates category emails
  emails.push({
    id: 'email_updates_1',
    threadId: 'thread_updates_1',
    from: { name: 'Chase Bank', email: 'no-reply@chase.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Your February 2026 statement is ready',
    body: 'Your Chase Checking Account statement for February 2026 is now available. Your balance is $3,248.76. Log in to view your full statement.',
    snippet: 'Your Chase Checking Account statement for February 2026 is now available.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 4).toISOString(), // 4 hours ago
    read: false,
    starred: false,
    important: false,
    labels: ['l4'],
    category: 'updates',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_updates_2',
    threadId: 'thread_updates_2',
    from: { name: 'ShopMail', email: 'no-reply@security.shopmail.example', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: 'Security alert: New sign-in on Windows',
    body: 'Your ShopMail account alice@shopgym.com was just signed in to from a Windows device. If this was you, you can ignore this alert. If not, we recommend securing your account.',
    snippet: 'Your ShopMail account was just signed in to from a Windows device.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 20).toISOString(), // 20 hours ago
    read: true,
    starred: false,
    important: false,
    labels: [],
    category: 'updates',
    folder: 'inbox',
    attachments: []
  });

  // Forums category emails
  emails.push({
    id: 'email_forums_1',
    threadId: 'thread_forums_1',
    from: { name: 'Python Mailing List', email: 'python-dev@python.org', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: '[Python-dev] PEP 740 - Index Support for Verifiable Build Provenance',
    body: 'Hi all, I\'d like to propose a new PEP for adding index support for verifiable build provenance. The main goal is to allow package indices to support attestations...',
    snippet: 'I\'d like to propose a new PEP for adding index support for verifiable build provenance.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 10).toISOString(), // 10 hours ago
    read: false,
    starred: false,
    important: false,
    labels: [],
    category: 'forums',
    folder: 'inbox',
    attachments: []
  });

  emails.push({
    id: 'email_forums_2',
    threadId: 'thread_forums_2',
    from: { name: 'Company All-Hands Group', email: 'all-hands@company.com', avatar: null },
    to: [{ name: 'Alice Anderson', email: 'alice@shopgym.com' }],
    cc: [],
    bcc: [],
    subject: '[Company] Engineering All-Hands Notes - Feb 2026',
    body: 'Hi everyone, here are the notes from our February Engineering All-Hands. Key topics covered: roadmap review, hiring update, and new engineering principles.',
    snippet: 'Here are the notes from our February Engineering All-Hands meeting.',
    timestamp: new Date(BASE_TIME - 1000 * 60 * 60 * 30).toISOString(), // 30 hours ago
    read: true,
    starred: false,
    important: false,
    labels: ['l1'],
    category: 'forums',
    folder: 'inbox',
    attachments: []
  });

  // --- ambient demo mailbox (auto-added so bare-tab browsing is also full) ---
  emails.push({"id": "ambd_0", "threadId": "ambd_0", "from": {"name": "Megan Anderson", "email": "megan.anderson88@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Mom's birthday — are we still doing brunch?", "body": "Hey sis, I booked a table for six at Sunday's place for 11am. Can you swing by early to help me carry the cake? Let me know if that time still works for you.", "snippet": "Hey sis, I booked a table for six at Sunday's place for 11am. Can you swing by early to help me carry the cake? Let me know if that time sti", "timestamp": "2026-02-09T04:00:00.000Z", "read": false, "starred": true, "important": true, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_1", "threadId": "ambd_1", "from": {"name": "Dad", "email": "robert.anderson1954@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Found your old bike in the garage", "body": "Cleaning out the garage this weekend and I found your green Schwinn from high school. Want me to hold onto it or should I donate it? No rush, just let me know.", "snippet": "Cleaning out the garage this weekend and I found your green Schwinn from high school. Want me to hold onto it or should I donate it? No rush", "timestamp": "2026-02-09T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_2", "threadId": "ambd_2", "from": {"name": "Priya Nair", "email": "priya.nair@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Book club Thursday — chapters 8-14", "body": "Just a reminder we're meeting at my place Thursday at 7. We're covering through chapter fourteen, so no spoilers past that! I'll have tea and those lemon cookies you liked.", "snippet": "Just a reminder we're meeting at my place Thursday at 7. We're covering through chapter fourteen, so no spoilers past that! I'll have tea an", "timestamp": "2026-02-08T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_3", "threadId": "ambd_3", "from": {"name": "Tom Bradley", "email": "tom.bradley.nyc@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Apartment 4B — radiator inspection Tuesday", "body": "Hi Alice, the building super needs access to check the radiators Tuesday between 9 and noon. Will you be home, or should I use the spare key? Thanks for the heads up either way.", "snippet": "Hi Alice, the building super needs access to check the radiators Tuesday between 9 and noon. Will you be home, or should I use the spare key", "timestamp": "2026-02-08T16:00:00.000Z", "read": false, "starred": false, "important": true, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_4", "threadId": "ambd_4", "from": {"name": "Jason Anderson", "email": "jasonanderson@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Fantasy football draft night", "body": "We're locking in the draft for next Friday at 8. You in this year or are you sitting it out again? Chris already called dibs on being commissioner, so brace yourself.", "snippet": "We're locking in the draft for next Friday at 8. You in this year or are you sitting it out again? Chris already called dibs on being commis", "timestamp": "2026-02-08T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_5", "threadId": "ambd_5", "from": {"name": "Laura Kim", "email": "laura.kim.design@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Thank you for the housewarming gift!", "body": "Alice, the ceramic planter is absolutely perfect and it's already sitting in our kitchen window. Thank you so much for thinking of us. You have to come see the place once we finish unpacking!", "snippet": "Alice, the ceramic planter is absolutely perfect and it's already sitting in our kitchen window. Thank you so much for thinking of us. You h", "timestamp": "2026-02-08T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_6", "threadId": "ambd_6", "from": {"name": "Daniel Foster", "email": "dfoster.trips@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Cabin weekend in October — who's driving?", "body": "Locked in the cabin for the second weekend of October. We've got room for six and two cars. Can you drive, or should we figure out a rental? Trying to sort logistics before deposits are due.", "snippet": "Locked in the cabin for the second weekend of October. We've got room for six and two cars. Can you drive, or should we figure out a rental?", "timestamp": "2026-02-08T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_7", "threadId": "ambd_7", "from": {"name": "Grandma Ruth", "email": "ruthanderson.knits@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Just checking in on you, dear", "body": "Haven't heard from you in a couple weeks and wanted to make sure everything's alright. I finished the blue scarf I was making for you, so come by whenever you can. Love you lots.", "snippet": "Haven't heard from you in a couple weeks and wanted to make sure everything's alright. I finished the blue scarf I was making for you, so co", "timestamp": "2026-02-08T00:00:00.000Z", "read": false, "starred": true, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_8", "threadId": "ambd_8", "from": {"name": "Nina Alvarez", "email": "nina.alvarez@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Girls' dinner Saturday?", "body": "It's been way too long since we all got together. Thinking that little Thai place on Court Street this Saturday around 7. Free? I'll text the group chat if you're a yes.", "snippet": "It's been way too long since we all got together. Thinking that little Thai place on Court Street this Saturday around 7. Free? I'll text th", "timestamp": "2026-02-07T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_9", "threadId": "ambd_9", "from": {"name": "Kevin Doyle", "email": "kevin.doyle.bk@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Package left with me", "body": "Hey neighbor, a box got delivered to my door with your name on it this afternoon. I'll be home all evening, so knock whenever. Nothing perishable from the looks of it.", "snippet": "Hey neighbor, a box got delivered to my door with your name on it this afternoon. I'll be home all evening, so knock whenever. Nothing peris", "timestamp": "2026-02-07T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_10", "threadId": "ambd_10", "from": {"name": "Sophie Anderson", "email": "sophie.a.college@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Can I crash with you next month?", "body": "I've got a conference in the city the third week of September and hotels are insane. Any chance I could take your couch for three nights? I promise to bring good coffee and stay out of your way.", "snippet": "I've got a conference in the city the third week of September and hotels are insane. Any chance I could take your couch for three nights? I ", "timestamp": "2026-02-07T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_11", "threadId": "ambd_11", "from": {"name": "Marcus Webb", "email": "marcus.webb@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Recap: Saturday hiking group", "body": "Great turnout on the Palisades trail this weekend — twelve of us plus Rosa's dog. Next month we're eyeing Breakneck Ridge. Photos are in the shared album if you want to grab any.", "snippet": "Great turnout on the Palisades trail this weekend — twelve of us plus Rosa's dog. Next month we're eyeing Breakneck Ridge. Photos are in the", "timestamp": "2026-02-07T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_12", "threadId": "ambd_12", "from": {"name": "Ellen Park", "email": "ellen.park.pta@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Community garden plot renewal", "body": "Renewals for next season's plots are due by the end of the month. You had bed 14 this year — want me to put you down for the same one? A few new folks are on the waitlist so let me know soon.", "snippet": "Renewals for next season's plots are due by the end of the month. You had bed 14 this year — want me to put you down for the same one? A few", "timestamp": "2026-02-07T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_13", "threadId": "ambd_13", "from": {"name": "Chris Halloran", "email": "chris.halloran@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Concert tickets — one extra", "body": "I ended up with a spare ticket to the Wilco show next Thursday. First person to say yes gets it and I thought of you immediately. Doors at 7, want in?", "snippet": "I ended up with a spare ticket to the Wilco show next Thursday. First person to say yes gets it and I thought of you immediately. Doors at 7", "timestamp": "2026-02-07T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_14", "threadId": "ambd_14", "from": {"name": "Aunt Carol", "email": "carol.mercer@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Family reunion date poll", "body": "We're trying to nail down a weekend for the reunion next summer. Uncle Pete is pushing for July but I think August is cooler. Can you fill out the little date poll I'm sending around? Every vote counts.", "snippet": "We're trying to nail down a weekend for the reunion next summer. Uncle Pete is pushing for July but I think August is cooler. Can you fill o", "timestamp": "2026-02-06T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_15", "threadId": "ambd_15", "from": {"name": "Rachel Green", "email": "rachel.green.bakes@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "That sourdough recipe you asked for", "body": "Finally writing down the sourdough recipe I promised you at dinner. The trick is the overnight cold proof in the fridge — don't skip it. Text me a photo when you try it, I want to see!", "snippet": "Finally writing down the sourdough recipe I promised you at dinner. The trick is the overnight cold proof in the fridge — don't skip it. Tex", "timestamp": "2026-02-06T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_16", "threadId": "ambd_16", "from": {"name": "Group Chat: The Usual Suspects", "email": "notifications@groupme.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "18 new messages in The Usual Suspects", "body": "You have unread activity: Nina shared a photo, Chris asked about weekend plans, and Dan started a poll about the cabin trip. Tap to catch up on the conversation.", "snippet": "You have unread activity: Nina shared a photo, Chris asked about weekend plans, and Dan started a poll about the cabin trip. Tap to catch up", "timestamp": "2026-02-06T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_17", "threadId": "ambd_17", "from": {"name": "Ben Carter", "email": "ben.carter.music@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Sorry I missed your call", "body": "Saw I had two missed calls from you last night — everything okay? I was at rehearsal with my phone on silent. Give me a ring back whenever, I'm around all day tomorrow.", "snippet": "Saw I had two missed calls from you last night — everything okay? I was at rehearsal with my phone on silent. Give me a ring back whenever, ", "timestamp": "2026-02-06T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_18", "threadId": "ambd_18", "from": {"name": "Olivia Bennett", "email": "olivia.bennett@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Baby shower planning for Dana", "body": "A few of us are throwing Dana a surprise shower the first Sunday of next month. Can you help with decorations, or would you rather handle the cake order? Either way I'm so glad you're in.", "snippet": "A few of us are throwing Dana a surprise shower the first Sunday of next month. Can you help with decorations, or would you rather handle th", "timestamp": "2026-02-06T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_19", "threadId": "ambd_19", "from": {"name": "Mr. Petrakis", "email": "g.petrakis.landlord@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Lease renewal for next year", "body": "Hi Alice, your lease is up for renewal in November. Rent will stay the same if you re-sign by October, otherwise it goes up a bit. Let me know your plans and I'll send the paperwork over.", "snippet": "Hi Alice, your lease is up for renewal in November. Rent will stay the same if you re-sign by October, otherwise it goes up a bit. Let me kn", "timestamp": "2026-02-06T00:00:00.000Z", "read": false, "starred": true, "important": true, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_20", "threadId": "ambd_20", "from": {"name": "Hannah Reyes", "email": "hannah.reyes@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Coffee this week? It's been ages", "body": "I keep meaning to text and then life happens. Can we finally grab a coffee this week and actually catch up properly? I miss our long rambling chats. Tuesday or Wednesday morning both work for me.", "snippet": "I keep meaning to text and then life happens. Can we finally grab a coffee this week and actually catch up properly? I miss our long ramblin", "timestamp": "2026-02-05T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_21", "threadId": "ambd_21", "from": {"name": "Uncle Pete", "email": "pete.mercer.fish@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Come out fishing with us Sunday", "body": "Taking the boat out early Sunday if the weather holds. Bring nothing but a hat and your appetite — I've got the rest covered. Your cousin's coming too so it'll be a full crew.", "snippet": "Taking the boat out early Sunday if the weather holds. Bring nothing but a hat and your appetite — I've got the rest covered. Your cousin's ", "timestamp": "2026-02-05T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_22", "threadId": "ambd_22", "from": {"name": "Grace Liu", "email": "grace.liu.nyc@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Moving day — could use a hand", "body": "We're finally moving into the new place on the 20th and I'm calling in every favor I have. Any chance you're free that Saturday morning? Pizza and my eternal gratitude are the going rate.", "snippet": "We're finally moving into the new place on the 20th and I'm calling in every favor I have. Any chance you're free that Saturday morning? Piz", "timestamp": "2026-02-05T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_23", "threadId": "ambd_23", "from": {"name": "Sam Whitfield", "email": "sam.whitfield@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Trivia team needs you back", "body": "We came in third last week without you and honestly the geography round was a bloodbath. Please tell me you're free this Wednesday. The team is not the same without our history expert.", "snippet": "We came in third last week without you and honestly the geography round was a bloodbath. Please tell me you're free this Wednesday. The team", "timestamp": "2026-02-05T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_24", "threadId": "ambd_24", "from": {"name": "Mom", "email": "linda.anderson@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Did you eat today?", "body": "Just your mother checking that you're taking care of yourself. Call me when you get a chance — I want to hear how the new project is going. Also your father says hi and can't work the TV remote again.", "snippet": "Just your mother checking that you're taking care of yourself. Call me when you get a chance — I want to hear how the new project is going. ", "timestamp": "2026-02-05T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_25", "threadId": "ambd_25", "from": {"name": "Isabel Ortega", "email": "isabel.ortega@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Potluck this Friday — bring a dish", "body": "Hosting a little potluck at my place Friday evening, super casual. Can you bring that roasted veggie thing you made last time? Everyone still talks about it. Starts around 6:30, come hungry.", "snippet": "Hosting a little potluck at my place Friday evening, super casual. Can you bring that roasted veggie thing you made last time? Everyone stil", "timestamp": "2026-02-05T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_26", "threadId": "ambd_26", "from": {"name": "Amazon.com", "email": "auto-confirm@amazon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Amazon.com order of \"Bamboo Cutting Board Set\" has shipped", "body": "Hi Alice, your package is on the way and should arrive Wednesday, August 5. Track your shipment anytime from Your Orders.", "snippet": "Hi Alice, your package is on the way and should arrive Wednesday, August 5. Track your shipment anytime from Your Orders.", "timestamp": "2026-02-04T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_27", "threadId": "ambd_27", "from": {"name": "Best Buy", "email": "BestBuyInfo@emailinfo.bestbuy.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Thanks for your order — pickup ready at Atlantic Terminal", "body": "Your Anker USB-C charger is ready for in-store pickup. Bring a photo ID and your order number when you come by.", "snippet": "Your Anker USB-C charger is ready for in-store pickup. Bring a photo ID and your order number when you come by.", "timestamp": "2026-02-04T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_28", "threadId": "ambd_28", "from": {"name": "IKEA", "email": "noreply@email.ikea.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Order confirmation #IK-4471902", "body": "Thanks for shopping with IKEA, Alice. Your KALLAX shelf unit and two drawer inserts are being prepared for delivery next Tuesday.", "snippet": "Thanks for shopping with IKEA, Alice. Your KALLAX shelf unit and two drawer inserts are being prepared for delivery next Tuesday.", "timestamp": "2026-02-04T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_29", "threadId": "ambd_29", "from": {"name": "Etsy", "email": "transaction@mail.etsy.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your receipt from MapleLeafCeramics", "body": "Thank you for supporting a small shop! Your handmade speckled mug is confirmed and the seller will ship within 3 business days.", "snippet": "Thank you for supporting a small shop! Your handmade speckled mug is confirmed and the seller will ship within 3 business days.", "timestamp": "2026-02-04T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_30", "threadId": "ambd_30", "from": {"name": "Uber Receipts", "email": "receipts@uber.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Thursday morning trip with Uber", "body": "Thanks for riding, Alice. Your trip from Park Slope to DUMBO totaled $14.60, including tip. Tap to see your full receipt.", "snippet": "Thanks for riding, Alice. Your trip from Park Slope to DUMBO totaled $14.60, including tip. Tap to see your full receipt.", "timestamp": "2026-02-04T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_31", "threadId": "ambd_31", "from": {"name": "DoorDash", "email": "no-reply@doordash.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Order receipt: Thai Basil Kitchen", "body": "Your order was delivered! Pad see ew and spring rolls came to $28.45. We hope everything arrived hot and tasty.", "snippet": "Your order was delivered! Pad see ew and spring rolls came to $28.45. We hope everything arrived hot and tasty.", "timestamp": "2026-02-04T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_32", "threadId": "ambd_32", "from": {"name": "Netflix", "email": "info@mailer.netflix.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "New arrivals you might like this week", "body": "Because you watched cozy documentaries, we lined up a few new titles for your list. Settle in whenever you're ready.", "snippet": "Because you watched cozy documentaries, we lined up a few new titles for your list. Settle in whenever you're ready.", "timestamp": "2026-02-03T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_33", "threadId": "ambd_33", "from": {"name": "Spotify", "email": "no-reply@spotify.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Discover Weekly is refreshed", "body": "Thirty new songs picked just for you are ready to play. Give them a listen before they update again next Monday.", "snippet": "Thirty new songs picked just for you are ready to play. Give them a listen before they update again next Monday.", "timestamp": "2026-02-03T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_34", "threadId": "ambd_34", "from": {"name": "YouTube", "email": "noreply@youtube.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "A channel you follow just posted", "body": "Smitten Kitchen uploaded a new video: a one-bowl summer plum cake. Watch it now or save it for later.", "snippet": "Smitten Kitchen uploaded a new video: a one-bowl summer plum cake. Watch it now or save it for later.", "timestamp": "2026-02-03T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_35", "threadId": "ambd_35", "from": {"name": "Morning Brew", "email": "crew@morningbrew.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "☕ Markets wobble, coffee prices climb", "body": "Good morning! Today we unpack why your latte might cost more this fall and what a quiet week on Wall Street really means.", "snippet": "Good morning! Today we unpack why your latte might cost more this fall and what a quiet week on Wall Street really means.", "timestamp": "2026-02-03T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_36", "threadId": "ambd_36", "from": {"name": "TLDR Newsletter", "email": "dan@tldrnewsletter.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "TLDR: A big week in open-source tooling", "body": "Your five-minute tech briefing is here. Today's highlights include a popular framework's major release and a clever new CLI.", "snippet": "Your five-minute tech briefing is here. Today's highlights include a popular framework's major release and a clever new CLI.", "timestamp": "2026-02-03T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_37", "threadId": "ambd_37", "from": {"name": "Anne Helen Petersen", "email": "annehelen@substack.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "On rest, and why we're so bad at it", "body": "This week's essay is about the quiet guilt of taking a real day off. Reply and tell me how you actually unplug.", "snippet": "This week's essay is about the quiet guilt of taking a real day off. Reply and tell me how you actually unplug.", "timestamp": "2026-02-03T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_38", "threadId": "ambd_38", "from": {"name": "Duolingo", "email": "hello@duolingo.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Keep your 12-day streak alive! 🔥", "body": "You're doing great with Spanish, Alice. A quick five-minute lesson today will keep your streak going strong.", "snippet": "You're doing great with Spanish, Alice. A quick five-minute lesson today will keep your streak going strong.", "timestamp": "2026-02-02T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_39", "threadId": "ambd_39", "from": {"name": "Starbucks Rewards", "email": "rewards@e.starbucks.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You've earned a free handcrafted drink ⭐", "body": "Congrats! Your Stars added up to a reward. Redeem it for any handcrafted beverage on your next visit before it expires.", "snippet": "Congrats! Your Stars added up to a reward. Redeem it for any handcrafted beverage on your next visit before it expires.", "timestamp": "2026-02-02T16:00:00.000Z", "read": false, "starred": true, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_40", "threadId": "ambd_40", "from": {"name": "Target", "email": "orders@target.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your order is out for delivery", "body": "Good news, Alice — your laundry detergent and dish towels are on the truck and should reach your door by 8 PM tonight.", "snippet": "Good news, Alice — your laundry detergent and dish towels are on the truck and should reach your door by 8 PM tonight.", "timestamp": "2026-02-02T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_41", "threadId": "ambd_41", "from": {"name": "The New York Times", "email": "nytdirect@nytimes.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "The Morning: What to know today", "body": "Here's your daily briefing with the stories shaping the news, plus a short read on why city gardens are thriving this summer.", "snippet": "Here's your daily briefing with the stories shaping the news, plus a short read on why city gardens are thriving this summer.", "timestamp": "2026-02-02T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_42", "threadId": "ambd_42", "from": {"name": "Airbnb", "email": "automated@airbnb.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your reservation in the Hudson Valley is confirmed", "body": "You're all set for your September getaway! Your host Marion left a note with check-in details and a coffee shop recommendation.", "snippet": "You're all set for your September getaway! Your host Marion left a note with check-in details and a coffee shop recommendation.", "timestamp": "2026-02-02T04:00:00.000Z", "read": true, "starred": true, "important": true, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_43", "threadId": "ambd_43", "from": {"name": "Goodreads", "email": "no-reply@goodreads.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "A book on your want-to-read list is on sale", "body": "The novel you saved last month just dropped to $3.99 as an ebook. It might be the perfect pick for your weekend.", "snippet": "The novel you saved last month just dropped to $3.99 as an ebook. It might be the perfect pick for your weekend.", "timestamp": "2026-02-02T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_44", "threadId": "ambd_44", "from": {"name": "REI Co-op", "email": "notifications@notifications.rei.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your order has shipped — hello, hiking season", "body": "Your trail runners and wool socks are on their way and should arrive Friday. Adventure awaits, Alice.", "snippet": "Your trail runners and wool socks are on their way and should arrive Friday. Adventure awaits, Alice.", "timestamp": "2026-02-01T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_45", "threadId": "ambd_45", "from": {"name": "Etsy", "email": "marketing@mail.etsy.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Handmade finds picked for you", "body": "Based on your recent browsing, we gathered a cozy set of ceramics and linen goods you might love. Take a peek this weekend.", "snippet": "Based on your recent browsing, we gathered a cozy set of ceramics and linen goods you might love. Take a peek this weekend.", "timestamp": "2026-02-01T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_46", "threadId": "ambd_46", "from": {"name": "LinkedIn", "email": "messages-noreply@linkedin.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You appeared in 9 searches this week", "body": "Your profile is getting noticed, Alice. Recruiters and peers found you in searches — see who's been looking around.", "snippet": "Your profile is getting noticed, Alice. Recruiters and peers found you in searches — see who's been looking around.", "timestamp": "2026-02-01T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "social", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_47", "threadId": "ambd_47", "from": {"name": "Instacart", "email": "orders@instacart.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your groceries were delivered", "body": "Your shopper Denise finished your order and left it at the door. A few items were substituted — tap to review your receipt.", "snippet": "Your shopper Denise finished your order and left it at the door. A few items were substituted — tap to review your receipt.", "timestamp": "2026-02-01T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_48", "threadId": "ambd_48", "from": {"name": "Medium Daily Digest", "email": "noreply@medium.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Stories for you: focus, food, and slow mornings", "body": "We picked a handful of reads based on what you've enjoyed, including a lovely piece on building a calmer daily routine.", "snippet": "We picked a handful of reads based on what you've enjoyed, including a lovely piece on building a calmer daily routine.", "timestamp": "2026-02-01T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_49", "threadId": "ambd_49", "from": {"name": "Warby Parker", "email": "help@warbyparker.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Home Try-On is on its way", "body": "Five frames are heading to you to test out for free. Keep them for five days, snap some selfies, and send the box back easy.", "snippet": "Five frames are heading to you to test out for free. Keep them for five days, snap some selfies, and send the box back easy.", "timestamp": "2026-02-01T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_50", "threadId": "ambd_50", "from": {"name": "Patagonia", "email": "news@e.patagonia.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Worn Wear: give your gear a second life", "body": "Trade in your gently used items for store credit and help keep clothing out of landfills. Every repair makes a difference.", "snippet": "Trade in your gently used items for store credit and help keep clothing out of landfills. Every repair makes a difference.", "timestamp": "2026-01-31T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "inbox", "attachments": []});
  emails.push({"id": "ambd_51", "threadId": "ambd_51", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Maya Patel", "email": "maya.patel88@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: Brunch on Saturday", "body": "Saturday at 11 works perfectly for me. Let's meet at that new cafe on Bedford Ave — I'll grab us a table by the window if I get there first.", "snippet": "Saturday at 11 works perfectly for me. Let's meet at that new cafe on Bedford Ave — I'll grab us a table by the window if I get there first.", "timestamp": "2026-01-31T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_52", "threadId": "ambd_52", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Dad", "email": "robert.anderson1954@gmail.com"}], "cc": [], "bcc": [], "subject": "Thanks for the birthday call", "body": "It really made my day to hear from you and Mom this morning. The card arrived too — I laughed out loud at the cartoon inside. Talk soon!", "snippet": "It really made my day to hear from you and Mom this morning. The card arrived too — I laughed out loud at the cartoon inside. Talk soon!", "timestamp": "2026-01-31T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_53", "threadId": "ambd_53", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Jenna Kim", "email": "jenna.kim@outlook.com"}], "cc": [], "bcc": [], "subject": "Count me in for the hike", "body": "Yes, I'd love to join the group hike up Breakneck Ridge next weekend. I'll bring extra water and some trail mix to share. What time are we carpooling?", "snippet": "Yes, I'd love to join the group hike up Breakneck Ridge next weekend. I'll bring extra water and some trail mix to share. What time are we c", "timestamp": "2026-01-31T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_54", "threadId": "ambd_54", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sarah Whitfield", "email": "sarah.whitfield@gmail.com"}], "cc": [], "bcc": [], "subject": "My new address", "body": "Here's my new place for the housewarming invites: 214 Carroll Street, Apt 3B, Brooklyn NY 11231. Buzzer is labeled Anderson. Can't wait to have everyone over!", "snippet": "Here's my new place for the housewarming invites: 214 Carroll Street, Apt 3B, Brooklyn NY 11231. Buzzer is labeled Anderson. Can't wait to h", "timestamp": "2026-01-31T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_55", "threadId": "ambd_55", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Tom Reyes", "email": "tom.reyes@gmail.com"}], "cc": [], "bcc": [], "subject": "RSVP — yes to the wedding", "body": "We'd be honored to celebrate with you both on October 12th. Put me down for the chicken, and I'll happily take a seat near the dance floor. So excited for you two!", "snippet": "We'd be honored to celebrate with you both on October 12th. Put me down for the chicken, and I'll happily take a seat near the dance floor. ", "timestamp": "2026-01-31T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_56", "threadId": "ambd_56", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Priya Nair", "email": "priya.nair@gmail.com"}], "cc": [], "bcc": [], "subject": "That recipe you asked for", "body": "Here's the link to the lemon olive oil cake I made last week: it's the one from Smitten Kitchen. Don't skip the glaze — it's the best part. Let me know how it turns out!", "snippet": "Here's the link to the lemon olive oil cake I made last week: it's the one from Smitten Kitchen. Don't skip the glaze — it's the best part. ", "timestamp": "2026-01-30T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_57", "threadId": "ambd_57", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "ValueMart Support", "email": "support@valuemart.com"}], "cc": [], "bcc": [], "subject": "Following up on my return", "body": "I mailed back the blender on Monday using the prepaid label. Could you confirm you've received it and when the refund will post? My order number is VM-4471902. Thanks for your help.", "snippet": "I mailed back the blender on Monday using the prepaid label. Could you confirm you've received it and when the refund will post? My order nu", "timestamp": "2026-01-30T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_58", "threadId": "ambd_58", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Grandma Ruth", "email": "ruth.anderson@aol.com"}], "cc": [], "bcc": [], "subject": "Loved the photos", "body": "Thank you for mailing those old pictures from the lake house — I'd never seen the one of Dad in the canoe. I framed two of them for my hallway. Love you lots.", "snippet": "Thank you for mailing those old pictures from the lake house — I'd never seen the one of Dad in the canoe. I framed two of them for my hallw", "timestamp": "2026-01-30T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_59", "threadId": "ambd_59", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Daniel Osei", "email": "daniel.osei@outlook.com"}], "cc": [], "bcc": [], "subject": "Re: Book club pick", "body": "I finished it last night and I have so many thoughts! Tuesday at 7 still works for me to host. I'll make tea and something with chocolate. See you then.", "snippet": "I finished it last night and I have so many thoughts! Tuesday at 7 still works for me to host. I'll make tea and something with chocolate. S", "timestamp": "2026-01-30T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_60", "threadId": "ambd_60", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Lena Brooks", "email": "lena.brooks@gmail.com"}], "cc": [], "bcc": [], "subject": "Thank you for dinner", "body": "Last night was such a treat — your risotto has officially set the bar too high. Thanks for being so welcoming to my sister too. Let's do it again at my place soon.", "snippet": "Last night was such a treat — your risotto has officially set the bar too high. Thanks for being so welcoming to my sister too. Let's do it ", "timestamp": "2026-01-30T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_61", "threadId": "ambd_61", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Marcus Bell", "email": "marcus.bell@gmail.com"}], "cc": [], "bcc": [], "subject": "Confirming Thursday", "body": "Just locking in our coffee catch-up for Thursday at 3 at the place near your office. I've got a lot of updates to share since the move. See you then!", "snippet": "Just locking in our coffee catch-up for Thursday at 3 at the place near your office. I've got a lot of updates to share since the move. See ", "timestamp": "2026-01-30T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_62", "threadId": "ambd_62", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Aunt Carol", "email": "carol.jennings@yahoo.com"}], "cc": [], "bcc": [], "subject": "Recipe swap", "body": "Here's my grandmother's cornbread recipe like I promised — the secret is a spoonful of honey in the batter. Send me your chili one and we'll call it even. Miss you!", "snippet": "Here's my grandmother's cornbread recipe like I promised — the secret is a spoonful of honey in the batter. Send me your chili one and we'll", "timestamp": "2026-01-29T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_63", "threadId": "ambd_63", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "GymEats Orders", "email": "help@gymeats.com"}], "cc": [], "bcc": [], "subject": "Re: Missing side from my order", "body": "Thanks for the quick reply. The side salad was missing from last night's delivery, but everything else was great. A credit is totally fine — no need to resend. Appreciate it!", "snippet": "Thanks for the quick reply. The side salad was missing from last night's delivery, but everything else was great. A credit is totally fine —", "timestamp": "2026-01-29T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_64", "threadId": "ambd_64", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Nora Feldman", "email": "nora.feldman@gmail.com"}], "cc": [], "bcc": [], "subject": "Sharing the playlist", "body": "Here's the road-trip playlist I threw together for Saturday — feel free to add anything. I front-loaded it with the sing-along stuff so we start strong. Can't wait!", "snippet": "Here's the road-trip playlist I threw together for Saturday — feel free to add anything. I front-loaded it with the sing-along stuff so we s", "timestamp": "2026-01-29T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_65", "threadId": "ambd_65", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Uncle Jim", "email": "jim.anderson@comcast.net"}], "cc": [], "bcc": [], "subject": "Re: Thanksgiving plans", "body": "Count me in for Thanksgiving at your place this year. I'll bring the pies and a big pot of green beans. Let me know if you need me there early to help set up.", "snippet": "Count me in for Thanksgiving at your place this year. I'll bring the pies and a big pot of green beans. Let me know if you need me there ear", "timestamp": "2026-01-29T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_66", "threadId": "ambd_66", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Emily Carter", "email": "emily.carter@outlook.com"}], "cc": [], "bcc": [], "subject": "Following up on the tickets", "body": "Did you manage to grab the concert tickets for the 22nd? Happy to Venmo you my half as soon as you've got them. Thanks for keeping an eye on the drop!", "snippet": "Did you manage to grab the concert tickets for the 22nd? Happy to Venmo you my half as soon as you've got them. Thanks for keeping an eye on", "timestamp": "2026-01-29T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_67", "threadId": "ambd_67", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Dr. Nguyen's Office", "email": "frontdesk@brooklynfamilydental.com"}], "cc": [], "bcc": [], "subject": "Rescheduling my cleaning", "body": "I need to move my Wednesday cleaning to later in the week if possible. Thursday or Friday afternoon would both work for me. Sorry for the short notice, and thank you!", "snippet": "I need to move my Wednesday cleaning to later in the week if possible. Thursday or Friday afternoon would both work for me. Sorry for the sh", "timestamp": "2026-01-29T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_68", "threadId": "ambd_68", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Chloe Martin", "email": "chloe.martin@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: Baby shower", "body": "I'd love to help plan Rachel's shower! I can handle the decorations and take charge of the guest list. Let's hop on a call this weekend to divide up the rest. So fun!", "snippet": "I'd love to help plan Rachel's shower! I can handle the decorations and take charge of the guest list. Let's hop on a call this weekend to d", "timestamp": "2026-01-28T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_69", "threadId": "ambd_69", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Ben Alvarez", "email": "ben.alvarez@gmail.com"}], "cc": [], "bcc": [], "subject": "Here's the article I mentioned", "body": "Sending over that piece on urban gardening we talked about at lunch — the part about balcony herb boxes made me think of your place. Curious what you think.", "snippet": "Sending over that piece on urban gardening we talked about at lunch — the part about balcony herb boxes made me think of your place. Curious", "timestamp": "2026-01-28T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_70", "threadId": "ambd_70", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sophie Anderson", "email": "sophie.anderson02@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: Visiting next month", "body": "Yes! Come stay the weekend of the 15th — the guest room is all yours. I'll plan a walk across the bridge and that dumpling spot you loved. Book your train and let me know!", "snippet": "Yes! Come stay the weekend of the 15th — the guest room is all yours. I'll plan a walk across the bridge and that dumpling spot you loved. B", "timestamp": "2026-01-28T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_71", "threadId": "ambd_71", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Greenpoint Yoga", "email": "hello@greenpointyoga.com"}], "cc": [], "bcc": [], "subject": "Class package question", "body": "Thanks for the warm welcome to the studio. Could you confirm how many classes are left on my ten-pack? I've lost count and want to renew before it runs out.", "snippet": "Thanks for the warm welcome to the studio. Could you confirm how many classes are left on my ten-pack? I've lost count and want to renew bef", "timestamp": "2026-01-28T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_72", "threadId": "ambd_72", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Kevin Zhao", "email": "kevin.zhao@gmail.com"}], "cc": [], "bcc": [], "subject": "Thanks for the referral", "body": "The plumber you recommended came by today and fixed the leak in twenty minutes. I really appreciate you passing along his number — you saved me a huge headache!", "snippet": "The plumber you recommended came by today and fixed the leak in twenty minutes. I really appreciate you passing along his number — you saved", "timestamp": "2026-01-28T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_73", "threadId": "ambd_73", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Hannah Lopez", "email": "hannah.lopez@outlook.com"}], "cc": [], "bcc": [], "subject": "Re: Coffee next week", "body": "Tuesday morning is wide open for me — how about 10 at the little roastery on Franklin? I've been meaning to catch up properly since the summer. Looking forward to it!", "snippet": "Tuesday morning is wide open for me — how about 10 at the little roastery on Franklin? I've been meaning to catch up properly since the summ", "timestamp": "2026-01-28T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_74", "threadId": "ambd_74", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Mom", "email": "linda.anderson1957@gmail.com"}], "cc": [], "bcc": [], "subject": "Made it home safe", "body": "Just walked in the door — the drive back was smooth and traffic was light. Thank you for the leftovers, they're already in the fridge for tomorrow. Love you, talk soon.", "snippet": "Just walked in the door — the drive back was smooth and traffic was light. Thank you for the leftovers, they're already in the fridge for to", "timestamp": "2026-01-27T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_75", "threadId": "ambd_75", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Priya Nair", "email": "priya.nair@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Q3 roadmap review — my sections are ready", "body": "Hi Priya, I've finished the checkout and cart sections of the roadmap deck and dropped them into the shared drive. Let me know if you want me to walk you through the sequencing before Thursday's review. Happy to trim if we're tight on time.", "snippet": "Hi Priya, I've finished the checkout and cart sections of the roadmap deck and dropped them into the shared drive. Let me know if you want m", "timestamp": "2026-01-27T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_76", "threadId": "ambd_76", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Marcus Bell", "email": "marcus.bell@shopgym.com"}], "cc": [], "bcc": [], "subject": "PR #482 — addressed your review comments", "body": "Hey Marcus, I pushed a new commit that handles the null-state edge case you flagged and split the helper into its own module. Should be green now. Mind taking another pass when you get a chance?", "snippet": "Hey Marcus, I pushed a new commit that handles the null-state edge case you flagged and split the helper into its own module. Should be gree", "timestamp": "2026-01-27T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_77", "threadId": "ambd_77", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Dana Whitfield", "email": "dana.whitfield@shopgym.com"}], "cc": [], "bcc": [], "subject": "Weekly status — checkout parity work", "body": "Hi Dana, this week I closed out the tax-rounding bug and got the guest-checkout flow behind a flag. Next up is the address validation rework, which I expect will spill into early next week. No blockers on my end right now.", "snippet": "Hi Dana, this week I closed out the tax-rounding bug and got the guest-checkout flow behind a flag. Next up is the address validation rework", "timestamp": "2026-01-27T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_78", "threadId": "ambd_78", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Tom Reilly", "email": "tom.reilly@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Can you join the design sync Wednesday?", "body": "Hi Tom, Wednesday at 2 works for me. I'll come with the two layout options we discussed and some notes on the mobile breakpoints. See you then.", "snippet": "Hi Tom, Wednesday at 2 works for me. I'll come with the two layout options we discussed and some notes on the mobile breakpoints. See you th", "timestamp": "2026-01-27T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_79", "threadId": "ambd_79", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Rachel Kim", "email": "rachel.kim@northgate-recruiting.com"}], "cc": [], "bcc": [], "subject": "Re: Senior Engineer role — following up", "body": "Hi Rachel, thanks for reaching out. I'm happy with my current role and not looking to move right now, but I appreciate you thinking of me. Feel free to keep me in mind down the line.", "snippet": "Hi Rachel, thanks for reaching out. I'm happy with my current role and not looking to move right now, but I appreciate you thinking of me. F", "timestamp": "2026-01-27T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_80", "threadId": "ambd_80", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Ben Ortiz", "email": "ben.ortiz@shopgym.com"}], "cc": [], "bcc": [], "subject": "Sending over the API contract draft", "body": "Hey Ben, attached is the first draft of the orders API contract. I left a couple of open questions in the comments around pagination and error codes. Would love your thoughts before I circulate it more widely.", "snippet": "Hey Ben, attached is the first draft of the orders API contract. I left a couple of open questions in the comments around pagination and err", "timestamp": "2026-01-26T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_81", "threadId": "ambd_81", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sofia Marchetti", "email": "sofia.marchetti@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Sprint planning — can we push to Friday?", "body": "Hi Sofia, Friday morning is fine by me. I'll have my estimates for the search refactor ready by then. Thanks for the flexibility.", "snippet": "Hi Sofia, Friday morning is fine by me. I'll have my estimates for the search refactor ready by then. Thanks for the flexibility.", "timestamp": "2026-01-26T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_82", "threadId": "ambd_82", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "David Chen", "email": "david.chen@shopgym.com"}], "cc": [], "bcc": [], "subject": "Declining the Friday retro — conflict", "body": "Hi David, I won't be able to make the retro this Friday, I've got a conflicting doctor's appointment. Please go ahead without me and I'll read the notes after. Sorry for the short notice.", "snippet": "Hi David, I won't be able to make the retro this Friday, I've got a conflicting doctor's appointment. Please go ahead without me and I'll re", "timestamp": "2026-01-26T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_83", "threadId": "ambd_83", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Laura Simmons", "email": "laura.simmons@shopgym.com"}], "cc": [], "bcc": [], "subject": "Onboarding doc for the new hire", "body": "Hi Laura, I put together a short onboarding guide for the frontend setup and shared it with you. If it looks good I'll hand it to Jordan on Monday. Let me know if anything's missing.", "snippet": "Hi Laura, I put together a short onboarding guide for the frontend setup and shared it with you. If it looks good I'll hand it to Jordan on ", "timestamp": "2026-01-26T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_84", "threadId": "ambd_84", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Kevin Osei", "email": "kevin.osei@brightpath-vendors.com"}], "cc": [], "bcc": [], "subject": "Re: Contract renewal timeline", "body": "Hi Kevin, thanks for the updated quote. We're planning to renew, but I need to loop in procurement before signing. Can you hold the current pricing through the end of the month while we finalize internally?", "snippet": "Hi Kevin, thanks for the updated quote. We're planning to renew, but I need to loop in procurement before signing. Can you hold the current ", "timestamp": "2026-01-26T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_85", "threadId": "ambd_85", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Nina Patel", "email": "nina.patel@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Bug triage — I'll take the checkout ones", "body": "Hi Nina, I can pick up the three checkout-related tickets from this morning's triage. The payment timeout one looks the most urgent, so I'll start there. Assigning them to myself now.", "snippet": "Hi Nina, I can pick up the three checkout-related tickets from this morning's triage. The payment timeout one looks the most urgent, so I'll", "timestamp": "2026-01-26T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_86", "threadId": "ambd_86", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Greg Halloran", "email": "greg.halloran@shopgym.com"}], "cc": [], "bcc": [], "subject": "Demo recap and next steps", "body": "Hey Greg, thanks for sitting in on the demo today. As discussed, I'll wire up the analytics events next and circle back with a working prototype by end of next week. Shout if priorities shift.", "snippet": "Hey Greg, thanks for sitting in on the demo today. As discussed, I'll wire up the analytics events next and circle back with a working proto", "timestamp": "2026-01-25T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_87", "threadId": "ambd_87", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Emily Ross", "email": "emily.ross@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Coffee chat about the team lead opening", "body": "Hi Emily, I'd love to grab coffee and hear more about the team lead role. Does Tuesday afternoon work for you? I'm free anytime after 1.", "snippet": "Hi Emily, I'd love to grab coffee and hear more about the team lead role. Does Tuesday afternoon work for you? I'm free anytime after 1.", "timestamp": "2026-01-25T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_88", "threadId": "ambd_88", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Hassan Ali", "email": "hassan.ali@shopgym.com"}], "cc": [], "bcc": [], "subject": "Follow-up on the incident postmortem", "body": "Hi Hassan, I finished my write-up of the timeline for last week's outage and added it to the shared postmortem doc. I flagged the alerting gap as the main action item. Can you review before we present to leadership?", "snippet": "Hi Hassan, I finished my write-up of the timeline for last week's outage and added it to the shared postmortem doc. I flagged the alerting g", "timestamp": "2026-01-25T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_89", "threadId": "ambd_89", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Grace Lindqvist", "email": "grace.lindqvist@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Mentorship check-in", "body": "Hi Grace, thanks again for the notes from our last session. I tried the approach you suggested for scoping tickets and it made a real difference this sprint. Looking forward to our next check-in.", "snippet": "Hi Grace, thanks again for the notes from our last session. I tried the approach you suggested for scoping tickets and it made a real differ", "timestamp": "2026-01-25T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_90", "threadId": "ambd_90", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Oliver Grant", "email": "oliver.grant@shopgym.com"}], "cc": [], "bcc": [], "subject": "Handing off the cart migration", "body": "Hey Oliver, since I'll be out for a few days next week, I've documented where things stand on the cart migration and shared the runbook. The only pending piece is the feature-flag cleanup. Ping me if anything's unclear before I'm off.", "snippet": "Hey Oliver, since I'll be out for a few days next week, I've documented where things stand on the cart migration and shared the runbook. The", "timestamp": "2026-01-25T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_91", "threadId": "ambd_91", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sandra Boyle", "email": "sandra.boyle@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Performance review self-assessment", "body": "Hi Sandra, I've submitted my self-assessment in the HR portal and highlighted the checkout reliability work as my biggest win this cycle. Let me know if you'd like me to expand on anything before our one-on-one.", "snippet": "Hi Sandra, I've submitted my self-assessment in the HR portal and highlighted the checkout reliability work as my biggest win this cycle. Le", "timestamp": "2026-01-25T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_92", "threadId": "ambd_92", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Felix Nguyen", "email": "felix.nguyen@shopgym.com"}], "cc": [], "bcc": [], "subject": "Reviewed your design doc — a few thoughts", "body": "Hey Felix, read through your caching design doc and left comments inline. Overall it's solid; my main question is around cache invalidation when a product goes out of stock. Happy to pair on that section if useful.", "snippet": "Hey Felix, read through your caching design doc and left comments inline. Overall it's solid; my main question is around cache invalidation ", "timestamp": "2026-01-24T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_93", "threadId": "ambd_93", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Monica Alvarez", "email": "monica.alvarez@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Can you cover the standup Thursday?", "body": "Hi Monica, sure, I can run standup Thursday while you're out. I'll take notes and send a summary to the channel afterward so you're caught up when you're back.", "snippet": "Hi Monica, sure, I can run standup Thursday while you're out. I'll take notes and send a summary to the channel afterward so you're caught u", "timestamp": "2026-01-24T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_94", "threadId": "ambd_94", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Raj Malhotra", "email": "raj.malhotra@clearloop-solutions.com"}], "cc": [], "bcc": [], "subject": "Re: Integration test environment access", "body": "Hi Raj, thanks for setting up the sandbox. I was able to run our integration suite against it this morning and everything passed. I'll send over the results doc once I've cleaned up the logs.", "snippet": "Hi Raj, thanks for setting up the sandbox. I was able to run our integration suite against it this morning and everything passed. I'll send ", "timestamp": "2026-01-24T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_95", "threadId": "ambd_95", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Claire Donovan", "email": "claire.donovan@shopgym.com"}], "cc": [], "bcc": [], "subject": "Volunteering to lead the accessibility audit", "body": "Hi Claire, I'd like to put my hand up to lead the accessibility audit next quarter. I've been reading up on WCAG and think our checkout flow is a good place to start. Let me know if that fits with your plans for the team.", "snippet": "Hi Claire, I'd like to put my hand up to lead the accessibility audit next quarter. I've been reading up on WCAG and think our checkout flow", "timestamp": "2026-01-24T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_96", "threadId": "ambd_96", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Peter Vasquez", "email": "peter.vasquez@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Lunch and learn topic", "body": "Hey Peter, I'm happy to present at next month's lunch and learn. I was thinking of doing a walkthrough of how we cut checkout latency in half last quarter. Let me know if that works or if you'd prefer something else.", "snippet": "Hey Peter, I'm happy to present at next month's lunch and learn. I was thinking of doing a walkthrough of how we cut checkout latency in hal", "timestamp": "2026-01-24T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "sent", "attachments": []});
  emails.push({"id": "ambd_97", "threadId": "ambd_97", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Priya Raman", "email": "priya.raman@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: brunch this weekend", "body": "Hey Priya! Saturday works great for me, I've been dying to try that new place on Bedford. Sunday I've got a thing in the morning but could do late afternoon if that's easier for", "snippet": "Hey Priya! Saturday works great for me, I've been dying to try that new place on Bedford. Sunday I've got a thing in the morning but could d", "timestamp": "2026-01-24T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_98", "threadId": "ambd_98", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sunrise Appliances Support", "email": "support@sunriseappliances.com"}], "cc": [], "bcc": [], "subject": "Blender stopped working after two weeks", "body": "I purchased the ProBlend 500 on July 12th and it already won't turn on. I've tried a different outlet and held the reset button like the manual says, with no luck. I'd like to know whether I should return it or", "snippet": "I purchased the ProBlend 500 on July 12th and it already won't turn on. I've tried a different outlet and held the reset button like the man", "timestamp": "2026-01-23T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_99", "threadId": "ambd_99", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Grandma Rose", "email": "rose.anderson@outlook.com"}], "cc": [], "bcc": [], "subject": "Happy Birthday!!", "body": "Happy birthday Grandma! I can't believe you're turning 80 this year, you don't look a day over 60. I'm sending a little something in the mail and I really hope I can make it up to see you before", "snippet": "Happy birthday Grandma! I can't believe you're turning 80 this year, you don't look a day over 60. I'm sending a little something in the mai", "timestamp": "2026-01-23T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_100", "threadId": "ambd_100", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Marcus Bell", "email": "marcus.bell@shopgym.com"}], "cc": [], "bcc": [], "subject": "Q3 dashboard update", "body": "Hi Marcus, quick status on the analytics dashboard: the ingestion pipeline is done and the first two widgets are wired up. Still blocked on the auth piece from the platform team, so I'll follow up with them tomorrow and", "snippet": "Hi Marcus, quick status on the analytics dashboard: the ingestion pipeline is done and the first two widgets are wired up. Still blocked on ", "timestamp": "2026-01-23T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_101", "threadId": "ambd_101", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Dmitri Volkov", "email": "dmitri.volkov@gmail.com"}], "cc": [], "bcc": [], "subject": "Radiator noise in unit 4B", "body": "Hi Dmitri, the radiator in the bedroom has been clanging loudly every night this week and it's making it hard to sleep. Could you have someone take a look sometime next week? I'm usually home after", "snippet": "Hi Dmitri, the radiator in the bedroom has been clanging loudly every night this week and it's making it hard to sleep. Could you have someo", "timestamp": "2026-01-23T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_102", "threadId": "ambd_102", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "FitLife Memberships", "email": "cancellations@fitlifegym.com"}], "cc": [], "bcc": [], "subject": "Cancel my membership", "body": "I'd like to cancel my monthly membership effective at the end of this billing cycle. I've barely been able to use it since my schedule changed and I don't want to keep paying for something I'm not. Please let me know if you need", "snippet": "I'd like to cancel my monthly membership effective at the end of this billing cycle. I've barely been able to use it since my schedule chang", "timestamp": "2026-01-23T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_103", "threadId": "ambd_103", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Jenna Cole", "email": "jenna.cole@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: still on for the hike?", "body": "Yes! I checked the forecast and Sunday looks clear, mid-60s. I was thinking we start early to beat the crowds at the trailhead, maybe meet at", "snippet": "Yes! I checked the forecast and Sunday looks clear, mid-60s. I was thinking we start early to beat the crowds at the trailhead, maybe meet a", "timestamp": "2026-01-23T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_104", "threadId": "ambd_104", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Dr. Owen Fields", "email": "ofields@brooklynhealth.org"}], "cc": [], "bcc": [], "subject": "Question about my prescription refill", "body": "Hi Dr. Fields, I'm down to my last few days of the medication and wanted to confirm whether I'm cleared for another refill or if you'd like me to come in first. The pharmacy said they needed authorization before", "snippet": "Hi Dr. Fields, I'm down to my last few days of the medication and wanted to confirm whether I'm cleared for another refill or if you'd like ", "timestamp": "2026-01-22T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_105", "threadId": "ambd_105", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Team Distribution", "email": "team-eng@shopgym.com"}], "cc": [], "bcc": [], "subject": "Notes from today's standup", "body": "Hey all, wrapping up a few things from this morning: the staging deploy is green, and QA signed off on the checkout flow. One thing we didn't get to was the migration plan for the old orders table, which I think we should", "snippet": "Hey all, wrapping up a few things from this morning: the staging deploy is green, and QA signed off on the checkout flow. One thing we didn'", "timestamp": "2026-01-22T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_106", "threadId": "ambd_106", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Leo Anderson", "email": "leo.anderson88@gmail.com"}], "cc": [], "bcc": [], "subject": "Mom's surprise party", "body": "Hey Leo, I started sketching out the plan for Mom's 60th. I'm thinking we book the back room at Rosetta's and keep it to about twenty people. Can you handle the guest list on Dad's side and", "snippet": "Hey Leo, I started sketching out the plan for Mom's 60th. I'm thinking we book the back room at Rosetta's and keep it to about twenty people", "timestamp": "2026-01-22T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_107", "threadId": "ambd_107", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Bright Meadows HOA", "email": "board@brightmeadowshoa.org"}], "cc": [], "bcc": [], "subject": "Follow-up on the parking complaint", "body": "I'm writing again about the delivery trucks blocking the shared driveway in the mornings. It's been three weeks since my first email and nothing has changed, so I'd appreciate an actual timeline on when this will be", "snippet": "I'm writing again about the delivery trucks blocking the shared driveway in the mornings. It's been three weeks since my first email and not", "timestamp": "2026-01-22T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_108", "threadId": "ambd_108", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Sofia Ramirez", "email": "sofia.ramirez@outlook.com"}], "cc": [], "bcc": [], "subject": "Re: recipe you asked about", "body": "Finally writing this down before I forget! For the lemon orzo you need about a cup of orzo, a whole lemon zested and juiced, and a big handful of parmesan. The trick is to toast the orzo first until it's", "snippet": "Finally writing this down before I forget! For the lemon orzo you need about a cup of orzo, a whole lemon zested and juiced, and a big handf", "timestamp": "2026-01-22T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_109", "threadId": "ambd_109", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "CloudNote Billing", "email": "billing@cloudnote.io"}], "cc": [], "bcc": [], "subject": "Downgrade my plan", "body": "I've been on the Pro tier for a year but I really only use the basic features anymore. I'd like to switch to the free plan and make sure I'm not charged for the next cycle. Do I lose my saved notes if I", "snippet": "I've been on the Pro tier for a year but I really only use the basic features anymore. I'd like to switch to the free plan and make sure I'm", "timestamp": "2026-01-22T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_110", "threadId": "ambd_110", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Nathan Brooks", "email": "nathan.brooks@gmail.com"}], "cc": [], "bcc": [], "subject": "Thank you", "body": "Nathan, I just wanted to say how much it meant that you covered for me last week while everything was going on with my family. I don't think I properly thanked you in the moment and I", "snippet": "Nathan, I just wanted to say how much it meant that you covered for me last week while everything was going on with my family. I don't think", "timestamp": "2026-01-21T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_111", "threadId": "ambd_111", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Willowbrook Property Mgmt", "email": "leasing@willowbrookpm.com"}], "cc": [], "bcc": [], "subject": "Notice about not renewing my lease", "body": "I wanted to give you early notice that I won't be renewing my lease when it ends in October. It's been a good three years but I'm relocating for work. Could you let me know what the move-out process looks like and whether", "snippet": "I wanted to give you early notice that I won't be renewing my lease when it ends in October. It's been a good three years but I'm relocating", "timestamp": "2026-01-21T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_112", "threadId": "ambd_112", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Hannah Wills", "email": "hannah.wills@gmail.com"}], "cc": [], "bcc": [], "subject": "Re: how are you holding up?", "body": "Hey Han, sorry it took me a few days to reply, it's been a lot. Honestly I'm doing okay, some days are harder than others but work has been a good distraction. How are things on your end with the new", "snippet": "Hey Han, sorry it took me a few days to reply, it's been a lot. Honestly I'm doing okay, some days are harder than others but work has been ", "timestamp": "2026-01-21T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_113", "threadId": "ambd_113", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "StreamFlix Support", "email": "help@streamflix.com"}], "cc": [], "bcc": [], "subject": "Charged twice this month", "body": "I noticed two identical charges on my statement for the same subscription this month. I've only ever had one account under this email, so I'd like one of them refunded. I can send a screenshot of the statement if", "snippet": "I noticed two identical charges on my statement for the same subscription this month. I've only ever had one account under this email, so I'", "timestamp": "2026-01-21T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_114", "threadId": "ambd_114", "from": {"name": "Alice Anderson", "email": "alice@shopgym.com", "avatar": null}, "to": [{"name": "Professor Alan Reyes", "email": "areyes@citytech.edu"}], "cc": [], "bcc": [], "subject": "Guest lecture invitation", "body": "Dear Professor Reyes, I'm organizing a small speaker series for our team this fall and I'd love to invite you to talk about your work on urban data systems. We're flexible on dates in October, and I'd be happy to", "snippet": "Dear Professor Reyes, I'm organizing a small speaker series for our team this fall and I'd love to invite you to talk about your work on urb", "timestamp": "2026-01-21T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "drafts", "attachments": []});
  emails.push({"id": "ambd_115", "threadId": "ambd_115", "from": {"name": "Con Edison", "email": "no-reply@coned.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your July electricity bill is due August 12", "body": "Your latest statement of $84.60 is now available in your account. Please schedule a payment before the due date to avoid a late fee.", "snippet": "Your latest statement of $84.60 is now available in your account. Please schedule a payment before the due date to avoid a late fee.", "timestamp": "2026-01-21T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-10T12:00:00.000Z"});
  emails.push({"id": "ambd_116", "threadId": "ambd_116", "from": {"name": "Park Slope Dental", "email": "appointments@parkslopedental.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Please confirm your cleaning on August 10", "body": "Hi Alice, we have you booked with Dr. Nguyen at 9:30 AM on Monday, August 10. Reply CONFIRM or call us so we can hold your spot.", "snippet": "Hi Alice, we have you booked with Dr. Nguyen at 9:30 AM on Monday, August 10. Reply CONFIRM or call us so we can hold your spot.", "timestamp": "2026-01-20T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-10T18:00:00.000Z"});
  emails.push({"id": "ambd_117", "threadId": "ambd_117", "from": {"name": "Brooklyn Public Library", "email": "noreply@bklynlibrary.org", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Action needed: renew your library card online", "body": "Your library card expires at the end of the month. Complete the short renewal form to keep borrowing books and using our digital collection.", "snippet": "Your library card expires at the end of the month. Complete the short renewal form to keep borrowing books and using our digital collection.", "timestamp": "2026-01-20T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-11T00:00:00.000Z"});
  emails.push({"id": "ambd_118", "threadId": "ambd_118", "from": {"name": "The New York Times", "email": "subscriptions@nytimes.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Digital subscription renews August 20", "body": "Just a heads-up that your annual All Access plan will renew automatically on August 20 for $89. You can review or change your plan anytime in account settings.", "snippet": "Just a heads-up that your annual All Access plan will renew automatically on August 20 for $89. You can review or change your plan anytime i", "timestamp": "2026-01-20T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-11T06:00:00.000Z"});
  emails.push({"id": "ambd_119", "threadId": "ambd_119", "from": {"name": "Maria Alvarez", "email": "maria.alvarez88@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: brunch sometime this month?", "body": "It feels like ages! I'm free most weekends before Labor Day, so pick a Saturday and I'll come to you. Let me know what works.", "snippet": "It feels like ages! I'm free most weekends before Labor Day, so pick a Saturday and I'll come to you. Let me know what works.", "timestamp": "2026-01-20T08:00:00.000Z", "read": false, "starred": true, "important": false, "labels": [], "category": "primary", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-11T12:00:00.000Z"});
  emails.push({"id": "ambd_120", "threadId": "ambd_120", "from": {"name": "Whole Foods Market", "email": "receipts@wholefoodsmarket.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your receipt from August 1", "body": "Thanks for shopping with us at the Gowanus store. Your order total was $52.18, and your itemized receipt is attached for your records.", "snippet": "Thanks for shopping with us at the Gowanus store. Your order total was $52.18, and your itemized receipt is attached for your records.", "timestamp": "2026-01-20T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-11T18:00:00.000Z"});
  emails.push({"id": "ambd_121", "threadId": "ambd_121", "from": {"name": "Priya Desai", "email": "priya.desai@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You're invited! Please RSVP by August 15", "body": "We'd love to have you at our garden wedding in the Hudson Valley on September 12. Could you let me know if you'll be coming, and whether you're bringing a plus-one?", "snippet": "We'd love to have you at our garden wedding in the Hudson Valley on September 12. Could you let me know if you'll be coming, and whether you", "timestamp": "2026-01-20T00:00:00.000Z", "read": false, "starred": true, "important": true, "labels": [], "category": "primary", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-12T00:00:00.000Z"});
  emails.push({"id": "ambd_122", "threadId": "ambd_122", "from": {"name": "Verizon", "email": "no-reply@verizon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your wireless bill is ready", "body": "Your August statement of $70.99 is now available. If you're on paper billing, your payment is due by August 18.", "snippet": "Your August statement of $70.99 is now available. If you're on paper billing, your payment is due by August 18.", "timestamp": "2026-01-19T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-12T06:00:00.000Z"});
  emails.push({"id": "ambd_123", "threadId": "ambd_123", "from": {"name": "Spotify", "email": "no-reply@spotify.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Premium plan renews soon", "body": "Your Individual Premium plan will renew on August 22 for $11.99. No action is needed unless you'd like to change or cancel your subscription.", "snippet": "Your Individual Premium plan will renew on August 22 for $11.99. No action is needed unless you'd like to change or cancel your subscription", "timestamp": "2026-01-19T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-12T12:00:00.000Z"});
  emails.push({"id": "ambd_124", "threadId": "ambd_124", "from": {"name": "ShopGym Benefits", "email": "benefits@shopgym.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Open enrollment: complete your benefits form by August 18", "body": "This is a reminder to finalize your health and dental elections for the coming year. The enrollment form takes about ten minutes and must be submitted before the window closes.", "snippet": "This is a reminder to finalize your health and dental elections for the coming year. The enrollment form takes about ten minutes and must be", "timestamp": "2026-01-19T12:00:00.000Z", "read": false, "starred": false, "important": true, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-12T18:00:00.000Z"});
  emails.push({"id": "ambd_125", "threadId": "ambd_125", "from": {"name": "Sterling Property Management", "email": "leasing@sterlingpm.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Lease renewal — please review and sign", "body": "Your current lease ends September 30, and we've prepared a renewal offer for your apartment. Please review the attached terms and return a signed copy within two weeks to lock in your rate.", "snippet": "Your current lease ends September 30, and we've prepared a renewal offer for your apartment. Please review the attached terms and return a s", "timestamp": "2026-01-19T08:00:00.000Z", "read": false, "starred": true, "important": true, "labels": [], "category": "primary", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-13T00:00:00.000Z"});
  emails.push({"id": "ambd_126", "threadId": "ambd_126", "from": {"name": "NYU Langone Health", "email": "no-reply@nyulangone.org", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Time to schedule your annual physical", "body": "Our records show it's been about a year since your last checkup with Dr. Halloran. Log in to the patient portal or call the office to book a convenient time.", "snippet": "Our records show it's been about a year since your last checkup with Dr. Halloran. Log in to the patient portal or call the office to book a", "timestamp": "2026-01-19T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-13T06:00:00.000Z"});
  emails.push({"id": "ambd_127", "threadId": "ambd_127", "from": {"name": "Amazon", "email": "auto-confirm@amazon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your return window closes August 9", "body": "The stand mixer from your recent order is still eligible for return until August 9. If you'd like to send it back, start the return from Your Orders before then.", "snippet": "The stand mixer from your recent order is still eligible for return until August 9. If you'd like to send it back, start the return from You", "timestamp": "2026-01-19T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-13T12:00:00.000Z"});
  emails.push({"id": "ambd_128", "threadId": "ambd_128", "from": {"name": "Costco Member Services", "email": "memberservices@costco.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your membership expires this month", "body": "Your Gold Star membership is set to expire on August 31. Renew online or at any warehouse to keep your benefits active without interruption.", "snippet": "Your Gold Star membership is set to expire on August 31. Renew online or at any warehouse to keep your benefits active without interruption.", "timestamp": "2026-01-18T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-13T18:00:00.000Z"});
  emails.push({"id": "ambd_129", "threadId": "ambd_129", "from": {"name": "Kings County Clerk", "email": "no-reply@nycourts.gov", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Complete your juror qualification questionnaire", "body": "You have been selected to complete a juror qualification questionnaire. Please fill out and submit the form within ten days using the juror ID printed on your notice.", "snippet": "You have been selected to complete a juror qualification questionnaire. Please fill out and submit the form within ten days using the juror ", "timestamp": "2026-01-18T16:00:00.000Z", "read": false, "starred": false, "important": true, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-14T00:00:00.000Z"});
  emails.push({"id": "ambd_130", "threadId": "ambd_130", "from": {"name": "Blink Fitness", "email": "memberships@blinkfitness.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your annual membership renews August 25", "body": "Your Green membership will renew for another year on August 25 at $16.99 per month. Reply or visit your club's front desk if you'd like to make any changes.", "snippet": "Your Green membership will renew for another year on August 25 at $16.99 per month. Reply or visit your club's front desk if you'd like to m", "timestamp": "2026-01-18T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-14T06:00:00.000Z"});
  emails.push({"id": "ambd_131", "threadId": "ambd_131", "from": {"name": "Daniel Okafor", "email": "daniel.okafor@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: your thoughts on the venue?", "body": "The loft space I mentioned is holding a date for us until Friday, but they need a decision soon. What did you think of the photos I sent over?", "snippet": "The loft space I mentioned is holding a date for us until Friday, but they need a decision soon. What did you think of the photos I sent ove", "timestamp": "2026-01-18T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-14T12:00:00.000Z"});
  emails.push({"id": "ambd_132", "threadId": "ambd_132", "from": {"name": "charity: water", "email": "donate@charitywater.org", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your donation receipt", "body": "Thank you for your generous gift of $40 toward clean water projects. This email serves as your official receipt for tax purposes; please keep it for your records.", "snippet": "Thank you for your generous gift of $40 toward clean water projects. This email serves as your official receipt for tax purposes; please kee", "timestamp": "2026-01-18T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-14T18:00:00.000Z"});
  emails.push({"id": "ambd_133", "threadId": "ambd_133", "from": {"name": "Sabrina Chen", "email": "sabrina.chen@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Potluck at my place — can you make it?", "body": "I'm hosting a late-summer potluck on August 23 and would love for you to come. Just let me know if you're in and what dish you might bring.", "snippet": "I'm hosting a late-summer potluck on August 23 and would love for you to come. Just let me know if you're in and what dish you might bring.", "timestamp": "2026-01-18T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-15T00:00:00.000Z"});
  emails.push({"id": "ambd_134", "threadId": "ambd_134", "from": {"name": "Cohen's Fashion Optical", "email": "appointments@cohensoptical.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Confirm your eye exam on August 14", "body": "Hi Alice, you're scheduled for an eye exam at 4:00 PM on Thursday, August 14. Please confirm so we can prepare your file, or call us to reschedule.", "snippet": "Hi Alice, you're scheduled for an eye exam at 4:00 PM on Thursday, August 14. Please confirm so we can prepare your file, or call us to resc", "timestamp": "2026-01-17T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "snoozed", "attachments": [], "snoozedUntil": "2026-03-15T06:00:00.000Z"});
  emails.push({"id": "ambd_135", "threadId": "ambd_135", "from": {"name": "Rewards Center", "email": "claim@rewards-winner-notify.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "CONGRATULATIONS! You've won a $500 Amazon Gift Card", "body": "Alice, your email was randomly selected as our lucky winner of a $500 Amazon gift card! Complete a short 3-question survey to claim your prize before it expires tonight.", "snippet": "Alice, your email was randomly selected as our lucky winner of a $500 Amazon gift card! Complete a short 3-question survey to claim your pri", "timestamp": "2026-01-17T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_136", "threadId": "ambd_136", "from": {"name": "KetoSlim Pro", "email": "offers@ketoslim-miracle.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Melt 27 lbs in 3 weeks WITHOUT dieting", "body": "Doctors are furious about this one weird trick that torches belly fat overnight. Try our clinically-inspired gummies risk-free and watch the pounds disappear.", "snippet": "Doctors are furious about this one weird trick that torches belly fat overnight. Try our clinically-inspired gummies risk-free and watch the", "timestamp": "2026-01-17T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_137", "threadId": "ambd_137", "from": {"name": "CryptoWealth Alerts", "email": "signals@bitwealth-daily.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Turn $250 into $18,000 with this coin", "body": "Our AI trading bot spotted the next 100x altcoin before it explodes. Early members are already retiring — don't miss the window closing this Friday.", "snippet": "Our AI trading bot spotted the next 100x altcoin before it explodes. Early members are already retiring — don't miss the window closing this", "timestamp": "2026-01-17T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_138", "threadId": "ambd_138", "from": {"name": "Account Security Team", "email": "verify@account-secure-update.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your account needs verification within 24 hours", "body": "We detected unusual sign-in activity and your account has been temporarily limited. Reply with your details to restore full access before your account is suspended.", "snippet": "We detected unusual sign-in activity and your account has been temporarily limited. Reply with your details to restore full access before yo", "timestamp": "2026-01-17T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_139", "threadId": "ambd_139", "from": {"name": "FedEx Delivery Notice", "email": "parcel@fedx-delivery-fee.org", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your package is on hold - $1.99 fee due", "body": "Your parcel could not be delivered due to an unpaid customs fee of $1.99. Settle the outstanding balance now to avoid your package being returned to sender.", "snippet": "Your parcel could not be delivered due to an unpaid customs fee of $1.99. Settle the outstanding balance now to avoid your package being ret", "timestamp": "2026-01-17T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_140", "threadId": "ambd_140", "from": {"name": "Top SEO Experts", "email": "growth@rank-page1-seo.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Get your website on Google page 1 - guaranteed", "body": "Your competitors are outranking you and stealing your customers every single day. Our proven SEO package guarantees first-page rankings in just 30 days.", "snippet": "Your competitors are outranking you and stealing your customers every single day. Our proven SEO package guarantees first-page rankings in j", "timestamp": "2026-01-16T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_141", "threadId": "ambd_141", "from": {"name": "Auto Warranty Dept", "email": "renewals@extended-warranty-now.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "FINAL NOTICE: Your vehicle warranty is expiring", "body": "This is your final courtesy notice that the factory warranty on your vehicle is about to expire. Act now to extend your coverage before you're left paying costly repairs.", "snippet": "This is your final courtesy notice that the factory warranty on your vehicle is about to expire. Act now to extend your coverage before you'", "timestamp": "2026-01-16T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_142", "threadId": "ambd_142", "from": {"name": "Prince Adewale", "email": "contact@intl-fund-transfer.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Urgent business proposal - $15 million partnership", "body": "Dear friend, I am seeking a trustworthy partner to help transfer an inheritance of $15 million abroad. You will receive 30% for your kind assistance in this confidential matter.", "snippet": "Dear friend, I am seeking a trustworthy partner to help transfer an inheritance of $15 million abroad. You will receive 30% for your kind as", "timestamp": "2026-01-16T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_143", "threadId": "ambd_143", "from": {"name": "iPhone Giveaway", "email": "winner@free-iphone-16-event.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You're eligible for a FREE iPhone 16 Pro", "body": "Great news! You have been pre-selected to receive a brand new iPhone 16 Pro at no cost. Just cover the $4.95 shipping and it ships to your door tomorrow.", "snippet": "Great news! You have been pre-selected to receive a brand new iPhone 16 Pro at no cost. Just cover the $4.95 shipping and it ships to your d", "timestamp": "2026-01-16T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_144", "threadId": "ambd_144", "from": {"name": "Male Vitality Labs", "email": "support@vitality-boost-rx.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Boost your energy and stamina naturally tonight", "body": "Thousands of men are reclaiming their confidence with our all-natural performance supplement. Order today and get two bottles absolutely free with discreet shipping.", "snippet": "Thousands of men are reclaiming their confidence with our all-natural performance supplement. Order today and get two bottles absolutely fre", "timestamp": "2026-01-16T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_145", "threadId": "ambd_145", "from": {"name": "Publishers Prize Bureau", "email": "notify@mega-sweepstakes-draw.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You may already be a $1,000,000 winner", "body": "Your name has been entered into our final drawing for a one million dollar grand prize. Confirm your entry today to keep your winning number active for the big draw.", "snippet": "Your name has been entered into our final drawing for a one million dollar grand prize. Confirm your entry today to keep your winning number", "timestamp": "2026-01-16T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_146", "threadId": "ambd_146", "from": {"name": "WFH Income Coach", "email": "jobs@earn-from-home-daily.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Make $3,500/week working from home online", "body": "Housewives and retirees are earning thousands from home with just a laptop and 2 hours a day. No experience needed — start earning your first payout this week.", "snippet": "Housewives and retirees are earning thousands from home with just a laptop and 2 hours a day. No experience needed — start earning your firs", "timestamp": "2026-01-15T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_147", "threadId": "ambd_147", "from": {"name": "Debt Relief Solutions", "email": "help@erase-your-debt-fast.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Wipe out up to 80% of your debt legally", "body": "You may qualify for a special government-backed program to eliminate most of your credit card debt. Call now to see how much you could save before enrollment closes.", "snippet": "You may qualify for a special government-backed program to eliminate most of your credit card debt. Call now to see how much you could save ", "timestamp": "2026-01-15T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_148", "threadId": "ambd_148", "from": {"name": "Solar Savings USA", "email": "quotes@free-solar-panels-gov.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Homeowners: get solar panels for $0 down", "body": "A new program lets qualified homeowners install solar panels with zero upfront cost and slash their electric bill to nearly nothing. Check if your zip code qualifies today.", "snippet": "A new program lets qualified homeowners install solar panels with zero upfront cost and slash their electric bill to nearly nothing. Check i", "timestamp": "2026-01-15T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_149", "threadId": "ambd_149", "from": {"name": "Pharmacy Discounts", "email": "deals@canadian-meds-online.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Save 90% on your prescriptions - no Rx needed", "body": "Skip the expensive pharmacy and order your medications online at up to 90% off. Fast discreet worldwide shipping with no prescription required for most items.", "snippet": "Skip the expensive pharmacy and order your medications online at up to 90% off. Fast discreet worldwide shipping with no prescription requir", "timestamp": "2026-01-15T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_150", "threadId": "ambd_150", "from": {"name": "Lucky Casino VIP", "email": "vip@spin-jackpot-royale.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your 200 FREE spins are waiting - claim now", "body": "You've been awarded 200 free spins plus a $1,000 welcome bonus at our online casino. No deposit needed to start — your jackpot could be one spin away.", "snippet": "You've been awarded 200 free spins plus a $1,000 welcome bonus at our online casino. No deposit needed to start — your jackpot could be one ", "timestamp": "2026-01-15T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_151", "threadId": "ambd_151", "from": {"name": "Timeshare Getaways", "email": "vacations@dream-resort-deals.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You've won a 5-night Cancun vacation!", "body": "Congratulations, you have been selected for a complimentary 5-night stay at a luxury Cancun resort. Simply attend a brief 90-minute presentation to claim your free trip.", "snippet": "Congratulations, you have been selected for a complimentary 5-night stay at a luxury Cancun resort. Simply attend a brief 90-minute presenta", "timestamp": "2026-01-15T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_152", "threadId": "ambd_152", "from": {"name": "Student Loan Forgiveness", "email": "apply@loan-forgiveness-center.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your student loans may be forgiven - apply today", "body": "New federal guidelines mean your student loans could be completely forgiven this year. Our specialists will file everything for you — spots are limited so apply before the deadline.", "snippet": "New federal guidelines mean your student loans could be completely forgiven this year. Our specialists will file everything for you — spots ", "timestamp": "2026-01-14T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_153", "threadId": "ambd_153", "from": {"name": "Walmart Shopper Panel", "email": "survey@shopper-reward-panel.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Get a $100 Walmart gift card for your opinion", "body": "As a valued shopper you've been chosen to receive a $100 Walmart gift card. Just complete our quick shopping survey and cover a small $2 processing fee to receive it.", "snippet": "As a valued shopper you've been chosen to receive a $100 Walmart gift card. Just complete our quick shopping survey and cover a small $2 pro", "timestamp": "2026-01-14T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_154", "threadId": "ambd_154", "from": {"name": "Antivirus Alert", "email": "alert@pc-virus-detected-scan.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "WARNING: 5 viruses detected on your device", "body": "Our system has flagged 5 serious threats actively harming your computer right now. Renew your protection immediately before your files and passwords are stolen.", "snippet": "Our system has flagged 5 serious threats actively harming your computer right now. Renew your protection immediately before your files and p", "timestamp": "2026-01-14T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_155", "threadId": "ambd_155", "from": {"name": "Hot Singles Nearby", "email": "matches@meet-local-tonight.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "3 people near you want to chat right now", "body": "You have 3 new messages from attractive singles in your area waiting to connect. Sign up free tonight and see who's been checking out your profile nearby.", "snippet": "You have 3 new messages from attractive singles in your area waiting to connect. Sign up free tonight and see who's been checking out your p", "timestamp": "2026-01-14T08:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_156", "threadId": "ambd_156", "from": {"name": "Tax Relief Hotline", "email": "resolve@irs-settlement-experts.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Settle your IRS back taxes for pennies on the dollar", "body": "You may qualify to reduce your outstanding tax debt by thousands through a fresh-start settlement program. Call our licensed agents now before penalties keep piling up.", "snippet": "You may qualify to reduce your outstanding tax debt by thousands through a fresh-start settlement program. Call our licensed agents now befo", "timestamp": "2026-01-14T04:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_157", "threadId": "ambd_157", "from": {"name": "Wrinkle Miracle", "email": "beauty@age-reverse-cream.biz", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Look 20 years younger in just 14 days", "body": "Dermatologists are stunned by this breakthrough cream that erases wrinkles and fine lines fast. Claim your free trial jar today and reveal younger-looking skin by next week.", "snippet": "Dermatologists are stunned by this breakthrough cream that erases wrinkles and fine lines fast. Claim your free trial jar today and reveal y", "timestamp": "2026-01-14T00:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_158", "threadId": "ambd_158", "from": {"name": "Costco Rewards", "email": "loyalty@member-reward-bonus.info", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Costco loyalty bonus is ready to claim", "body": "Thank you for being a loyal member — a $75 bonus reward has been reserved in your name. Verify your membership below within 48 hours to release your bonus before it expires.", "snippet": "Thank you for being a loyal member — a $75 bonus reward has been reserved in your name. Verify your membership below within 48 hours to rele", "timestamp": "2026-01-13T20:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_159", "threadId": "ambd_159", "from": {"name": "Payday Fast Cash", "email": "loans@instant-cash-approval.co", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Need cash now? $5,000 approved in minutes", "body": "Get up to $5,000 deposited into your account today with no credit check and instant approval. Bad credit is welcome — apply in 60 seconds and get funded fast.", "snippet": "Get up to $5,000 deposited into your account today with no credit check and instant approval. Bad credit is welcome — apply in 60 seconds an", "timestamp": "2026-01-13T16:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_160", "threadId": "ambd_160", "from": {"name": "Energy Bill Savers", "email": "savings@cut-electric-bill-device.net", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "This $39 gadget cuts your electric bill by 90%", "body": "Power companies don't want you to know about this tiny device that slashes your energy usage overnight. Thousands of households are already saving hundreds each month.", "snippet": "Power companies don't want you to know about this tiny device that slashes your energy usage overnight. Thousands of households are already ", "timestamp": "2026-01-13T12:00:00.000Z", "read": false, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "spam", "attachments": []});
  emails.push({"id": "ambd_161", "threadId": "ambd_161", "from": {"name": "Chipotle Rewards", "email": "rewards@chipotle.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Last chance: Free guac ends tonight", "body": "Your free guacamole reward expires at midnight. Add it to any entree order in the app before the clock runs out.", "snippet": "Your free guacamole reward expires at midnight. Add it to any entree order in the app before the clock runs out.", "timestamp": "2026-01-13T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_162", "threadId": "ambd_162", "from": {"name": "The Skimm", "email": "newsletter@theskimm.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your daily Skimm for June 14", "body": "Here's everything you need to make sense of the morning headlines. We broke down the three stories everyone will be talking about today.", "snippet": "Here's everything you need to make sense of the morning headlines. We broke down the three stories everyone will be talking about today.", "timestamp": "2026-01-13T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_163", "threadId": "ambd_163", "from": {"name": "Old Navy", "email": "news@oldnavy.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "50% off ended — but we saved you a peek", "body": "Our summer clearance blowout wrapped up over the weekend. Thanks for browsing, and keep an eye out for the next big event.", "snippet": "Our summer clearance blowout wrapped up over the weekend. Thanks for browsing, and keep an eye out for the next big event.", "timestamp": "2026-01-13T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_164", "threadId": "ambd_164", "from": {"name": "Duolingo", "email": "hello@duolingo.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "You've kept your streak — nice work!", "body": "Your 7-day streak is safe thanks to today's lesson. Keep it going and you'll hit two weeks before you know it.", "snippet": "Your 7-day streak is safe thanks to today's lesson. Keep it going and you'll hit two weeks before you know it.", "timestamp": "2026-01-12T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_165", "threadId": "ambd_165", "from": {"name": "Grubhub", "email": "orders@grubhub.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your order from Nonna's Kitchen was delivered", "body": "Your dinner arrived at 7:42 PM. We hope everything was hot and delicious — rate your driver when you get a chance.", "snippet": "Your dinner arrived at 7:42 PM. We hope everything was hot and delicious — rate your driver when you get a chance.", "timestamp": "2026-01-12T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_166", "threadId": "ambd_166", "from": {"name": "Sephora", "email": "beauty@sephora.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Spring Savings Event is over", "body": "Thanks for shopping our Spring Savings Event. Your Beauty Insider points have been updated to reflect any recent purchases.", "snippet": "Thanks for shopping our Spring Savings Event. Your Beauty Insider points have been updated to reflect any recent purchases.", "timestamp": "2026-01-12T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_167", "threadId": "ambd_167", "from": {"name": "Eventbrite", "email": "noreply@eventbrite.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Canceled: Brooklyn Rooftop Yoga", "body": "Unfortunately the organizer has canceled Brooklyn Rooftop Yoga on Saturday. Your full refund will appear within five business days.", "snippet": "Unfortunately the organizer has canceled Brooklyn Rooftop Yoga on Saturday. Your full refund will appear within five business days.", "timestamp": "2026-01-12T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_168", "threadId": "ambd_168", "from": {"name": "Amazon.com", "email": "receipts@amazon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Amazon.com order confirmation", "body": "Thanks for your order of the stainless steel water bottle. This is a duplicate confirmation for the purchase you placed earlier today.", "snippet": "Thanks for your order of the stainless steel water bottle. This is a duplicate confirmation for the purchase you placed earlier today.", "timestamp": "2026-01-12T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_169", "threadId": "ambd_169", "from": {"name": "Spotify", "email": "no-reply@spotify.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Discover Weekly is waiting", "body": "We refreshed your Discover Weekly with 30 new tracks based on what you've been listening to. Give it a spin whenever you're ready.", "snippet": "We refreshed your Discover Weekly with 30 new tracks based on what you've been listening to. Give it a spin whenever you're ready.", "timestamp": "2026-01-12T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_170", "threadId": "ambd_170", "from": {"name": "Warby Parker", "email": "hello@warbyparker.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Home Try-On is ending soon", "body": "Just a reminder that your five-pair Home Try-On window closes this Friday. Pop your frames in the prepaid box whenever you're done.", "snippet": "Just a reminder that your five-pair Home Try-On window closes this Friday. Pop your frames in the prepaid box whenever you're done.", "timestamp": "2026-01-11T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_171", "threadId": "ambd_171", "from": {"name": "The New York Times", "email": "nytdirect@nytimes.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "The Morning: What to watch this week", "body": "Today's edition looks at the stories shaping the week ahead. Our editors picked a few reads worth your coffee break.", "snippet": "Today's edition looks at the stories shaping the week ahead. Our editors picked a few reads worth your coffee break.", "timestamp": "2026-01-11T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_172", "threadId": "ambd_172", "from": {"name": "FedEx", "email": "tracking@fedex.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Delivery exception for your package", "body": "We hit a brief delay with your shipment on Tuesday, but it's now back on track. No action is needed on your end.", "snippet": "We hit a brief delay with your shipment on Tuesday, but it's now back on track. No action is needed on your end.", "timestamp": "2026-01-11T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_173", "threadId": "ambd_173", "from": {"name": "Bath & Body Works", "email": "email@bathandbodyworks.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Candle Day pricing has ended", "body": "Our biggest candle event of the season has wrapped up. Thanks for stocking up — your favorites will be back before you know it.", "snippet": "Our biggest candle event of the season has wrapped up. Thanks for stocking up — your favorites will be back before you know it.", "timestamp": "2026-01-11T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_174", "threadId": "ambd_174", "from": {"name": "Blue Apron", "email": "hello@blueapron.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Reminder: skip week deadline passed", "body": "The deadline to skip your upcoming delivery has passed, so your box is on its way. Enjoy this week's seasonal recipes.", "snippet": "The deadline to skip your upcoming delivery has passed, so your box is on its way. Enjoy this week's seasonal recipes.", "timestamp": "2026-01-11T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_175", "threadId": "ambd_175", "from": {"name": "Groupon", "email": "deals@groupon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your saved deal has expired", "body": "The spa package you saved is no longer available at that price. Browse similar local deals whenever you're ready for a treat.", "snippet": "The spa package you saved is no longer available at that price. Browse similar local deals whenever you're ready for a treat.", "timestamp": "2026-01-11T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_176", "threadId": "ambd_176", "from": {"name": "Uber Receipts", "email": "noreply@uber.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your Thursday evening trip receipt", "body": "Thanks for riding with Uber. Your trip from downtown to Park Slope totaled $14.30, tip included. Rate your driver anytime.", "snippet": "Thanks for riding with Uber. Your trip from downtown to Park Slope totaled $14.30, tip included. Rate your driver anytime.", "timestamp": "2026-01-10T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_177", "threadId": "ambd_177", "from": {"name": "REI Co-op", "email": "members@rei.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Anniversary Sale wraps up Monday", "body": "Our member Anniversary Sale is winding down this weekend. Thanks for being a co-op member — your dividend is ready to spend.", "snippet": "Our member Anniversary Sale is winding down this weekend. Thanks for being a co-op member — your dividend is ready to spend.", "timestamp": "2026-01-10T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_178", "threadId": "ambd_178", "from": {"name": "Meetup", "email": "info@meetup.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Brooklyn Book Club meeting rescheduled", "body": "Heads up — this month's Brooklyn Book Club has moved to next Thursday at the same cafe. Hope the new date works for you.", "snippet": "Heads up — this month's Brooklyn Book Club has moved to next Thursday at the same cafe. Hope the new date works for you.", "timestamp": "2026-01-10T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_179", "threadId": "ambd_179", "from": {"name": "Michaels Stores", "email": "news@michaels.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Weekend coupon expired Sunday", "body": "Your 40% off one item coupon expired at the end of the weekend. Don't worry — a fresh batch of savings is always around the corner.", "snippet": "Your 40% off one item coupon expired at the end of the weekend. Don't worry — a fresh batch of savings is always around the corner.", "timestamp": "2026-01-10T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "promotions", "folder": "trash", "attachments": []});
  emails.push({"id": "ambd_180", "threadId": "ambd_180", "from": {"name": "Delta Air Lines", "email": "confirmation@delta.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your trip to Portland is confirmed — DL2287", "body": "Thanks for booking with Delta. Your round-trip from New York (JFK) to Portland (PDX) departs March 14 at 8:05 AM, returning March 19. Your confirmation code is HXK4RQ.", "snippet": "Thanks for booking with Delta. Your round-trip from New York (JFK) to Portland (PDX) departs March 14 at 8:05 AM, returning March 19. Your c", "timestamp": "2026-01-10T04:00:00.000Z", "read": true, "starred": true, "important": true, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_181", "threadId": "ambd_181", "from": {"name": "Airbnb", "email": "automated@airbnb.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Reservation confirmed: Cozy loft in Pearl District", "body": "Your stay in Portland is booked for March 14–19. Your host Marcus will send check-in instructions the day before arrival. Total paid: $612.00.", "snippet": "Your stay in Portland is booked for March 14–19. Your host Marcus will send check-in instructions the day before arrival. Total paid: $612.0", "timestamp": "2026-01-10T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_182", "threadId": "ambd_182", "from": {"name": "Amazon.com", "email": "auto-confirm@amazon.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your order of the Anker charging station has shipped", "body": "Your order #112-4498210-7735402 shipped and should arrive Tuesday. You can track the package from Your Orders. Keep this email for warranty purposes.", "snippet": "Your order #112-4498210-7735402 shipped and should arrive Tuesday. You can track the package from Your Orders. Keep this email for warranty ", "timestamp": "2026-01-09T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_183", "threadId": "ambd_183", "from": {"name": "KitchenAid Support", "email": "warranty@kitchenaid.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Warranty registration complete — Artisan Stand Mixer", "body": "Your KitchenAid Artisan Series mixer is now registered for its 1-year limited warranty. Keep your purchase receipt in case service is ever needed. Registration ID: KA-88301744.", "snippet": "Your KitchenAid Artisan Series mixer is now registered for its 1-year limited warranty. Keep your purchase receipt in case service is ever n", "timestamp": "2026-01-09T16:00:00.000Z", "read": true, "starred": true, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_184", "threadId": "ambd_184", "from": {"name": "TurboTax", "email": "noreply@intuit.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your 2024 federal return was accepted", "body": "The IRS accepted your 2024 federal tax return on April 3. A PDF copy is stored in your TurboTax account for your records. Please retain a copy for at least three years.", "snippet": "The IRS accepted your 2024 federal tax return on April 3. A PDF copy is stored in your TurboTax account for your records. Please retain a co", "timestamp": "2026-01-09T12:00:00.000Z", "read": true, "starred": false, "important": true, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_185", "threadId": "ambd_185", "from": {"name": "Stellar Property Management", "email": "leasing@stellarpm.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Signed lease copy — 214 Wythe Ave, Apt 3B", "body": "Attached is the fully executed copy of your lease renewal for the term beginning June 1. Please keep this for your records. Reach out if you have any questions about the terms.", "snippet": "Attached is the fully executed copy of your lease renewal for the term beginning June 1. Please keep this for your records. Reach out if you", "timestamp": "2026-01-09T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_186", "threadId": "ambd_186", "from": {"name": "Priya Raman", "email": "priya.raman@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Final photos from the cabin weekend", "body": "Just uploaded everything to the shared album, all 240 shots. The sunrise ones from Saturday came out even better than I remembered. Thanks again for organizing the whole trip!", "snippet": "Just uploaded everything to the shared album, all 240 shots. The sunrise ones from Saturday came out even better than I remembered. Thanks a", "timestamp": "2026-01-09T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_187", "threadId": "ambd_187", "from": {"name": "Geico", "email": "service@geico.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your renters insurance policy documents", "body": "Your renters policy has renewed for another 12-month term. Your declarations page and coverage summary are attached for your records. Policy number: 4471-889-02.", "snippet": "Your renters policy has renewed for another 12-month term. Your declarations page and coverage summary are attached for your records. Policy", "timestamp": "2026-01-09T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_188", "threadId": "ambd_188", "from": {"name": "Marcus Feldman", "email": "marcus.feldman@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Q1 volunteer schedule — all wrapped up", "body": "Thanks for covering the Thursday shifts this quarter, the pantry team really appreciated it. I've closed out the sign-up sheet for now. Let's regroup before the spring drive.", "snippet": "Thanks for covering the Thursday shifts this quarter, the pantry team really appreciated it. I've closed out the sign-up sheet for now. Let'", "timestamp": "2026-01-08T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_189", "threadId": "ambd_189", "from": {"name": "Apple", "email": "no_reply@email.apple.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your receipt from Apple — AirPods Pro", "body": "Thank you for your purchase. Your order for AirPods Pro (2nd generation) totaling $249.00 is complete. Keep this receipt for warranty and returns within 14 days.", "snippet": "Thank you for your purchase. Your order for AirPods Pro (2nd generation) totaling $249.00 is complete. Keep this receipt for warranty and re", "timestamp": "2026-01-08T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_190", "threadId": "ambd_190", "from": {"name": "United Airlines", "email": "receipts@united.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "eTicket itinerary — Newark to Austin, UA1102", "body": "Here is your itinerary for the December trip. Depart Newark (EWR) Dec 22 at 6:40 PM, return from Austin (AUS) Dec 27. Confirmation: LMP9TE. Please arrive two hours before departure.", "snippet": "Here is your itinerary for the December trip. Depart Newark (EWR) Dec 22 at 6:40 PM, return from Austin (AUS) Dec 27. Confirmation: LMP9TE. ", "timestamp": "2026-01-08T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_191", "threadId": "ambd_191", "from": {"name": "Dr. Nguyen's Office", "email": "frontdesk@brooklynfamilydental.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Receipt for your dental cleaning visit", "body": "Thank you for visiting us on February 9. Your visit is fully paid, and your next cleaning is due in six months. A copy of your receipt is attached for your records.", "snippet": "Thank you for visiting us on February 9. Your visit is fully paid, and your next cleaning is due in six months. A copy of your receipt is at", "timestamp": "2026-01-08T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_192", "threadId": "ambd_192", "from": {"name": "Wirecutter Reads", "email": "newsletter@wirecutter.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "The standing desk guide you saved", "body": "You asked us to save this one for later. Our updated pick for best standing desk under $500 is still the Fully Jarvis, with the Uplift a close runner-up. Full breakdown inside.", "snippet": "You asked us to save this one for later. Our updated pick for best standing desk under $500 is still the Fully Jarvis, with the Uplift a clo", "timestamp": "2026-01-08T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_193", "threadId": "ambd_193", "from": {"name": "Eventbrite", "email": "orders@eventbrite.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your tickets: Brooklyn Book Festival", "body": "Your two general admission tickets are confirmed for September 21. Present the QR code at the entrance, no printout needed. Order #7729104. We hope you enjoy the festival.", "snippet": "Your two general admission tickets are confirmed for September 21. Present the QR code at the entrance, no printout needed. Order #7729104. ", "timestamp": "2026-01-08T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_194", "threadId": "ambd_194", "from": {"name": "Chase", "email": "no.reply.alerts@chase.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your January statement is ready", "body": "Your monthly account statement is now available to view online. There is nothing you need to do; this notice is for your records. Log in anytime to download a PDF copy.", "snippet": "Your monthly account statement is now available to view online. There is nothing you need to do; this notice is for your records. Log in any", "timestamp": "2026-01-07T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_195", "threadId": "ambd_195", "from": {"name": "Diego Alvarez", "email": "diego.alvarez88@gmail.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Website launch — we did it!", "body": "Just flipped the site live at midnight and everything is holding steady. Couldn't have shipped the redesign without your copy edits. Closing out this thread, drinks on me next week.", "snippet": "Just flipped the site live at midnight and everything is holding steady. Couldn't have shipped the redesign without your copy edits. Closing", "timestamp": "2026-01-07T16:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_196", "threadId": "ambd_196", "from": {"name": "REI Co-op", "email": "orders@rei.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Order confirmation — Osprey daypack", "body": "Thanks for your order. Your Osprey Talon 22 daypack in Coastal Blue is on its way, with an estimated delivery of Friday. Keep this email for returns within one year, no questions asked.", "snippet": "Thanks for your order. Your Osprey Talon 22 daypack in Coastal Blue is on its way, with an estimated delivery of Friday. Keep this email for", "timestamp": "2026-01-07T12:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_197", "threadId": "ambd_197", "from": {"name": "Coursera", "email": "no-reply@coursera.org", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Congratulations on completing Data Analytics", "body": "You've finished the Google Data Analytics Certificate. Your completion certificate is available to download and share. We're proud of the work you put in over the last six months.", "snippet": "You've finished the Google Data Analytics Certificate. Your completion certificate is available to download and share. We're proud of the wo", "timestamp": "2026-01-07T08:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_198", "threadId": "ambd_198", "from": {"name": "Con Edison", "email": "noreply@coned.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Payment received — thank you", "body": "We received your payment of $84.32 for your November electricity bill. No further action is needed. A receipt has been saved to your online account for your records.", "snippet": "We received your payment of $84.32 for your November electricity bill. No further action is needed. A receipt has been saved to your online ", "timestamp": "2026-01-07T04:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_199", "threadId": "ambd_199", "from": {"name": "Hannah Cole", "email": "hannah.cole@outlook.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Re: Thank you note wording — finalized", "body": "That last version is perfect, I sent them all out this morning. Grandma already called to say hers made her cry. Thanks for helping me get the tone just right on these.", "snippet": "That last version is perfect, I sent them all out this morning. Grandma already called to say hers made her cry. Thanks for helping me get t", "timestamp": "2026-01-07T00:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "primary", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_200", "threadId": "ambd_200", "from": {"name": "Booking.com", "email": "confirmation@booking.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your stay at Hotel Vermont is confirmed", "body": "Your reservation in Burlington for October 11–13 is all set. Check-in is from 3 PM and breakfast is included. Confirmation number 4482119. We wish you a pleasant stay.", "snippet": "Your reservation in Burlington for October 11–13 is all set. Check-in is from 3 PM and breakfast is included. Confirmation number 4482119. W", "timestamp": "2026-01-06T20:00:00.000Z", "read": true, "starred": false, "important": false, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});
  emails.push({"id": "ambd_201", "threadId": "ambd_201", "from": {"name": "H&R Block", "email": "noreply@hrblock.com", "avatar": null}, "to": [{"name": "Alice Anderson", "email": "alice@shopgym.com"}], "cc": [], "bcc": [], "subject": "Your 2023 tax documents archive", "body": "As requested, here is the archived copy of your 2023 return and supporting W-2 and 1099 forms. Please store these securely; you may need them for future filings or loan applications.", "snippet": "As requested, here is the archived copy of your 2023 return and supporting W-2 and 1099 forms. Please store these securely; you may need the", "timestamp": "2026-01-06T16:00:00.000Z", "read": true, "starred": false, "important": true, "labels": [], "category": "updates", "folder": "all-mail", "attachments": []});

  return emails;
};

export const DEFAULT_SETTINGS = {
  density: 'default',
  undoSend: 10,
  signature: '--\nAlice Anderson\nalice@shopgym.com',
  categoryTabs: { primary: true, social: true, promotions: true, updates: false, forums: false },
  replyBehavior: 'Reply',
  language: 'English (US)',
  sysLabelShown: {},
  userLabelShown: {},
};

function createDefaultData() {
  return {
    user: CURRENT_USER,
    emails: generateEmails(),
    labels: LABELS,
    drafts: [],
    settings: { ...DEFAULT_SETTINGS },
  };
}

export const INITIAL_STATE = createDefaultData();

// Custom state injected via POST /post endpoint
let customInitialState = null;

export const setCustomInitialState = (state) => {
  customInitialState = state;
};

export const getCustomInitialState = () => customInitialState;

// Merge custom state with defaults
export const getInitialStateWithCustom = () => {
  if (!customInitialState) {
    return INITIAL_STATE;
  }

  // Deep merge custom state with defaults
  const merged = { ...INITIAL_STATE };

  if (customInitialState.user) {
    merged.user = { ...INITIAL_STATE.user, ...customInitialState.user };
  }

  if (customInitialState.emails) {
    // For emails, replace if provided, don't merge arrays
    merged.emails = customInitialState.emails;
  }

  if (customInitialState.labels) {
    merged.labels = customInitialState.labels;
  }

  if (customInitialState.drafts) {
    merged.drafts = customInitialState.drafts;
  }

  return merged;
};

// Calculate state diff
export const calculateStateDiff = (initial, current) => {
  const diff = {};

  // Check emails changes
  const initialEmails = initial?.emails || [];
  const currentEmails = current?.emails || [];

  // New emails
  const newEmailIds = currentEmails.filter(e => !initialEmails.find(ie => ie.id === e.id)).map(e => e.id);
  if (newEmailIds.length > 0) {
    diff.newEmails = newEmailIds;
  }

  // Deleted emails
  const deletedEmailIds = initialEmails.filter(e => !currentEmails.find(ce => ce.id === e.id)).map(e => e.id);
  if (deletedEmailIds.length > 0) {
    diff.deletedEmails = deletedEmailIds;
  }

  // Modified emails (read status, starred, folder, etc.)
  const modifiedEmails = {};
  for (const current of currentEmails) {
    const initial = initialEmails.find(e => e.id === current.id);
    if (initial) {
      const changes = {};
      if (initial.read !== current.read) changes.read = { from: initial.read, to: current.read };
      if (initial.starred !== current.starred) changes.starred = { from: initial.starred, to: current.starred };
      if (initial.important !== current.important) changes.important = { from: initial.important, to: current.important };
      if (initial.folder !== current.folder) changes.folder = { from: initial.folder, to: current.folder };
      if (JSON.stringify(initial.labels) !== JSON.stringify(current.labels)) changes.labels = { from: initial.labels, to: current.labels };

      if (Object.keys(changes).length > 0) {
        modifiedEmails[current.id] = changes;
      }
    }
  }
  if (Object.keys(modifiedEmails).length > 0) {
    diff.modifiedEmails = modifiedEmails;
  }

  // Labels changes
  if (JSON.stringify(initial?.labels) !== JSON.stringify(current?.labels)) {
    diff.labels = current?.labels;
  }

  // Settings changes
  if (JSON.stringify(initial?.settings) !== JSON.stringify(current?.settings)) {
    diff.settings = current?.settings;
  }

  return diff;
};
