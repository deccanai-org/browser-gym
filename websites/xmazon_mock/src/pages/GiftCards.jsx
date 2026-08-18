import React, { useState } from 'react';
import { useStore } from '../context/StoreContext';
import { Button } from '../components/ui/Button';
import { Gift } from 'lucide-react';

// Every amount on this page is WHOLE DOLLARS. An earlier version called the
// number `amountCents` while passing dollars straight through to `price`, which
// was harmless only because the engine also prices in dollars — the name was the
// only thing that was wrong, and a name that lies about its unit is how a $50
// card eventually ships for fifty cents.
const PRESET_AMOUNTS_USD = [25, 50, 100, 150, 200];
const MIN_USD = 1;
const MAX_USD = 2000;

// The engine's id namespace for standalone gift cards (server/ambient.py). It is
// canonical whole dollars in range and nothing else: `giftcard-050` and
// `giftcard-2500` are refused, so this page must not invent either. Three tasks
// forbid buying a gift card and their tripwires recognise a purchase BY this id,
// so the spelling here is load-bearing, not cosmetic.
const giftCardId = (usd) => `giftcard-${usd}`;

// "Gift Cards" in the top nav used to open a Beauty product search. It now has a
// real gift-card purchase page: pick an amount, addressee, and add it to the cart
// as a line item like any other product.
export const GiftCards = () => {
  const { addToCart, setLineOptions } = useStore();
  const [presetUsd, setPresetUsd] = useState(50);
  const [customText, setCustomText] = useState('');
  const [recipient, setRecipient] = useState('');
  const [message, setMessage] = useState('');
  // The result of the last add, as the ENGINE reported it. This used to be a
  // bare `added` boolean set unconditionally, so the page said "Added to cart"
  // over a cart that had not changed — the same failure ProductDetail.jsx was
  // fixed for. A refusal has to look like a refusal.
  const [result, setResult] = useState(null);

  // A custom amount is only an amount once it is a whole number in range.
  // Clamping silently (the old Math.min/Math.max pair, applied twice) turned a
  // typo into a purchase: "abc" became $1 and "5000" became $2000, and the
  // annotator was billed for a card they never chose.
  const customTrimmed = customText.trim();
  const customUsd = /^\d+$/.test(customTrimmed) ? Number(customTrimmed) : null;
  const customValid =
    customUsd !== null && customUsd >= MIN_USD && customUsd <= MAX_USD;
  const customError = customTrimmed !== '' && !customValid
    ? `Enter a whole dollar amount between $${MIN_USD} and $${MAX_USD}.`
    : '';
  const amountUsd = customValid ? customUsd : presetUsd;
  const usingCustom = customTrimmed !== '';

  const recipientError = recipient.trim() !== '' && !recipient.includes('@')
    ? 'Enter a valid email address.'
    : '';

  // Recipient and message were collected and then dropped on the floor. The
  // engine's cart line has `gift_message`, which is where a gift note belongs and
  // — unlike this component's state — is part of the world, so a task can verify
  // that the right person was named. There is no separate recipient field, so
  // fold it into the note rather than invent one the engine cannot store.
  const giftNote = () => {
    const to = recipient.trim();
    const body = message.trim();
    if (to && body) return `To: ${to} — ${body}`;
    if (to) return `To: ${to}`;
    return body;
  };

  const handleAdd = () => {
    if (customError || recipientError) return;
    const show = (msg, bad) => {
      setResult({ msg, bad });
      clearTimeout(handleAdd._t);
      handleAdd._t = setTimeout(() => setResult(null), 4000);
    };
    const id = giftCardId(amountUsd);
    const note = giftNote();
    Promise.resolve(addToCart({
      id,
      title: `ShopGym Gift Card — $${amountUsd}`,
      price: amountUsd,
      image: '',
      category: 'Gift Cards',
      giftCard: true,
      inStock: true,
      stockCount: null,
    }, 1))
      .then(r => {
        if (r && r.ok === false) {
          show(r.error ? `Could not add the gift card — ${r.error}`
                       : 'Could not add the gift card', true);
          return null;
        }
        // Attach the note to the line that was just created. Only claim success
        // once this has landed too: a card that reaches the cart without the
        // message is not what the annotator asked for.
        if (!note) return show(`Added a $${amountUsd} gift card to your cart`, false);
        return Promise.resolve(setLineOptions(id, { gift_message: note }))
          .then(rr => (rr && rr.ok === false)
            ? show('Gift card added, but the message could not be saved', true)
            : show(`Added a $${amountUsd} gift card to your cart`, false));
      })
      .catch(() => show('Could not add the gift card', true));
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
              {PRESET_AMOUNTS_USD.map(a => (
                <button key={a} type="button" data-test-id={`gift-amount-${a}`}
                  onClick={() => { setPresetUsd(a); setCustomText(''); }}
                  aria-pressed={!usingCustom && presetUsd === a}
                  className={`px-4 py-2 rounded border text-sm font-medium ${!usingCustom && presetUsd === a ? 'bg-xmazon-orange border-xmazon-orange text-black' : 'bg-white border-gray-300 hover:border-gray-500'}`}>
                  ${a}
                </button>
              ))}
            </div>
            <div className="mt-3">
              <label className="block text-xs text-gray-600 mb-1">Or enter a custom amount</label>
              <input type="number" min={MIN_USD} max={MAX_USD} step="1"
                value={customText} placeholder="$"
                aria-label="Custom gift card amount" data-test-id="gift-custom-amount"
                onChange={e => setCustomText(e.target.value)}
                className="border rounded px-3 py-2 text-sm w-40 focus:outline-none focus:border-xmazon-orange" />
              {customError && (
                <p className="text-red-700 text-xs mt-1" role="alert">{customError}</p>
              )}
            </div>
          </div>
          <div>
            <label className="block text-sm font-bold mb-1">Recipient email</label>
            <input type="email" value={recipient} placeholder="name@example.com"
              aria-label="Recipient email" data-test-id="gift-recipient"
              onChange={e => setRecipient(e.target.value)}
              className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
            {recipientError && (
              <p className="text-red-700 text-xs mt-1" role="alert">{recipientError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-bold mb-1">Gift message (optional)</label>
            <textarea value={message} rows={3} onChange={e => setMessage(e.target.value)}
              aria-label="Gift message" data-test-id="gift-message"
              className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={handleAdd} aria-label="Add gift card to cart"
              data-test-id="gift-add-to-cart"
              disabled={!!customError || !!recipientError}>
              Add to Cart — ${amountUsd}
            </Button>
            {result && (
              <span role="status" data-test-id="gift-add-status"
                className={`text-sm ${result.bad ? 'text-red-700' : 'text-green-700'}`}>
                {result.msg}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
