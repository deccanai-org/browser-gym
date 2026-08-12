import React, { useState, useEffect } from 'react';
import { useStore } from '../context/StoreContext';
import { gymNow, fmtDeliveryDate } from '../lib/mockData';
import { bridged, bridgeAct } from '../lib/bridge';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Search, Package, Truck, CheckCircle, Clock, X, MapPin } from 'lucide-react';

const STATUS_ICONS = {
  'Delivered': <CheckCircle size={16} className="text-green-600" />,
  'Shipped': <Truck size={16} className="text-blue-600" />,
  'Processing': <Clock size={16} className="text-orange-500" />,
  'Cancelled': <X size={16} className="text-red-500" />,
};

const STATUS_COLORS = {
  'Delivered': 'text-green-700',
  'Shipped': 'text-blue-700',
  'Processing': 'text-orange-600',
  'Cancelled': 'text-red-600',
};

const fmtLongDate = (d) =>
  new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

/** Infer limited-warranty window from product copy + order date vs gym clock. */
function warrantyInfo(product, orderDate, now) {
  if (!product || !orderDate) return null;
  const text = `${product.description || ''} ${(product.bulletPoints || []).join(' ')} ${product.title || ''}`;
  if (!/warranty|replace\s+polic/i.test(text)) return null;
  const purchased = new Date(orderDate);
  if (Number.isNaN(purchased.getTime())) return null;
  const dayMatch = text.match(/(\d+)\s*[- ]?\s*days?\b/i);
  const monthMatch = text.match(/(\d+)\s*[- ]?\s*months?\b/i);
  const ends = new Date(purchased);
  let windowLabel = null;
  let months = null;
  let days = null;
  if (dayMatch) {
    days = parseInt(dayMatch[1], 10);
    if (!days || days > 3660) return null;
    ends.setDate(ends.getDate() + days);
    windowLabel = `${days}-day`;
  } else if (monthMatch) {
    months = parseInt(monthMatch[1], 10);
    if (!months || months > 120) return null;
    ends.setMonth(ends.getMonth() + months);
    windowLabel = `${months}-month`;
  } else {
    return null;
  }
  const expired = now.getTime() >= ends.getTime();
  return {
    months,
    days,
    windowLabel,
    purchaseLabel: fmtLongDate(purchased),
    endsLabel: fmtLongDate(ends),
    expired,
    statusLabel: expired
      ? `Warranty expired (ended ${fmtLongDate(ends)})`
      : `Warranty active until ${fmtLongDate(ends)}`,
  };
}

function WarrantyBanner({ info, compact = false }) {
  if (!info) return null;
  return (
    <div
      data-test-id="warranty-status"
      className={`${compact ? 'text-xs mt-1' : 'text-sm mt-2'} rounded border px-2 py-1.5 ${
        info.expired
          ? 'bg-amber-50 border-amber-300 text-amber-900'
          : 'bg-green-50 border-green-300 text-green-900'
      }`}
    >
      <div className="font-semibold" data-test-id="warranty-status-label">{info.statusLabel}</div>
      <div className={compact ? 'text-[11px] opacity-90' : 'text-xs opacity-90'}>
        Purchased {info.purchaseLabel} · {info.windowLabel} limited warranty from purchase date
      </div>
    </div>
  );
}

