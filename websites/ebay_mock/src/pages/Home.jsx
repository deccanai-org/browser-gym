import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useStore } from '../context/StoreContext';
import ListingCard from '../components/ListingCard';
import { ArrowRight } from 'lucide-react';

// Each tile targets a category that actually has active listings in the seed
// (verified against the projection) and carries a real photo.
const CATEGORIES = [
  { label: 'Electronics', c: 'Electronics', img: '/assets/categories/electronics.jpg' },
  { label: 'Home & Garden', c: 'Home & Garden', img: '/assets/categories/home_garden.jpg' },
  { label: 'Fashion', c: 'Fashion', img: '/assets/categories/fashion.jpg' },
  { label: 'Collectibles', c: 'Collectibles', img: '/assets/categories/collectibles.jpg' },
  { label: 'Sporting Goods', c: 'Sporting Goods', img: '/assets/categories/sporting_goods.jpg' },
  { label: 'Toys & Hobbies', c: 'Toys & Hobbies', img: '/assets/categories/toys_hobbies.jpg' },
  { label: 'Health & Beauty', c: 'Health & Beauty', img: '/assets/categories/health_beauty.jpg' },
  { label: 'Books', c: 'Books', img: '/assets/categories/books.jpg' },
];

function Rail({ title, to, listings }) {
  if (!listings.length) return null;
  return (
    <div className="mb-12">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
        {to && (
          <Link to={to} className="text-xbay-blue font-medium hover:underline flex items-center">
            See all <ArrowRight size={16} className="ml-1" />
          </Link>
        )}
      </div>
      <div className="flex gap-6 overflow-x-auto pb-2 -mx-1 px-1">
        {listings.map(listing => (
          <div key={listing.id} className="flex-shrink-0 w-60">
            <ListingCard listing={listing} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const { state } = useStore();
  const active = useMemo(() => state.listings.filter(l => l.status === 'active'), [state.listings]);
  const featured = active.slice(0, 8);
  const dealsUnder50 = useMemo(
    () => active.filter(l => Number(l.price) > 0 && Number(l.price) < 50).slice(0, 10),
    [active]
  );
  const electronics = useMemo(
    () => active.filter(l => (l.category || '').toLowerCase() === 'electronics').slice(0, 10),
    [active]
  );

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Hero Banner */}
      <div
        className="text-white rounded-xl p-8 mb-12 flex items-center justify-between overflow-hidden relative bg-xbay-blue"
        style={{
          backgroundImage: "linear-gradient(90deg, rgba(15,23,42,0.85) 0%, rgba(15,23,42,0.55) 45%, rgba(15,23,42,0.15) 100%), url('/assets/hero.jpg')",
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          minHeight: '260px',
        }}
      >
        <div className="relative z-10 max-w-lg">
          <h1 className="text-4xl font-bold mb-4">Score the best deals, every day</h1>
          <p className="text-lg mb-6 text-blue-100">From vintage finds to the latest tech — millions of listings, one marketplace.</p>
          <Link to="/search?c=electronics" className="inline-block bg-white text-xbay-blue font-bold px-6 py-3 rounded-full hover:bg-blue-50 transition-colors">
            Shop Electronics
          </Link>
        </div>
      </div>

      {/* Categories Grid */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold mb-6 text-gray-900">Explore Popular Categories</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {CATEGORIES.map((cat) => (
            <Link key={cat.label} to={`/search?c=${encodeURIComponent(cat.c)}`} className="group block text-center">
              <div className="rounded-full mb-3 overflow-hidden mx-auto w-32 h-32 bg-gray-100 ring-1 ring-gray-200 group-hover:scale-105 group-hover:ring-xbay-blue transition-transform">
                <img src={cat.img} alt={cat.label} className="w-full h-full object-cover" />
              </div>
              <span className="font-medium group-hover:underline">{cat.label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Featured Listings */}
      <div className="mb-12">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Today's Featured Items</h2>
          <Link to="/search" className="text-xbay-blue font-medium hover:underline flex items-center">
            See all <ArrowRight size={16} className="ml-1" />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {featured.map(listing => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      </div>

      {/* Deal + category rails */}
      <Rail title="Deals under $50" to="/search" listings={dealsUnder50} />
      <Rail title="More in Electronics" to="/search?c=electronics" listings={electronics} />
    </div>
  );
}
