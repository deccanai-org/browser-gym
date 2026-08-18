import React, { useEffect, useMemo, useState } from 'react';
import { X, Minus, Plus } from 'lucide-react';
import { formatCurrency } from '../utils/dataManager';
import './ItemModal.css';

function getDefaultSelections(groups = []) {
  const selected = {};
  groups.forEach(group => {
    const defaults = group.options.filter(o => o.isDefault && o.isAvailable);
    if (group.maxSelections === 1) {
      selected[group.id] = defaults[0] ? [defaults[0]] : [];
    } else {
      selected[group.id] = defaults;
    }
  });
  return selected;
}

export default function ItemModal({ item, restaurant, onClose, onAdd }) {
  const groups = item?.customizationGroups || [];
  const [quantity, setQuantity] = useState(1);
  const [selections, setSelections] = useState(() => getDefaultSelections(groups));
  const [instructions, setInstructions] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!item) return undefined;
    setQuantity(1);
    setSelections(getDefaultSelections(item.customizationGroups || []));
    setInstructions('');
    setError('');

    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [item, onClose]);

  const selectedOptions = useMemo(() => {
    const options = [];
    groups.forEach(group => {
      (selections[group.id] || []).forEach(opt => {
        options.push({
          groupId: group.id,
          groupName: group.name,
          optionId: opt.id,
          optionName: opt.name,
          priceModifier: opt.priceModifier || 0,
        });
      });
    });
    return options;
  }, [groups, selections]);

  const unitPrice = useMemo(() => {
    const mods = selectedOptions.reduce((s, o) => s + o.priceModifier, 0);
    return (item?.price || 0) + mods;
  }, [item, selectedOptions]);

  if (!item) return null;

  const toggleOption = (group, option) => {
    setError('');
    setSelections(prev => {
      const current = prev[group.id] || [];
      if (group.maxSelections === 1) {
        return { ...prev, [group.id]: [option] };
      }
      const exists = current.some(o => o.id === option.id);
      if (exists) {
        return { ...prev, [group.id]: current.filter(o => o.id !== option.id) };
      }
      if (current.length >= group.maxSelections) {
        return prev;
      }
      return { ...prev, [group.id]: [...current, option] };
    });
  };

  const isSelected = (groupId, optionId) =>
    (selections[groupId] || []).some(o => o.id === optionId);

  const handleAdd = () => {
    for (const group of groups) {
      const count = (selections[group.id] || []).length;
      if (group.required && count < (group.minSelections || 1)) {
        setError(`Please select: ${group.name}`);
        return;
      }
    }
    onAdd(item, quantity, selectedOptions, instructions);
  };

  return (
    <div className="item-modal-overlay" onClick={onClose}>
      <div className="item-modal animate-fadeIn" onClick={(e) => e.stopPropagation()}>
        <button className="item-modal__close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>

        <div className="item-modal__body">
          {item.imageUrl && (
            <img
              src={item.imageUrl}
              alt={item.name}
              className="item-modal__photo"
              style={{ width: '100%', height: 180, objectFit: 'cover', borderRadius: 12, marginBottom: 12, display: 'block' }}
            />
          )}
          <div className="item-modal__header">
            <h2 className="item-modal__name">{item.name}</h2>
            {item.description && <p className="item-modal__desc">{item.description}</p>}
            <div className="item-modal__price">{formatCurrency(item.price)}</div>
            {item.dietaryTags?.length > 0 && (
              <div className="item-modal__tags">
                {item.dietaryTags.map(tag => (
                  <span key={tag} className="item-modal__tag">{tag}</span>
                ))}
              </div>
            )}
          </div>

          {groups.map(group => (
            <div key={group.id} className="item-modal__group">
              <div className="item-modal__group-header">
                <h3 className="item-modal__group-name">{group.name}</h3>
                {group.required ? (
                  <span className="item-modal__required">Required</span>
                ) : (
                  <span className="item-modal__optional">Optional</span>
                )}
              </div>
              <div className="item-modal__options">
                {group.options.filter(o => o.isAvailable !== false).map(option => (
                  <label
                    key={option.id}
                    className={`item-modal__option ${isSelected(group.id, option.id) ? 'item-modal__option--selected' : ''}`}
                  >
                    <input
                      className="item-modal__option-input"
                      type={group.maxSelections === 1 ? 'radio' : 'checkbox'}
                      name={group.id}
                      checked={isSelected(group.id, option.id)}
                      onChange={() => toggleOption(group, option)}
                    />
                    <span className="item-modal__option-name">{option.name}</span>
                    {option.priceModifier > 0 && (
                      <span className="item-modal__option-price">+{formatCurrency(option.priceModifier)}</span>
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}

          <div className="item-modal__instructions">
            <h3 className="item-modal__group-name">Special instructions</h3>
            <textarea
              className="item-modal__textarea"
              rows={3}
              placeholder="Add a note (e.g. allergies, spice level)"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>
        </div>

        <div className="item-modal__footer" style={{ flexWrap: 'wrap' }}>
          {error && (
            <div style={{ width: '100%', color: 'var(--color-error)', fontSize: 13, marginBottom: 4 }}>
              {error}
            </div>
          )}
          <div className="item-modal__qty-controls">
            <button
              className="item-modal__qty-btn"
              onClick={() => setQuantity(q => Math.max(1, q - 1))}
              disabled={quantity <= 1}
              aria-label="Decrease quantity"
            >
              <Minus size={16} />
            </button>
            <span className="item-modal__qty">{quantity}</span>
            <button
              className="item-modal__qty-btn"
              onClick={() => setQuantity(q => q + 1)}
              aria-label="Increase quantity"
            >
              <Plus size={16} />
            </button>
          </div>
          <button className="item-modal__add-btn" onClick={handleAdd}>
            <span>Add to order{restaurant ? ` · ${restaurant.name}` : ''}</span>
            <span>{formatCurrency(unitPrice * quantity)}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
