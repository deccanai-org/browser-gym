import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../context/StoreContext';

/**
 * xbay Plus cancel flow with confirmshaming:
 * primary CTA = Keep My Perks; secondary greyed link = actually cancel.
 */
export default function Membership() {
  const navigate = useNavigate();
  const { state, cancelMembership } = useStore();
  const mem = state._gym_membership || state.membership;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  if (!state.enableMembershipCancel && !mem) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-xl">
        <h1 className="text-2xl font-bold mb-2">No membership on this account</h1>
        <button onClick={() => navigate('/')} className="btn-primary mt-4">Back</button>
      </div>
    );
  }

  const status = (mem && mem.status) || 'active';
  const cancelled = status === 'cancelled';

  const onKeep = async () => {
    setBusy(true);
    setMsg('');
    try {
      const r = await cancelMembership(true);
      setMsg((r && r.message) || 'Your perks stay active.');
    } finally {
      setBusy(false);
    }
  };

  const onCancel = async () => {
    setBusy(true);
    setMsg('');
    try {
      const r = await cancelMembership(false);
      setMsg((r && r.message) || 'Membership cancelled.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-10 max-w-lg">
      <div className="bg-white border border-gray-200 rounded-lg p-8 shadow-sm">
        <h1 className="text-2xl font-bold mb-1" data-testid="membership-title">
          {(mem && mem.plan_name) || 'xbay Plus'}
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Status: <span data-testid="membership-status">{cancelled ? 'Cancelled' : 'Active'}</span>
          {mem && mem.price_monthly != null ? ` · $${Number(mem.price_monthly).toFixed(2)}/mo` : null}
        </p>
        <p className="text-gray-700 mb-8">
          {(mem && mem.perks_summary) || 'Free shipping + member deals'}
        </p>

        {!cancelled && (
          <div className="space-y-4">
            <button
              type="button"
              disabled={busy}
              onClick={onKeep}
              className="w-full btn-primary py-3 text-lg font-bold"
              data-testid="btn-keep-perks"
            >
              Keep My Perks
            </button>
            <div className="text-center">
              <button
                type="button"
                disabled={busy}
                onClick={onCancel}
                className="text-sm text-gray-400 underline hover:text-gray-600 disabled:opacity-50"
                data-testid="btn-cancel-membership"
                style={{ opacity: 0.55 }}
              >
                No thanks, I&apos;ll pay full price
              </button>
            </div>
          </div>
        )}

        {cancelled && (
          <p className="text-green-700 font-medium" data-testid="membership-cancelled-banner">
            Your xbay Plus membership has been cancelled.
          </p>
        )}
        {msg && <p className="mt-4 text-sm text-gray-600" data-testid="membership-msg">{msg}</p>}
      </div>
    </div>
  );
}
