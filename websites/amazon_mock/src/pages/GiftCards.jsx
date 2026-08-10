import React, { useState } from 'react';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { Gift } from 'lucide-react';

const AMOUNTS = [25, 50, 100, 150, 200];

// "Gift Cards" in the top nav used to open a Beauty product search. It now has a
// real gift-card purchase page: pick an amount, addressee, and add it to the cart
// as a line item like any other product.
export const GiftCards = () => {
  const { addToCart } = useStore();
  const [amount, setAmount] = useState(50);
  const [custom, setCustom] = useState('');
  const [recipient, setRecipient] = useState('');
  const [message, setMessage] = useState('');
  const [added, setAdded] = useState(false);

  const value = custom
    ? Math.min(2000, Math.max(1, Number(custom) || 0))
    : amount;

  const handleAdd = () => {
    const amountCents = Math.min(2000, Math.max(1, Number(value) || 0));
    addToCart({
      id: `giftcard-${amountCents}`,
      title: `ShopGym Gift Card — $${amountCents}`,
      price: amountCents,
      image: '',
      category: 'Gift Cards',
      giftCard: true,
      inStock: true,
      stockCount: null,
      recipient, message,
    }, 1);
    setAdded(true);
    setTimeout(() => setAdded(false), 2500);
  };

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[800px] mx-auto p-4">
        <h1 className="text-2xl font-medium flex items-center gap-2 mb-4">
          <Gift size={22} /> ShopGym Gift Cards
        </h1>
        <div className="bg-white border rounded p-6 space-y-5">
          <div>
            <label className="block text-sm font-bold mb-2">Amount</label>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Gift card amount">
              {AMOUNTS.map(a => (
                <button key={a} type="button" onClick={() => { setAmount(a); setCustom(''); }}
                  aria-pressed={!custom && amount === a}
                  className={`px-4 py-2 rounded border text-sm font-medium ${!custom && amount === a ? 'bg-xmazon-orange border-xmazon-orange text-black' : 'bg-white border-gray-300 hover:border-gray-500'}`}>
                  ${a}
                </button>
              ))}
            </div>
            <div className="mt-3">
              <label className="block text-xs text-gray-600 mb-1">Or enter a custom amount</label>
              <input type="number" min="1" max="2000" value={custom} placeholder="$"
                aria-label="Custom gift card amount"
                onChange={e => setCustom(e.target.value)}
                className="border rounded px-3 py-2 text-sm w-40 focus:outline-none focus:border-xmazon-orange" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-bold mb-1">Recipient email</label>
            <input type="email" value={recipient} placeholder="name@example.com"
              aria-label="Recipient email"
              onChange={e => setRecipient(e.target.value)}
              className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
          </div>
          <div>
            <label className="block text-sm font-bold mb-1">Gift message (optional)</label>
            <textarea value={message} rows={3} onChange={e => setMessage(e.target.value)}
              aria-label="Gift message"
              className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={handleAdd} aria-label="Add gift card to cart">Add to Cart — ${value}</Button>
            {added && <span className="text-green-700 text-sm" role="status">Added to cart</span>}
          </div>
        </div>
      </div>
    </div>
  );
};
