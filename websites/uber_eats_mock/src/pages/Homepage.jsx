import React, { useMemo, useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useApp } from '../context/AppContext';
import RestaurantCard from '../components/RestaurantCard';
import FilterBar from '../components/FilterBar';
import './Homepage.css';

// Dietary tags are compared case- AND separator-insensitively: ambient dishes
// historically carried "gluten_free" while the filter emits "gluten-free".
const dnorm = (s) => (s || '').toLowerCase().replace(/[\s_]+/g, '-');

export default function Homepage() {
  const { state, applyPromoCode } = useApp();
  const navigate = useNavigate();
  const [promoBannerIdx, setPromoBannerIdx] = useState(0);

  const filteredRestaurants = useMemo(() => {
    let results = [...state.restaurants];
    const filters = state.ui.activeFilters;

    if (filters.priceRange && filters.priceRange.length > 0) {
      results = results.filter(r => filters.priceRange.includes(r.priceRange));
    }

    if (filters.dietary && filters.dietary.length > 0) {
      results = results.filter(r => {
        const menuItems = state.menuItems.filter(m => m.restaurantId === r.id);
        return filters.dietary.some(d =>
          menuItems.some(m => m.dietaryTags && m.dietaryTags.some(t => dnorm(t) === dnorm(d)))
        );
      });
    }

    if (filters.maxDeliveryFee !== null && filters.maxDeliveryFee !== undefined) {
      results = results.filter(r => r.deliveryFee <= filters.maxDeliveryFee);
    }

    if (filters.deals) {
      results = results.filter(r =>
        (r.promotions && r.promotions.length > 0) || r.deliveryFee === 0
      );
    }

    if (filters.under30) {
      results = results.filter(r => r.deliveryTimeMax <= 30);
    }

    switch (filters.sort) {
      case 'popular':
        results.sort((a, b) => b.reviewCount - a.reviewCount);
        break;
      case 'rating':
        results.sort((a, b) => b.rating - a.rating);
        break;
      case 'delivery_time':
        results.sort((a, b) => a.deliveryTimeMin - b.deliveryTimeMin);
        break;
      case 'price_low':
        results.sort((a, b) => a.priceRange.length - b.priceRange.length);
        break;
      case 'price_high':
        results.sort((a, b) => b.priceRange.length - a.priceRange.length);
        break;
      default:
        results.sort((a, b) => {
          if (a.isSponsored && !b.isSponsored) return -1;
          if (!a.isSponsored && b.isSponsored) return 1;
          return b.rating - a.rating;
        });
    }

    return results;
  }, [state.restaurants, state.menuItems, state.ui.activeFilters]);

  const featured = filteredRestaurants.filter(r => r.isSponsored || (r.tags || []).includes('Popular'));
  const topRated = [...filteredRestaurants].sort((a, b) => b.rating - a.rating).slice(0, 4);
  const quickDelivery = [...filteredRestaurants].sort((a, b) => a.deliveryTimeMin - b.deliveryTimeMin).slice(0, 4);
  const newRestaurants = filteredRestaurants.filter(r => (r.tags || []).includes('New'));
  const dealsRestaurants = filteredRestaurants.filter(r => r.promotions && r.promotions.length > 0);

  // Build banners from the REAL promo codes the engine will actually accept
  // (state.promotions), so we never advertise a code checkout will reject. Each
  // banner is clickable: it stages the code (applyPromoCode) and routes to the
  // Offers view. A leading $0-delivery banner is honest (many restaurants have
  // deliveryFee 0). Falls back to code-free banners in demo mode.
  const BANNER_BG = ['#06C167', '#276E50', '#000000', '#1F6FEB'];
  const promoBanners = useMemo(() => {
    const promos = state.promotions || [];
    const list = [{ id: 'pb_delivery', title: '$0 Delivery Fee', subtitle: 'On select restaurants near you', bg: BANNER_BG[0], accent: 'rgba(255,255,255,0.15)', to: '/search?q=deals' }];
    promos.forEach((p, i) => {
      const pct = p.percentOff ? Math.round(p.percentOff * 100) : null;
      list.push({
        id: p.code || `pb${i}`,
        title: pct ? `${pct}% off your order` : (p.description || 'Special offer'),
        subtitle: p.code ? `Use code ${p.code} at checkout` : (p.description || ''),
        bg: BANNER_BG[(i + 1) % BANNER_BG.length], accent: 'rgba(255,255,255,0.12)',
        code: p.code, to: '/search?q=deals',
      });
    });
    return list;
  }, [state.promotions]);

  const handleBannerClick = (banner) => {
    // Only stage the code when there's already a cart to apply it to; otherwise
    // the code is shown on the banner and works at checkout. Always route to the
    // Offers view so the click does something visible.
    if (banner.code && applyPromoCode && (state.cart?.items?.length > 0)) applyPromoCode(banner.code);
    if (banner.to) navigate(banner.to);
  };

  const handlePrevBanner = () => {
    setPromoBannerIdx(prev => (prev === 0 ? promoBanners.length - 1 : prev - 1));
  };
  const handleNextBanner = () => {
    setPromoBannerIdx(prev => (prev === promoBanners.length - 1 ? 0 : prev + 1));
  };

  return (
    <div className="homepage">
      {/* Category Carousel */}
      <div className="homepage__categories scrollbar-hide">
        {state.categories.map(cat => (
          <Link
            key={cat.id}
            to={`/search?category=${encodeURIComponent(cat.name)}`}
            className="homepage__cat-chip"
          >
            <div className="homepage__cat-icon-wrap">
              <span className="homepage__cat-icon">{cat.icon}</span>
            </div>
            <span className="homepage__cat-name">{cat.name}</span>
          </Link>
        ))}
      </div>

      {/* Filter Bar */}
      <FilterBar />

      {/* Promo Banner Carousel */}
      <div className="homepage__banner-carousel">
        <button className="homepage__banner-arrow homepage__banner-arrow--left" onClick={handlePrevBanner}>
          <ChevronLeft size={20} />
        </button>
        <div className="homepage__banner-track">
          {promoBanners.map((banner, idx) => (
            <div
              key={banner.id}
              role="button"
              tabIndex={idx === promoBannerIdx ? 0 : -1}
              onClick={() => handleBannerClick(banner)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleBannerClick(banner); } }}
              className={`homepage__promo-banner ${idx === promoBannerIdx ? 'homepage__promo-banner--active' : ''}`}
              style={{ background: banner.bg, cursor: 'pointer' }}
            >
              <div className="homepage__promo-banner-inner">
                <h3 className="homepage__promo-banner-title">{banner.title}</h3>
                <p className="homepage__promo-banner-subtitle">{banner.subtitle}</p>
              </div>
              <div className="homepage__promo-banner-shape" style={{ background: banner.accent }} />
            </div>
          ))}
        </div>
        <button className="homepage__banner-arrow homepage__banner-arrow--right" onClick={handleNextBanner}>
          <ChevronRight size={20} />
        </button>
        <div className="homepage__banner-dots">
          {promoBanners.map((_, idx) => (
            <button
              key={idx}
              className={`homepage__banner-dot ${idx === promoBannerIdx ? 'homepage__banner-dot--active' : ''}`}
              onClick={() => setPromoBannerIdx(idx)}
            />
          ))}
        </div>
      </div>

      {/* Offers near you */}
      {dealsRestaurants.length > 0 && (
        <section className="homepage__section">
          <div className="homepage__section-header">
            <h2 className="homepage__section-title">Offers near you</h2>
            <Link to="/search?q=deals" className="homepage__see-all">See all</Link>
          </div>
          <div className="homepage__scroll-row scrollbar-hide">
            {dealsRestaurants.map(r => (
              <div key={r.id} className="homepage__scroll-item">
                <RestaurantCard restaurant={r} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Featured Section */}
      {featured.length > 0 && (
        <section className="homepage__section">
          <div className="homepage__section-header">
            <h2 className="homepage__section-title">Featured on GymEats</h2>
            <Link to="/search?q=popular" className="homepage__see-all">See all</Link>
          </div>
          <div className="homepage__grid">
            {featured.slice(0, 6).map(r => (
              <RestaurantCard key={r.id} restaurant={r} />
            ))}
          </div>
        </section>
      )}

      {/* Popular Near You */}
      <section className="homepage__section">
        <div className="homepage__section-header">
          <h2 className="homepage__section-title">Popular near you</h2>
          <Link to="/search?q=popular" className="homepage__see-all">See all</Link>
        </div>
        <div className="homepage__grid">
          {topRated.map(r => (
            <RestaurantCard key={r.id} restaurant={r} />
          ))}
        </div>
      </section>

      {/* Quick Delivery */}
      <section className="homepage__section">
        <div className="homepage__section-header">
          <h2 className="homepage__section-title">Quick delivery</h2>
        </div>
        <div className="homepage__scroll-row scrollbar-hide">
          {quickDelivery.map(r => (
            <div key={r.id} className="homepage__scroll-item">
              <RestaurantCard restaurant={r} />
            </div>
          ))}
        </div>
      </section>

      {/* New on GymEats */}
      {newRestaurants.length > 0 && (
        <section className="homepage__section">
          <div className="homepage__section-header">
            <h2 className="homepage__section-title">New on GymEats</h2>
          </div>
          <div className="homepage__grid">
            {newRestaurants.map(r => (
              <RestaurantCard key={r.id} restaurant={r} />
            ))}
          </div>
        </section>
      )}

      {/* GymEats One Banner */}
      {!state.user.uberOneActive && (
        <div className="homepage__uber-one-banner">
          <div className="homepage__uber-one-content">
            <div className="homepage__uber-one-icon">
              <span style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>1</span>
            </div>
            <div>
              <h3 className="homepage__uber-one-title">$0 Delivery Fee with GymEats One</h3>
              <p className="homepage__uber-one-sub">Plus 5% off eligible orders. Cancel anytime.</p>
            </div>
          </div>
          <Link to="/account" className="homepage__uber-one-cta">Try free for 1 month</Link>
        </div>
      )}

      {/* All Restaurants */}
      <section className="homepage__section">
        <div className="homepage__section-header">
          <h2 className="homepage__section-title">All restaurants</h2>
        </div>
        <div className="homepage__grid">
          {filteredRestaurants.map(r => (
            <RestaurantCard key={r.id} restaurant={r} />
          ))}
        </div>
      </section>
    </div>
  );
}
