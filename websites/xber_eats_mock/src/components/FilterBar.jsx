import React, { useState, useMemo } from 'react';
import { ChevronDown, X, Star, Tag, Zap } from 'lucide-react';
import { useApp } from '../context/AppContext';
import './FilterBar.css';

const SORT_OPTIONS = [
  { value: 'recommended', label: 'Recommended' },
  { value: 'popular', label: 'Most Popular' },
  { value: 'rating', label: 'Rating' },
  { value: 'delivery_time', label: 'Delivery Time' },
  { value: 'price_low', label: 'Price: Low to High' },
  { value: 'price_high', label: 'Price: High to Low' },
];

const PRICE_TIERS = ['$', '$$', '$$$', '$$$$'];

// Compare dietary tags case- and separator-insensitively (data has "Gluten-Free",
// filter state stores "gluten-free"); mirrors Homepage's dnorm.
const dnorm = (s) => (s || '').toLowerCase().replace(/[\s_]+/g, '-');

// The menu feed labels a tag inconsistently ("Vegetarian", "gluten_free",
// "vegan") depending on whether it comes from the demo seed or the live engine;
// present them uniformly Title-Cased and hyphenated regardless of source.
const prettyDiet = (s) =>
  (s || '')
    .trim()
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join('-');

export default function FilterBar() {
  const { state, updateFilters } = useApp();
  const filters = state.ui.activeFilters;

  // Derive the DIETARY options from the actual menu data instead of a hardcoded
  // list that can drift from the seed: one entry per dietary tag that really
  // exists, labelled with how many restaurants offer it, sorted most-available
  // first (ties alphabetical). A tag no restaurant serves never appears.
  const dietaryOptions = useMemo(() => {
    const byTag = {};
    for (const m of state.menuItems || []) {
      for (const t of (m.dietaryTags || [])) {
        const key = dnorm(t);
        if (!key) continue;
        if (!byTag[key]) byTag[key] = { key, label: prettyDiet(t), rests: new Set() };
        if (m.restaurantId) byTag[key].rests.add(m.restaurantId);
      }
    }
    return Object.values(byTag)
      .map(o => ({ key: o.key, label: o.label, count: o.rests.size }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  }, [state.menuItems]);

  // Only offer PRICE tiers that actually exist in the catalog, in ascending
  // order — the old fixed $/$$/$$$/$$$$ listed tiers ($$$, $$$$) that matched
  // zero restaurants, so selecting them silently emptied the results.
  const priceOptions = useMemo(() => {
    const present = new Set((state.restaurants || []).map(r => r.priceRange).filter(Boolean));
    return PRICE_TIERS.filter(p => present.has(p));
  }, [state.restaurants]);
  const [sortOpen, setSortOpen] = useState(false);
  const [ratingOpen, setRatingOpen] = useState(false);
  const [priceOpen, setPriceOpen] = useState(false);
  const [dietaryOpen, setDietaryOpen] = useState(false);

  const hasActiveFilters = (filters.sort || 'recommended') !== 'recommended' ||
    filters.priceRange.length > 0 ||
    filters.dietary.length > 0 ||
    filters.maxDeliveryFee !== null ||
    filters.deals ||
    filters.under30;

  const togglePrice = (p) => {
    const current = filters.priceRange || [];
    const updated = current.includes(p) ? current.filter(x => x !== p) : [...current, p];
    updateFilters({ priceRange: updated });
  };

  const toggleDietary = (d) => {
    const current = filters.dietary || [];
    const updated = current.includes(d) ? current.filter(x => x !== d) : [...current, d];
    updateFilters({ dietary: updated });
  };

  const clearAll = () => {
    updateFilters({
      sort: 'recommended',
      priceRange: [],
      dietary: [],
      maxDeliveryFee: null,
      deals: false,
      under30: false
    });
  };

  return (
    <div className="filter-bar scrollbar-hide">
      {/* Offers pill */}
      <button
        className={`filter-bar__pill ${filters.deals ? 'filter-bar__pill--active' : ''}`}
        onClick={() => updateFilters({ deals: !filters.deals })}
      >
        <Tag size={14} />
        Offers
      </button>

      {/* Under 30 min */}
      <button
        className={`filter-bar__pill ${filters.under30 ? 'filter-bar__pill--active' : ''}`}
        onClick={() => updateFilters({ under30: !filters.under30 })}
      >
        Under 30 min
      </button>

      {/* Best overall */}
      <button
        className={`filter-bar__pill ${filters.sort === 'popular' ? 'filter-bar__pill--active' : ''}`}
        onClick={() => updateFilters({ sort: filters.sort === 'popular' ? 'recommended' : 'popular' })}
      >
        <Star size={14} />
        Best overall
      </button>

      {/* Rating dropdown */}
      <div className="filter-bar__dropdown-wrap">
        <button
          className={`filter-bar__pill ${filters.sort === 'rating' ? 'filter-bar__pill--active' : ''}`}
          onClick={() => { setRatingOpen(!ratingOpen); setSortOpen(false); setPriceOpen(false); setDietaryOpen(false); }}
        >
          <Star size={14} />
          Rating
          <ChevronDown size={14} />
        </button>
        {ratingOpen && (
          <>
            <div className="filter-bar__dropdown-backdrop" onClick={() => setRatingOpen(false)} />
            <div className="filter-bar__dropdown">
              <button
                className={`filter-bar__dropdown-item ${filters.sort === 'rating' ? 'filter-bar__dropdown-item--active' : ''}`}
                onClick={() => { updateFilters({ sort: 'rating' }); setRatingOpen(false); }}
              >
                Highest Rated
              </button>
              <button
                className={`filter-bar__dropdown-item ${filters.sort === 'recommended' ? 'filter-bar__dropdown-item--active' : ''}`}
                onClick={() => { updateFilters({ sort: 'recommended' }); setRatingOpen(false); }}
              >
                Recommended
              </button>
            </div>
          </>
        )}
      </div>

      {/* Price dropdown */}
      <div className="filter-bar__dropdown-wrap">
        <button
          className={`filter-bar__pill ${filters.priceRange.length > 0 ? 'filter-bar__pill--active' : ''}`}
          onClick={() => { setPriceOpen(!priceOpen); setSortOpen(false); setRatingOpen(false); setDietaryOpen(false); }}
        >
          Price
          <ChevronDown size={14} />
        </button>
        {priceOpen && (
          <>
            <div className="filter-bar__dropdown-backdrop" onClick={() => setPriceOpen(false)} />
            <div className="filter-bar__dropdown filter-bar__dropdown--price">
              <div className="filter-bar__price-grid">
                {priceOptions.map(p => (
                  <button
                    key={p}
                    className={`filter-bar__price-btn ${filters.priceRange.includes(p) ? 'filter-bar__price-btn--active' : ''}`}
                    onClick={() => togglePrice(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Dietary dropdown */}
      <div className="filter-bar__dropdown-wrap">
        <button
          className={`filter-bar__pill ${filters.dietary.length > 0 ? 'filter-bar__pill--active' : ''}`}
          onClick={() => { setDietaryOpen(!dietaryOpen); setSortOpen(false); setRatingOpen(false); setPriceOpen(false); }}
        >
          Dietary
          <ChevronDown size={14} />
        </button>
        {dietaryOpen && (
          <>
            <div className="filter-bar__dropdown-backdrop" onClick={() => setDietaryOpen(false)} />
            <div className="filter-bar__dropdown">
              {dietaryOptions.length === 0 && (
                <div className="filter-bar__dropdown-empty">No dietary options available</div>
              )}
              {dietaryOptions.map(o => {
                const active = filters.dietary.includes(o.key);
                return (
                  <button
                    key={o.key}
                    className={`filter-bar__dropdown-item ${active ? 'filter-bar__dropdown-item--active' : ''}`}
                    onClick={() => toggleDietary(o.key)}
                  >
                    <span className="filter-bar__dietary-label">{o.label}</span>
                    <span className="filter-bar__dietary-count">{o.count}</span>
                    {active && <span className="filter-bar__check">&#10003;</span>}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Sort dropdown */}
      <div className="filter-bar__dropdown-wrap">
        <button
          className={`filter-bar__pill ${filters.sort !== 'recommended' ? 'filter-bar__pill--active' : ''}`}
          onClick={() => { setSortOpen(!sortOpen); setRatingOpen(false); setPriceOpen(false); setDietaryOpen(false); }}
        >
          Sort
          <ChevronDown size={14} />
        </button>
        {sortOpen && (
          <>
            <div className="filter-bar__dropdown-backdrop" onClick={() => setSortOpen(false)} />
            <div className="filter-bar__dropdown">
              {SORT_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  className={`filter-bar__dropdown-item ${filters.sort === opt.value ? 'filter-bar__dropdown-item--active' : ''}`}
                  onClick={() => { updateFilters({ sort: opt.value }); setSortOpen(false); }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Clear all */}
      {hasActiveFilters && (
        <button className="filter-bar__clear" onClick={clearAll}>
          <X size={14} />
          Clear all
        </button>
      )}
    </div>
  );
}
