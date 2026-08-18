import React, { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Tag } from 'lucide-react';

// "Sell" in the top nav used to open the profile page. It now has a real
// list-an-item form that confirms submission — enough for an agent task that
// asks to "list X for sale" to complete against a matching page.
export const Sell = () => {
  const [form, setForm] = useState({ title: '', price: '', category: 'Electronics', condition: 'New' });
  const [listed, setListed] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[720px] mx-auto p-4">
        <h1 className="text-2xl font-medium flex items-center gap-2 mb-4">
          <Tag size={22} /> Sell on xmazon
        </h1>
        <div className="bg-white border rounded p-6">
          {listed ? (
            <div className="text-green-700 text-sm" role="status" data-testid="sell-listed">
              Your item “{form.title}” is now listed for ${form.price}.
            </div>
          ) : (
            <form onSubmit={e => { e.preventDefault(); setListed(true); }} className="space-y-4">
              <div>
                <label className="block text-sm font-bold mb-1">Item title</label>
                <input value={form.title} onChange={e => set('title', e.target.value)} required
                  aria-label="Item title"
                  className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
              </div>
              <div>
                <label className="block text-sm font-bold mb-1">Price ($)</label>
                <input type="number" min="0" step="0.01" value={form.price}
                  onChange={e => set('price', e.target.value)} required aria-label="Price"
                  className="border rounded px-3 py-2 text-sm w-40 focus:outline-none focus:border-xmazon-orange" />
              </div>
              <Button type="submit" aria-label="List item">List item</Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
