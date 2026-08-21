// Bridge client — puts a CUA-Gym-Hub mock into "bridged" mode, where every
// gym-backed interactable drives the REAL gym engine (cross-app bus, scheduler,
// verifiers) instead of this mock's local store. Cross-app effects (e.g. a shop
// order's confirmation email) then appear in the relevant tab on their own.
//
// Runtime opt-in: bridged when the page URL carries ?bridge=<bridge-service-url>
// (e.g. ...?bridge=http://127.0.0.1:8090). No param -> the mock behaves exactly
// as upstream (legacy mode), so one build serves both.
//
// ?session=<id> picks WHICH episode this tab belongs to. Each session leases its
// own gym instance, so two annotators on the same task never share a world — and
// every tab of one session (shop, mail, calendar, ...) must pass the same value
// or their cross-app effects would land in different engines. Without it the
// service falls back to a single default episode, which is fine for a solo run.

const _params = new URLSearchParams(
  typeof window !== 'undefined' ? window.location.search : '');
// Bridged mode must survive an in-app search or an F5 that drops the ?bridge=
// &session= query params, or the mock silently reverts to its stale hardcoded
// demo data. Persist them per-tab: a URL carrying them refreshes the store; a
// URL missing them recovers from it.
const _ss = (k, v) => {
  try { if (v) { sessionStorage.setItem(k, v); return v; } return sessionStorage.getItem(k) || ''; }
  catch (_) { return v || ''; }
};
const BASE = _ss('gym_bridge', (_params.get('bridge') || '').replace(/\/$/, ''));
const SESSION = _ss('gym_session', _params.get('session') || '');

const _root = () => (SESSION ? `${BASE}/bridge/${encodeURIComponent(SESSION)}` : `${BASE}/bridge`);

export const bridged = () => !!BASE;
export const bridgeSession = () => SESSION;

export async function bridgeState(app, tries = 6) {
  // The bridge holds ONE world and serves it single-threaded, so while another
  // app is mid-checkout a request to it can briefly fail or 503. A tab reloaded
  // in that window used to give up after a single try and fall back to its
  // bundled demo data, stranding it on a stale catalogue. Retry a few times so
  // a transient hiccup self-heals instead — the block clears in ~1-2s.
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(`${_root()}/state?app=${encodeURIComponent(app)}`);
      if (r.ok) return (await r.json()).apps?.[app] || null;
    } catch (_) { /* transient network failure — fall through and retry */ }
    if (i < tries - 1) await new Promise(res => setTimeout(res, 300 + 200 * i));
  }
  return null;
}

export async function bridgeAct(action, payload = {}) {
  const r = await fetch(`${_root()}/act`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, payload }),
  });
  return await r.json(); // { ok, status, apps:{shop,mail,market,calendar,food} }
}

// Poll the engine so cross-app effects produced in OTHER tabs surface here too.
// This is what makes a shop order's confirmation email appear in the Gmail tab
// without the annotator reloading anything.
export function bridgePoll(app, onState, ms = 2500) {
  if (!bridged()) return () => {};
  let live = true;
  const tick = async () => {
    if (!live) return;
    try { const s = await bridgeState(app); if (s) onState(s); } catch (_) {}
    if (live) setTimeout(tick, ms);
  };
  tick();   // fire immediately so a failed mount fetch recovers within one cycle
  return () => { live = false; };
}
