import React, { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { bridged, bridgeAct } from '../lib/bridge';

// Gift registry with purchased qty indicators (durable via _gym_registries).
export const Registry = () => {
  const { registryId } = useParams();
  const { state } = useStore();
  const regs = state._gym_registries || [];
  const reg =
    regs.find(r => r.id === registryId) ||
    regs[0] ||
    null;

  useEffect(() => {
    if (!bridged()) return;
    const rid = registryId || (reg && reg.id) || '';
    if (rid) bridgeAct('shop.view_registry', { registry_id: rid });
  }, [registryId, reg && reg.id]);

  if (!reg) {
    return (
      <div className="bg-xmazon-bg min-h-screen">
        <div className="max-w-[900px] mx-auto p-6">
          <h1 className="text-2xl font-medium mb-2">Gift Registry</h1>
          <p className="text-gray-600 mb-4">No registries found for this account.</p>
          <Link to="/wishlist" className="text-xmazon-blue hover:underline text-sm">
            Your Wish List
          </Link>
        </div>
      </div>
    );
  }

  const items = reg.items || [];

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[900px] mx-auto p-4">
        <div className="text-xs text-gray-500 mb-1">
          <Link to="/" className="text-xmazon-blue hover:underline">ShopGym</Link>
          <span className="mx-1">›</span>
          <span>Gift Registry</span>
        </div>
        <h1 className="text-2xl font-medium" data-testid="registry-title">
          {reg.owner_name}&apos;s Registry
        </h1>
        <p className="text-gray-600 mb-4">{reg.event_title}</p>
        <div className="text-sm text-gray-500 mb-4">Registry ID: {reg.id}</div>

        <div className="space-y-3">
          {items.map((item) => {
            const requested = Number(item.quantity_requested || 1);
            const purchased = Number(item.quantity_purchased || 0);
            const fulfilled = purchased >= requested;
            const remaining = Math.max(0, requested - purchased);
            return (
              <div
                key={item.product_id}
                className="bg-white border rounded p-4 flex justify-between gap-4"
                data-testid={`registry-item-${item.product_id}`}
              >
                <div>
                  <div className="font-medium text-base">{item.name}</div>
                  <div className="text-sm text-gray-600 mt-1">
                    ${Number(item.price || 0).toFixed(2)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">SKU {item.product_id}</div>
                </div>
                <div className="text-right text-sm">
                  <div
                    className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      fulfilled
                        ? 'bg-green-100 text-green-800'
                        : 'bg-blue-50 text-blue-800'
                    }`}
                    data-testid={`registry-purchase-status-${item.product_id}`}
                  >
                    {fulfilled
                      ? `Fully purchased (${purchased} of ${requested})`
                      : `Purchased ${purchased} of ${requested} · ${remaining} still needed`}
                  </div>
                  {fulfilled && (
                    <div className="text-xs text-green-700 mt-2 max-w-[220px]">
                      Someone already got this — picking another gift avoids a duplicate.
                    </div>
                  )}
                  {!fulfilled && (
                    <Link
                      to={`/product/${item.product_id}`}
                      className="block mt-3 text-xmazon-blue hover:underline text-xs"
                    >
                      View product
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
