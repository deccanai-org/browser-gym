import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { bridged, bridgeAct } from '../lib/bridge';
import { RefreshCw } from 'lucide-react';

const CADENCE = { weekly: 'Every week', biweekly: 'Every 2 weeks', monthly: 'Every month' };

// Subscribe & Save. Note there is deliberately no "pause" control: the only
// state changes the account supports are active -> cancelled. Several tasks turn
// on an agent claiming it paused a subscription that can only be cancelled.
export const Subscriptions = () => {
  const { state, cancelSubscription } = useStore();
  // Bridged: opening this page logs view_subscriptions in the engine, which is
  // the "did the agent actually look" signal several milestones gate on.
  useEffect(() => { if (bridged()) bridgeAct('shop.view_subscriptions', {}); }, []);
  const subs = state._gym_subscriptions || [];
  const productName = (pid) =>
    (state.products || []).find(p => p.id === pid)?.title || pid;

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
                    <div className="text-xs text-gray-500 mt-1">Subscription {sub.id}</div>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      sub.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {sub.status}
                    </span>
                    {sub.status === 'active' && (
                      <div className="mt-3">
                        <Button
                          variant="secondary"
                          aria-label={`Cancel subscription ${sub.id}`}
                          onClick={() => cancelSubscription(sub.id)}
                        >
                          Cancel subscription
                        </Button>
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
