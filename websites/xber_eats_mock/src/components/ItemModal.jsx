import React, { useEffect, useState } from 'react';
import { X, Minus, Plus } from 'lucide-react';
import { formatCurrency } from '../lib/utils';

/** Engine dishes use customizationGroups; seed demo uses modifiers. Never assume either. */
function modifierGroups(item) {
  if (Array.isArray(item?.modifiers)) return item.modifiers;
  if (Array.isArray(item?.customizationGroups)) return item.customizationGroups;
  return [];
}

function selectedOptionsFromState(modifiersState) {
  const out = [];
  for (const [groupId, val] of Object.entries(modifiersState || {})) {
    const opts = Array.isArray(val) ? val : [val];
    for (const o of opts) {
      if (!o) continue;
      out.push({
        groupId,
        groupName: '',
        optionId: o.id || '',
        optionName: o.name || '',
        priceModifier: o.price ?? o.priceModifier ?? 0,
      });
    }
  }
  return out;
}

export default function ItemModal({ item, isOpen, onClose, onAddToCart }) {
  const [quantity, setQuantity] = useState(1);
  const [modifiers, setModifiers] = useState({});
  const [instructions, setInstructions] = useState('');
  const [validationMessage, setValidationMessage] = useState('');

  // Reset the form ONLY when the dish changes. `onClose` is deliberately not a
  // dependency here: StorePage passes it as an inline arrow, so it has a new
  // identity on every render, and in bridged mode the 2.5s engine poll
  // re-renders the page constantly. With onClose in this list the effect re-ran
  // on every poll and setQuantity(1) silently threw away what the user had
  // chosen — set 4 portions, read the menu for three seconds, and the modal was
  // back to 1 with the button quietly showing the single-item price.
  useEffect(() => {
    if (!isOpen || !item) return;
    setQuantity(1);
    setModifiers({});
    setInstructions('');
    setValidationMessage('');
  }, [isOpen, item?.id]);

  // Escape closes the modal. This lives in its own effect so `onClose` (an inline
  // arrow from StorePage, new identity on every poll-driven render) can stay a
  // dependency here without re-running the reset effect above.
  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !item) return null;

  const groups = modifierGroups(item);
  const imageSrc = item.imageUrl || item.image || '';

  const handleModifierChange = (modId, option, type) => {
    setModifiers(prev => {
      if (type === 'radio') {
        return { ...prev, [modId]: option };
      }
      const current = Array.isArray(prev[modId]) ? prev[modId] : [];
      const exists = current.some(selected => selected.name === option.name);
      return {
        ...prev,
        [modId]: exists
          ? current.filter(selected => selected.name !== option.name)
          : [...current, option]
      };
    });
    setValidationMessage('');
  };

  const calculateTotal = () => {
    const modTotal = Object.values(modifiers)
      .flatMap(mod => (Array.isArray(mod) ? mod : [mod]))
      .reduce((sum, mod) => sum + (mod?.price || mod?.priceModifier || 0), 0);
    return (item.price + modTotal) * quantity;
  };

  const handleSubmit = () => {
    const missingRequired = groups.filter(m => m.required && !modifiers[m.id]);
    if (missingRequired.length > 0) {
      setValidationMessage(`Please select: ${missingRequired.map(m => m.name).join(', ')}`);
      return;
    }
    onAddToCart(item, quantity, selectedOptionsFromState(modifiers), instructions);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="bg-white w-full max-w-2xl max-h-[90vh] rounded-2xl overflow-hidden flex flex-col shadow-2xl animate-in fade-in zoom-in duration-200"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={item.name}
      >
        <div className="relative h-48 sm:h-64 shrink-0 bg-gray-100">
          {imageSrc ? (
            <img src={imageSrc} alt={item.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-5xl" aria-hidden>
              {item.emoji || '🍽️'}
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute top-4 right-4 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <h2 className="text-3xl font-bold mb-2">{item.name}</h2>
          <p className="text-gray-500 mb-6">{item.description}</p>

          <div className="space-y-8">
            {groups.map(mod => (
              <div key={mod.id} className="border-b border-gray-100 pb-6 last:border-0">
                <div className="flex justify-between mb-4">
                  <h3 className="font-bold text-lg">{mod.name}</h3>
                  {mod.required && (
                    <span className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded font-bold h-fit">
                      Required
                    </span>
                  )}
                </div>

                <div className="space-y-3">
                  {(mod.options || []).map((opt, idx) => (
                    <label key={idx} className="flex items-center justify-between cursor-pointer group">
                      <div className="flex items-center gap-3">
                        <input
                          type={mod.type || 'radio'}
                          name={mod.id}
                          className="w-5 h-5 accent-primary"
                          onChange={() => handleModifierChange(mod.id, opt, mod.type || 'radio')}
                          checked={
                            (mod.type || 'radio') === 'checkbox'
                              ? (Array.isArray(modifiers[mod.id])
                                && modifiers[mod.id].some(selected => selected.name === opt.name))
                              : modifiers[mod.id]?.name === opt.name
                          }
                        />
                        <span className="text-gray-700 group-hover:text-black">{opt.name}</span>
                      </div>
                      {(opt.price || 0) > 0 && (
                        <span className="text-gray-500">+{formatCurrency(opt.price)}</span>
                      )}
                    </label>
                  ))}
                </div>
              </div>
            ))}

            <div>
              <h3 className="font-bold text-lg mb-2">Special Instructions</h3>
              <textarea
                className="w-full border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-black focus:border-transparent outline-none resize-none"
                rows="3"
                placeholder="Add a note for the kitchen..."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-gray-100 bg-white shrink-0 space-y-3">
          {validationMessage && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
              {validationMessage}
            </div>
          )}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 border border-gray-300 rounded-full px-4 py-2">
              <button
                type="button"
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
                disabled={quantity <= 1}
                className="disabled:opacity-30 hover:text-primary"
                aria-label="Decrease quantity"
              >
                <Minus className="w-5 h-5" />
              </button>
              <span className="font-medium text-lg min-w-[20px] text-center">{quantity}</span>
              <button
                type="button"
                onClick={() => setQuantity(quantity + 1)}
                className="hover:text-primary"
                aria-label="Increase quantity"
              >
                <Plus className="w-5 h-5" />
              </button>
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              data-test-id="btn-add-to-cart"
              aria-label={`Add ${item?.name || 'item'} to order`}
              className="flex-1 bg-primary text-white font-bold text-lg py-3 rounded-lg hover:bg-green-600 transition-colors flex justify-between px-6"
            >
              <span>Add to order</span>
              <span>{formatCurrency(calculateTotal())}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
