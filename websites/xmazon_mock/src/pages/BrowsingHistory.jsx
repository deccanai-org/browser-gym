import React from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { Clock } from 'lucide-react';

// The account menu has always linked "Browsing History" and "Recommendations"
// straight back to "/", so both were dead ends. The store already records
// recentlyViewed as the shopper browses, so this just surfaces it — and it gives
// "what was I looking at earlier?" an actual answer.
export const BrowsingHistory = () => {
  const { state, clearBrowsingHistory } = useStore();
  const viewed = (state.recentlyViewed || [])
    .map(id => (state.products || []).find(p => p.id === id))
    .filter(Boolean);

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[1000px] mx-auto p-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-medium flex items-center gap-2">
            <Clock size={22} /> Browsing History
          </h1>
          {viewed.length > 0 && (
            <Button variant="secondary" aria-label="Clear browsing history"
                    onClick={clearBrowsingHistory}>
              Clear history
            </Button>
          )}
        </div>

        {viewed.length === 0 ? (
          <div className="bg-white border rounded p-8 text-center">
            <p className="text-gray-600 mb-2">You haven&rsquo;t viewed any items yet.</p>
            <Link to="/" className="text-xmazon-link hover:underline text-sm">Start shopping</Link>
          </div>
        ) : (
          <div className="bg-white border rounded divide-y">
            {viewed.map(p => (
              <div key={p.id} className="flex items-center gap-4 p-4" data-testid="history-row">
                <img src={p.image} alt={p.title} className="w-16 h-16 object-contain flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <Link to={`/product/${p.id}`}
                        className="text-sm text-xmazon-link hover:underline line-clamp-2">
                    {p.title}
                  </Link>
                  <div className="text-xs text-gray-500 mt-1">{p.brand}</div>
                </div>
                <div className="text-sm font-bold whitespace-nowrap">
                  ${Number(p.price || 0).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
