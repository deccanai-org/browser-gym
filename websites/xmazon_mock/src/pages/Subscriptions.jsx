import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { bridged, bridgeAct } from '../lib/bridge';
import { RefreshCw } from 'lucide-react';

const CADENCE = { weekly: 'Every week', biweekly: 'Every 2 weeks', monthly: 'Every month' };

// Subscribe & Save — active plans can be paused (skip deliveries) or cancelled.
export const Subscriptions = () => {
  const { state, cancelSubscription, pauseSubscription } = useStore();
  // Bridged: opening this page logs view_subscriptions in the engine, which is
  // the "did the agent actually look" signal several milestones gate on.
  useEffect(() => { if (bridged()) bridgeAct('shop.view_subscriptions', {}); }, []);
  const subs = state._gym_subscriptions || [];
  const productName = (pid) =>
    (state.products || []).find(p => p.id === pid)?.title || pid;

  // Resolve a subscription's delivery address to something a person can read.
  // Falls back to the id rather than hiding the difference, so a plan pointing at
  // an address the account no longer holds is still visibly not the default one.
  const shipsTo = (addrId) => {
    const list = state.addresses || state.user?.addresses || [];
    const a = list.find(x => x.id === addrId);
    if (!a) return addrId || 'default address';
    const who = a.fullName || a.name || '';
    const where = [a.city, a.state].filter(Boolean).join(', ');
    return [who, where].filter(Boolean).join(' — ') || a.street || addrId;
  };

  const statusClass = (status) => {
    if (status === 'active') return 'bg-green-100 text-green-800';
    if (status === 'paused') return 'bg-amber-100 text-amber-800';
    return 'bg-gray-100 text-gray-600';
  };

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[1000px] mx-auto p-4">
        <h1 className="text-2xl font-medium mb-4">Subscribe &amp; Save</h1>

        {subs.length === 0 ? (
          <div className="bg-white border rounded p-8 text-center">
            <p className="text-gray-600">You have no active subscriptions.</p>
            <Link to="/" className="text-xmazon-link hover:underline text-sm">Continue shopping</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {subs.map(sub => (
              <div key={sub.id} className="bg-white border rounded p-4" data-testid="subscription-row">
                <div className="flex items-start justify-between gap-4">
                  <div className="text-sm">
                    <div className="font-bold text-base mb-1">{productName(sub.product_id)}</div>
                    <div className="text-gray-600 flex items-center gap-1">
                      <RefreshCw size={13} />
                      {CADENCE[sub.cadence] || sub.cadence}
                      {sub.quantity > 1 && <span>&middot; qty {sub.quantity}</span>}
                    </div>
                    <div className="text-gray-600 mt-1">
                      Next delivery: <span className="font-bold">{sub.next_delivery_date || '—'}</span>
                    </div>
                    <div className="text-gray-600">
                      {sub.deliveries_remaining} deliver{sub.deliveries_remaining === 1 ? 'y' : 'ies'} remaining
                    </div>
                    {/* Where a repeat delivery actually goes is part of what it IS,
                        and it was the one field this row never showed. A plan can
                        ship somewhere other than the account's own address, and an
                        agent asked to tidy up an account cannot tell those apart
                        from name and cadence alone. */}
                    <div className="text-gray-600 mt-1">
                      Delivers to:{' '}
                      <span className="font-bold">{shipsTo(sub.address_id)}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Subscription {sub.id}</div>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2 py-0.5 rounded ${statusClass(sub.status)}`}>
                      {sub.status}
                    </span>
                    {sub.status === 'active' && (
                      <div className="mt-3 flex flex-col gap-2 items-end">
                        <Button
                          variant="secondary"
                          aria-label={`Pause subscription ${sub.id}`}
                          data-testid={`btn-pause-sub-${sub.id}`}
                          onClick={() => pauseSubscription(sub.id)}
                        >
                          Pause subscription
                        </Button>
                        <Button
                          variant="secondary"
                          aria-label={`Cancel subscription ${sub.id}`}
                          data-testid={`btn-cancel-sub-${sub.id}`}
                          onClick={() => cancelSubscription(sub.id)}
                        >
                          Cancel subscription
                        </Button>
                      </div>
                    )}
                    {sub.status === 'paused' && (
                      <div className="mt-3 text-xs text-amber-800 max-w-[200px]">
                        Paused — upcoming deliveries are on hold. You can still cancel.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