export const Orders = () => {
  const { state, addToCart, cancelOrder, changeOrderAddress, changeOrderShipping, changeOrderItemVariant, createReturn } = useStore();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('orders');
  // Show everything by default. The window filters compare against the real
  // wall clock, but seeded orders carry the gym's frozen dates, so a 90-day
  // default hid every seeded order and "Your Orders" came up empty.
  const [timeFilter, setTimeFilter] = useState('all');
  const [orderSearch, setOrderSearch] = useState('');
  const [cancelConfirm, setCancelConfirm] = useState(null);
  const [trackingModal, setTrackingModal] = useState(null); // { orderId, trackingNumber }
  const [addressModal, setAddressModal] = useState(null); // order shippingAddress
  const [orderDetailModal, setOrderDetailModal] = useState(null); // order
  const [returnModal, setReturnModal] = useState(null); // { order, product }
  const [returnSubmitted, setReturnSubmitted] = useState({});
  const [addrChangeReason, setAddrChangeReason] = useState('');
  const [addrChangeTarget, setAddrChangeTarget] = useState('');
  const [addrChangeMsg, setAddrChangeMsg] = useState('');

  // Bridged: opening the orders page logs view_orders in the engine (milestones).
  useEffect(() => { if (bridged()) bridgeAct('shop.view_orders', {}); }, []);

  const now = new Date(gymNow(state));
  const threeMonthsAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
  const sixMonthsAgo = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000);
  const oneYearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);

  const getFilteredOrders = () => {
    let filtered = [...state.orders];

    if (timeFilter === 'past3months') {
      filtered = filtered.filter(o => new Date(o.date) >= threeMonthsAgo);
    } else if (timeFilter === 'past6months') {
      filtered = filtered.filter(o => new Date(o.date) >= sixMonthsAgo);
    } else if (timeFilter === 'past1year') {
      filtered = filtered.filter(o => new Date(o.date) >= oneYearAgo);
    }

    if (activeTab === 'notShipped') {
      filtered = filtered.filter(o => o.status === 'Processing' || o.status === 'Shipped');
    } else if (activeTab === 'cancelled') {
      filtered = filtered.filter(o => o.status === 'Cancelled');
    }

    if (orderSearch.trim()) {
      const q = orderSearch.toLowerCase();
      filtered = filtered.filter(o => {
        const hasMatchingItem = o.items.some(item => {
          const p = state.products.find(pr => pr.id === item.productId);
          return p && p.title.toLowerCase().includes(q);
        });
        return o.id.toLowerCase().includes(q) || hasMatchingItem;
      });
    }

    return filtered.sort((a, b) => new Date(b.date) - new Date(a.date));
  };

  const filteredOrders = getFilteredOrders();

  // Unique products from all past orders for "Buy Again" tab
  const buyAgainProducts = (() => {
    const seen = new Set();
    const products = [];
    for (const order of state.orders) {
      for (const item of order.items) {
        if (!seen.has(item.productId)) {
          const prod = state.products.find(p => p.id === item.productId);
          if (prod) {
            seen.add(item.productId);
            products.push(prod);
          }
        }
      }
    }
    return products;
  })();

  const handleCancelConfirm = (orderId) => {
    cancelOrder(orderId);
    setCancelConfirm(null);
  };

  const handleBuyAgain = (product) => {
    addToCart(product, 1);
    // Brief visual feedback — navigate to cart
    navigate('/cart');
  };

  const handleReturnSubmit = (e, orderId, productId) => {
    e.preventDefault();
    const form = e.target;
    createReturn({
      orderId, productId,
      reason: form.elements.reason?.value || '',
      notes: form.elements.notes?.value || '',
    });
    setReturnSubmitted(prev => ({ ...prev, [`${orderId}-${productId}`]: true }));
    setReturnModal(null);
  };

  return (
    <div className="bg-xmazon-bg min-h-screen">
      <div className="max-w-[1000px] mx-auto p-4">
        <h1 className="text-2xl font-medium mb-4">Your Orders</h1>

        {/* Primary tab navigation */}
        <div className="bg-white border rounded-t border-b-0 flex overflow-x-auto">
          {[
            { key: 'orders', label: 'Orders' },
            { key: 'buyAgain', label: 'Buy Again' },
            { key: 'notShipped', label: 'Not Yet Shipped' },
            { key: 'cancelled', label: 'Cancelled Orders' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`px-5 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === key
                  ? 'border-xmazon-orange text-xmazon-dark'
                  : 'border-transparent text-gray-600 hover:text-xmazon-dark hover:bg-gray-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Buy Again tab content */}
        {activeTab === 'buyAgain' ? (
          <div className="bg-white border border-t-0 rounded-b p-4">
            <h2 className="text-lg font-medium mb-4">Buy Again</h2>
            {buyAgainProducts.length === 0 ? (
              <div className="text-center py-8">
                <Package size={48} className="mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No past orders to show here.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {buyAgainProducts.map(prod => (
                  <div key={prod.id} className="border rounded p-3 flex flex-col gap-2 hover:shadow-md transition-shadow">
                    <Link to={`/product/${prod.id}`}>
                      <img src={prod.image} alt={prod.title} className="w-full h-32 object-contain" />
                    </Link>
                    <Link to={`/product/${prod.id}`} className="text-xs text-xmazon-blue hover:underline font-medium line-clamp-2">
                      {prod.title}
                    </Link>
                    <div className="text-sm font-bold">${prod.price.toFixed(2)}</div>
                    <button
                      onClick={() => { addToCart(prod, 1); navigate('/cart'); }}
                      className="bg-xmazon-yellow hover:bg-yellow-400 text-xmazon-dark text-xs font-medium py-1.5 px-3 rounded-full border border-yellow-500 transition-colors"
                    >
                      Add to Cart
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
        {/* Time filter tabs + search */}
        <div className="bg-white border border-t-0 p-4 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between border-b-0">
          <div className="flex flex-wrap gap-1">
            {[
              { key: 'past3months', label: 'past 3 months' },
              { key: 'past6months', label: 'past 6 months' },
              { key: 'past1year', label: 'past year' },
              { key: 'all', label: 'all orders' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTimeFilter(key)}
                className={`px-3 py-1.5 text-sm rounded border transition-colors ${
                  timeFilter === key
                    ? 'bg-xmazon text-white border-xmazon'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Order search */}
          <div className="relative flex-shrink-0">
            <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={orderSearch}
              onChange={e => setOrderSearch(e.target.value)}
              placeholder="Search your orders"
              className="pl-7 pr-3 py-1.5 border rounded text-sm focus:outline-none focus:border-xmazon-orange w-56"
            />
          </div>
        </div>

        <div className="text-sm text-gray-600 bg-white px-4 py-2 border-x border-b mb-4 rounded-b">
          {filteredOrders.length} {filteredOrders.length === 1 ? 'order' : 'orders'} placed in
          {timeFilter === 'all' ? ' all time' : timeFilter === 'past3months' ? ' past 3 months' : timeFilter === 'past6months' ? ' past 6 months' : ' past year'}
        </div>

        {filteredOrders.length === 0 ? (
          <div className="bg-white p-8 border rounded text-center">
            <Package size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-lg font-medium mb-2">No orders found</p>
            {orderSearch ? (
              <p className="text-gray-500 text-sm mb-4">No orders match "{orderSearch}"</p>
            ) : (
              <p className="text-gray-500 text-sm mb-4">You haven't placed any orders in this time period.</p>
            )}
            <Link to="/" className="text-xmazon-blue hover:underline">Start shopping</Link>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredOrders.map(order => (
              <div key={order.id} className="border rounded bg-white overflow-hidden">
                {/* Order Header */}
                <div className="bg-gray-100 p-4 flex flex-wrap justify-between gap-4 text-sm text-gray-600">
                  <div className="flex flex-wrap gap-8">
                    <div>
                      <div className="uppercase text-xs font-bold text-gray-500 mb-0.5">ORDER PLACED</div>
                      <div>{new Date(order.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</div>
                      {order.items.map(item => {
                        const p = state.products.find(pr => pr.id === item.productId);
                        const w = warrantyInfo(p, order.date, now);
                        return w ? <WarrantyBanner key={`w-${item.productId}`} info={w} compact /> : null;
                      })}
                    </div>
                    <div>
                      <div className="uppercase text-xs font-bold text-gray-500 mb-0.5">TOTAL</div>
                      <div className="font-bold">${order.total.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="uppercase text-xs font-bold text-gray-500 mb-0.5">SHIP TO</div>
                      <button
                        className="text-xmazon-blue hover:underline cursor-pointer"
                        onClick={() => setAddressModal(order.shippingAddress)}
                      >
                        {order.shippingAddress.fullName}
                      </button>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="uppercase text-xs font-bold text-gray-500 mb-0.5">ORDER # {order.id}</div>
                    <button
                      className="text-xmazon-blue hover:underline block text-xs"
                      onClick={() => {
                        // the "agent actually opened this order" signal
                        if (bridged()) bridgeAct('shop.view_order', { order_id: order.id });
                        setOrderDetailModal(order);
                      }}
                    >
                      View order details
                    </button>
                    <button
                      className="text-xmazon-blue hover:underline block text-xs"
                      onClick={() => {
                        if (bridged()) bridgeAct('shop.view_order', { order_id: order.id });
                        setOrderDetailModal(order);
                      }}
                    >
                      Invoice
                    </button>
                  </div>
                </div>

                {/* Order Body */}
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-3">
                    {STATUS_ICONS[order.status] || <Package size={16} />}
                    <h3 className={`font-bold text-base ${STATUS_COLORS[order.status] || ''}`}>{order.status}</h3>
                    {order.refundStatus && (
                      <span
                        className="text-sm text-gray-600"
                        data-testid={`refund-status-${order.id}`}
                        data-test-id={`refund-status-${order.id}`}
                      >
                        — {order.refundStatus}
                      </span>
                    )}
                    {order.estimatedDelivery && order.status !== 'Delivered' && order.status !== 'Cancelled' && (
                      <span className="text-sm text-gray-600">
                        — Expected {fmtDeliveryDate(order.estimatedDelivery, { weekday: 'short', month: 'short', day: 'numeric' })}
                      </span>
                    )}
                    {order.trackingNumber && order.status === 'Shipped' && (
                      <button
                        className="ml-auto text-xs text-xmazon-blue hover:underline cursor-pointer"
                        onClick={() => { if (bridged()) bridgeAct('shop.view_tracking', { order_id: order.id }); setTrackingModal({ orderId: order.id, trackingNumber: order.trackingNumber }); }}
                      >
                        Track package
                      </button>
                    )}
                  </div>

                  {order.items.map(item => {
                    const product = state.products.find(p => p.id === item.productId);
                    if (!product) return null;
                    const returnKey = `${order.id}-${product.id}`;
                    return (
                      <div key={item.productId} className="flex gap-4 py-3 border-b last:border-0">
                        <Link to={`/product/${product.id}`}>
                          <img src={product.image} alt={product.title} className="w-20 h-20 object-contain flex-shrink-0" />
                        </Link>
                        <div className="flex-1">
                          <Link to={`/product/${product.id}`} className="font-bold text-xmazon-blue hover:underline text-sm line-clamp-2">
                            {product.title}
                          </Link>
                          <div className="text-xs text-gray-500 mt-1">Sold by: {product.brand}</div>
                          {item.quantity > 1 && (
                            <div className="text-xs text-gray-500">Qty: {item.quantity}</div>
                          )}
                          {(item.variantLabel || item.variantId) && (
                            <div className="text-xs text-gray-600 mt-1" data-test-id={`lbl-variant-${item.id || item.productId}`}>
                              Color / option: {item.variantLabel || item.variantId}
                            </div>
                          )}
                          {['Processing', 'Confirmed'].includes(order.status) && (item.availableVariants || []).length > 0 && (
                            <div className="mt-2 flex items-center gap-2">
                              <label className="text-xs text-gray-600">Change option</label>
                              <select
                                className="text-xs border rounded p-1"
                                data-test-id={`select-item-variant-${item.id || item.productId}`}
                                defaultValue={item.variantId || ''}
                                onChange={(e) => {
                                  const vid = e.target.value;
                                  if (vid && changeOrderItemVariant) {
                                    changeOrderItemVariant(order.id, item.id, vid);
                                  }
                                }}
                              >
                                {(item.availableVariants || []).map(v => (
                                  <option key={v.id} value={v.id}>{v.label || v.id}</option>
                                ))}
                              </select>
                            </div>
                          )}
                          <WarrantyBanner info={warrantyInfo(product, order.date, now)} compact />
                          <div className="flex flex-wrap gap-2 mt-2">
                            {order.status !== 'Cancelled' && (
                              <Button
                                variant="secondary"
                                className="text-xs py-1 px-3"
                                onClick={() => handleBuyAgain(product)}
                              >
                                Buy it again
                              </Button>
                            )}
                            <Button
                              variant="secondary"
                              className="text-xs py-1 px-3"
                              onClick={() => navigate(`/product/${product.id}`)}
                            >
                              View item
                            </Button>
                            {order.status === 'Delivered' && (
                              returnSubmitted[returnKey] ? (
                                <span className="text-xs text-green-700 py-1 px-3 border rounded border-green-300 bg-green-50">Return requested</span>
                              ) : (
                                <Button
                                  variant="secondary"
                                  className="text-xs py-1 px-3"
                                  onClick={() => setReturnModal({ order, product })}
                                >
                                  Return or replace items
                                </Button>
                              )
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Order actions */}
                  <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t">
                    {order.status === 'Processing' && (
                      <>
                        <div className="w-full text-xs text-gray-600 mb-1" data-testid={`order-shipping-speed-${order.id}`}>
                          Shipping: <span className="font-medium capitalize">{order.shippingSpeed || 'standard'}</span>
                          {order.estimatedDelivery && (
                            <span> · ETA {order.estimatedDelivery}</span>
                          )}
                        </div>
                        {(order.shippingSpeed || 'standard') === 'standard' && (
                          <button
                            type="button"
                            className="text-xmazon-blue hover:underline text-xs mr-3"
                            data-testid={`btn-upgrade-shipping-${order.id}`}
                            aria-label={`Upgrade shipping to express for ${order.id}`}
                            onClick={async () => {
                              // Express ETA is seeded on the order via estimatedDeliveryExpress when present.
                              const eta =
                                order.estimatedDeliveryExpress ||
                                order.expressEta ||
                                '';
                              await changeOrderShipping(order.id, 'express', eta);
                            }}
                          >
                            Upgrade to Express shipping
                          </button>
                        )}
                        {cancelConfirm === order.id ? (
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-gray-600">Cancel this order?</span>
                            <button
                              data-test-id={`btn-cancel-order-${order.id}`}
                              onClick={() => handleCancelConfirm(order.id)}
                              className="text-red-600 hover:underline font-bold text-xs"
                            >
                              Confirm Cancel
                            </button>
                            <button onClick={() => setCancelConfirm(null)} className="text-xmazon-blue hover:underline text-xs">
                              Keep Order
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setCancelConfirm(order.id)}
                            className="text-xmazon-blue hover:underline text-xs"
                            data-test-id={`btn-cancel-order-open-${order.id}`}
                          >
                            Cancel order
                          </button>
                        )}
                      </>
                    )}
                    {order.status === 'Shipped' && (
                      <span className="text-xs text-gray-500">
                        Tracking: <span className="font-mono text-gray-700">{order.trackingNumber}</span>
                      </span>
                    )}
                    {order.status === 'Delivered' && (
                      <div className="flex flex-wrap gap-2">
                        {order.items.map(item => {
                          const prod = state.products.find(p => p.id === item.productId);
                          if (!prod) return null;
                          return (
                            <Button
                              key={item.productId}
                              variant="secondary"
                              className="text-xs py-1 px-3"
                              onClick={() => navigate(`/product/${prod.id}#reviews`)}
                            >
                              Write a product review
                            </Button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        </>
        )}
      </div>

      {/* Tracking Modal */}
      {trackingModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setTrackingModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Track Your Package</h2>
              <button onClick={() => setTrackingModal(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded border border-blue-100">
                <Truck size={20} className="text-blue-600 flex-shrink-0" />
                <div>
                  <div className="font-bold text-blue-800">In Transit</div>
                  <div className="text-gray-600">Your package is on its way</div>
                </div>
              </div>
              <div>
                <span className="font-bold">Tracking number: </span>
                <span className="font-mono text-gray-700">{trackingModal.trackingNumber}</span>
              </div>
              <div className="space-y-2 mt-4">
                <div className="flex gap-3 items-start">
                  <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">Package picked up</div>
                    <div className="text-xs text-gray-500">Carrier facility</div>
                  </div>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">In transit to delivery facility</div>
                    <div className="text-xs text-gray-500">Expected delivery within 2 business days</div>
                  </div>
                </div>
              </div>
            </div>
            <button onClick={() => setTrackingModal(null)} className="mt-4 w-full bg-xmazon-yellow hover:bg-xmazon-darkYellow py-2 rounded font-bold text-sm">Close</button>
          </div>
        </div>
      )}

      {/* Shipping Address Modal */}
      {addressModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setAddressModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Shipping Address</h2>
              <button onClick={() => setAddressModal(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="flex gap-2 text-sm">
              <MapPin size={16} className="text-gray-500 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-bold">{addressModal.fullName}</div>
                <div>{addressModal.street}</div>
                <div>{addressModal.city}, {addressModal.state} {addressModal.zip}</div>
                <div>{addressModal.country}</div>
                {addressModal.phone && <div className="text-gray-500 mt-1">{addressModal.phone}</div>}
              </div>
            </div>
            <button onClick={() => setAddressModal(null)} className="mt-4 w-full bg-xmazon-yellow hover:bg-xmazon-darkYellow py-2 rounded font-bold text-sm">Close</button>
          </div>
        </div>
      )}

      {/* Order Detail Modal */}
      {orderDetailModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setOrderDetailModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Order Details</h2>
              <button onClick={() => setOrderDetailModal(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="font-bold text-gray-500 text-xs uppercase">Order #</span>
                <span className="font-mono text-xs">{orderDetailModal.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-gray-500 text-xs uppercase">Date Placed</span>
                <span>{new Date(orderDetailModal.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-gray-500 text-xs uppercase">Status</span>
                <span className={STATUS_COLORS[orderDetailModal.status] || ''}>{orderDetailModal.status}</span>
              </div>
              <div className="border-t pt-3" data-test-id="order-warranty-section">
                <div className="font-bold text-xs uppercase text-gray-500 mb-2">Warranty</div>
                {orderDetailModal.items.map(item => {
                  const p = state.products.find(pr => pr.id === item.productId);
                  const w = warrantyInfo(p, orderDetailModal.date, now);
                  if (!w) return null;
                  return (
                    <div key={`wd-${item.productId}`} className="mb-2">
                      <div className="text-xs text-gray-600 mb-0.5">{p?.title}</div>
                      <WarrantyBanner info={w} />
                    </div>
                  );
                })}
                {!orderDetailModal.items.some(item =>
                  warrantyInfo(state.products.find(pr => pr.id === item.productId), orderDetailModal.date, now)
                ) && (
                  <div className="text-xs text-gray-500">No limited-warranty terms on file for these items.</div>
                )}
              </div>
              <div className="border-t pt-3">
                <div className="font-bold text-xs uppercase text-gray-500 mb-2">Items Ordered</div>
                {orderDetailModal.items.map(item => {
                  const p = state.products.find(pr => pr.id === item.productId);
                  if (!p) return null;
                  return (
                    <div key={item.productId} className="flex gap-2 mb-2">
                      <img src={p.image} alt={p.title} className="w-12 h-12 object-contain flex-shrink-0" />
                      <div>
                        <div className="font-medium">{p.title}</div>
                        <div className="text-gray-500">Qty: {item.quantity} × ${p.price.toFixed(2)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="border-t pt-3 space-y-1">
                <div className="font-bold text-xs uppercase text-gray-500 mb-2">Shipping Address</div>
                <div>{orderDetailModal.shippingAddress.fullName}</div>
                <div>{orderDetailModal.shippingAddress.street}</div>
                <div>{orderDetailModal.shippingAddress.city}, {orderDetailModal.shippingAddress.state} {orderDetailModal.shippingAddress.zip}</div>
              </div>
              <div className="border-t pt-3" data-test-id="order-address-change-panel">
                <div className="font-bold text-xs uppercase text-gray-500 mb-2">Change delivery address</div>
                {(orderDetailModal.status === 'Out for Delivery' || orderDetailModal.status === 'Shipped' || orderDetailModal.status === 'Delivered' || orderDetailModal.status === 'Cancelled') ? (
                  <p className="text-xs text-gray-500" data-test-id="lbl-address-change-locked">
                    {orderDetailModal.status === 'Delivered'
                      ? 'Cannot change delivery address because this order has already been delivered.'
                      : `Address change is unavailable while this order is ${orderDetailModal.status}.`}
                  </p>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">Select a reason for the change to unlock the address picker, then save.</p>
                    <label className="block text-xs font-bold text-gray-600">Reason for change</label>
                    <select
                      data-test-id="select-address-change-reason"
                      value={addrChangeReason}
                      onChange={(e) => { setAddrChangeReason(e.target.value); setAddrChangeMsg(''); }}
                      className="w-full p-2 border rounded text-sm"
                    >
                      <option value="">Select a reason…</option>
                      <option value="moved">I moved / new home address</option>
                      <option value="wrong_address">Wrong address on the order</option>
                      <option value="gift_redirect">Redirect as a gift</option>
                      <option value="other">Other</option>
                    </select>
                    <label className="block text-xs font-bold text-gray-600">New ship-to address</label>
                    <select
                      data-test-id="select-order-new-address"
                      value={addrChangeTarget}
                      disabled={!addrChangeReason}
                      onChange={(e) => setAddrChangeTarget(e.target.value)}
                      className={`w-full p-2 border rounded text-sm ${!addrChangeReason ? 'opacity-50 bg-gray-100' : ''}`}
                    >
                      <option value="">Select address…</option>
                      {(state.user.addresses || []).map(a => (
                        <option key={a.id} value={a.id}>
                          {(a.label || a.name || a.id)} — {a.street || a.line1}, {a.city}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      data-test-id="btn-save-order-address"
                      disabled={!addrChangeReason || !addrChangeTarget}
                      className={`w-full py-2 rounded font-bold text-sm ${(!addrChangeReason || !addrChangeTarget) ? 'bg-gray-200 text-gray-500 opacity-50' : 'bg-xmazon-yellow hover:bg-xmazon-darkYellow'}`}
                      onClick={async () => {
                        const r = await changeOrderAddress(orderDetailModal.id, addrChangeTarget, addrChangeReason);
                        if (r && r.ok === false) {
                          setAddrChangeMsg(r.error || 'Could not change address.');
                          return;
                        }
                        setAddrChangeMsg('Delivery address updated.');
                        setOrderDetailModal(null);
                        setAddrChangeReason('');
                        setAddrChangeTarget('');
                      }}
                    >
                      Save new address
                    </button>
                    {addrChangeMsg && <p className="text-xs text-gray-600">{addrChangeMsg}</p>}
                  </div>
                )}
              </div>
              <div className="border-t pt-3 space-y-1">
                <div className="font-bold text-xs uppercase text-gray-500 mb-2">Payment</div>
                <div>{orderDetailModal.paymentMethod.brand} ending in {orderDetailModal.paymentMethod.last4}</div>
              </div>
              <div className="border-t pt-3 flex justify-between font-bold text-base">
                <span>Order Total</span>
                <span>${orderDetailModal.total.toFixed(2)}</span>
              </div>
            </div>
            <button onClick={() => setOrderDetailModal(null)} className="mt-4 w-full bg-xmazon-yellow hover:bg-xmazon-darkYellow py-2 rounded font-bold text-sm">Close</button>
          </div>
        </div>
      )}

      {/* Return Modal */}
      {returnModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setReturnModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold">Return or Replace Item</h2>
              <button onClick={() => setReturnModal(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="flex gap-3 mb-4 p-3 bg-gray-50 rounded border">
              <img src={returnModal.product.image} alt={returnModal.product.title} className="w-16 h-16 object-contain flex-shrink-0" />
              <div className="text-sm flex-1">
                <div className="font-medium line-clamp-2">{returnModal.product.title}</div>
                <div className="text-gray-500 mt-1">${returnModal.product.price.toFixed(2)}</div>
                <WarrantyBanner
                  info={warrantyInfo(returnModal.product, returnModal.order.date, now)}
                />
              </div>
            </div>
            <form onSubmit={(e) => handleReturnSubmit(e, returnModal.order.id, returnModal.product.id)} className="space-y-3">
              <div>
                <label className="block text-sm font-bold mb-1">Reason for return</label>
                <select name="reason" required className="w-full p-2 border rounded text-sm focus:outline-none focus:border-xmazon-orange">
                  <option value="">Select a reason</option>
                  <option value="defective">Defective/Doesn't work</option>
                  <option value="wrong-color">Wrong item/color</option>
                  <option value="wrong-item">Wrong item received</option>
                  <option value="not-needed">No longer needed</option>
                  <option value="not-as-described">Not as described</option>
                  <option value="damaged">Arrived damaged</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-bold mb-1">Comments (optional)</label>
                <textarea name="notes" className="w-full p-2 border rounded text-sm h-20 focus:outline-none focus:border-xmazon-orange" placeholder="Tell us more about the issue..." />
              </div>
              <div className="flex gap-2">
                <Button type="submit" className="flex-1">Submit Return Request</Button>
                <Button variant="secondary" type="button" onClick={() => setReturnModal(null)} className="flex-1">Cancel</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
