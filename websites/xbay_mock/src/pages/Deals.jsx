import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import ListingCard from '../components/ListingCard';

export default function Deals() {
  const { state } = useStore();
  // Reuse Home's deal rule: active listings with an effective price under $50,
  // sorted cheapest first. Reads state.listings so it works in demo AND bridged.
  const deals = useMemo(() => {
    return state.listings
      .filter(l => l.status === 'active' && Number(l.price) > 0 && Number(l.price) < 50)
      .sort((a, b) => Number(a.price) - Number(b.price));
  }, [state.listings]);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Daily Deals</h1>
        <p className="text-gray-600 mt-1">Active listings under $50 — grab them before they're gone.</p>
      </div>

      {deals.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500">No deals available right now.</p>
          <Link to="/" className="text-xbay-blue font-medium hover:underline mt-2 inline-block">
            Back to home
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {deals.map(listing => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}
    </div>
  );
}
