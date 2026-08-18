import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Headphones } from 'lucide-react';
import { useStore } from '../context/StoreContext';

const TOPICS = [
  ['Where is my order?', '/orders'],
  ['Return or replace items', '/orders'],
  ['Manage a subscription', '/subscriptions'],
  ['Payment & gift cards', '/gift-cards'],
];

// "Customer Service" in the top nav used to open the profile page. It now has a
// real help page: quick links to the relevant flows plus a contact form that
// persists a SupportTicket through the gym engine (bridged) so verifiers can
// read the claim text.
export const CustomerService = () => {
  const { createSupportTicket } = useStore();
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await createSupportTicket({ subject, body });
      setSent(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[900px] mx-auto p-4">
        <h1 className="text-2xl font-medium flex items-center gap-2 mb-4">
          <Headphones size={22} /> Customer Service
        </h1>
        <div className="bg-white border rounded p-6 mb-4">
          <h2 className="font-bold mb-3">What can we help you with?</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {TOPICS.map(([label, to]) => (
              <Link key={label} to={to} className="border rounded px-4 py-3 text-sm hover:border-gray-500 hover:bg-gray-50">
                {label}
              </Link>
            ))}
          </div>
        </div>
        <div className="bg-white border rounded p-6">
          <h2 className="font-bold mb-3">Contact us</h2>
          {sent ? (
            <div className="text-green-700 text-sm" role="status" data-testid="cs-sent">
              Thanks — your message was sent. Our team will reply to your account email.
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-3">
              <input value={subject} onChange={e => setSubject(e.target.value)} required
                aria-label="Subject" placeholder="Subject"
                data-testid="cs-subject"
                className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
              <textarea value={body} onChange={e => setBody(e.target.value)} required rows={4}
                aria-label="Message" placeholder="Describe your issue"
                data-testid="cs-body"
                className="border rounded px-3 py-2 text-sm w-full focus:outline-none focus:border-xmazon-orange" />
              <Button type="submit" aria-label="Send message" disabled={submitting}>
                Send message
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
