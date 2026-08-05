import React from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import { ProductCard } from '../components/product/ProductCard';
import { Sparkles } from 'lucide-react';

// "Recommendations" in the account menu used to dead-end on the wishlist. It now
// shows a real recommended-for-you grid, drawn from the highest-rated catalog
// items the shopper hasn't already bought — an honest page that matches its label.
export const Recommendations = () => {
  const { state } = useStore();
  const products = state.products || [];
  const boughtIds = new Set((state.orders || []).flatMap(o => (o.items || []).map(i => i.productId)));
  const recs = [...products]
    .filter(p => !boughtIds.has(p.id))
    .sort((a, b) => (b.rating || 0) - (a.rating || 0) || (b.reviewCount || 0) - (a.reviewCount || 0))
    .slice(0, 12);

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[1400px] mx-auto p-4">
        <h1 className="text-2xl font-medium flex items-center gap-2 mb-1">
          <Sparkles size={22} /> Recommended for you
        </h1>
        <p className="text-sm text-gray-600 mb-4">Top-rated picks based on what shoppers like you love.</p>
        {recs.length === 0 ? (
          <div className="bg-white border rounded p-8 text-center">
            <p className="text-gray-600 mb-2">Nothing to recommend yet.</p>
            <Link to="/" className="text-xmazon-link hover:underline text-sm">Browse the store</Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="recommendations-grid">
            {recs.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        )}
      </div>
    </div>
  );
};
