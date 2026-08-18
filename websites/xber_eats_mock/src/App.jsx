import React, { useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import CartPanel from './components/CartPanel';
import Footer from './components/Footer';
import Homepage from './pages/Homepage';
import StorePage from './pages/StorePage';
import SearchPage from './pages/SearchPage';
import Checkout from './pages/Checkout';
import Orders from './pages/Orders';
import OrderTracking from './pages/OrderTracking';
import Favorites from './pages/Favorites';
import Account from './pages/Account';
import Go from './pages/Go';

function RedirectToStore() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const query = searchParams.toString();
  return <Navigate to={query ? `/store/${id}?${query}` : `/store/${id}`} replace />;
}

function Layout({ children }) {
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const location = useLocation();

  if (location.pathname === '/go') {
    return children;
  }

  return (
    <div className="app-layout">
      <Header
        onCartClick={() => setIsCartOpen(true)}
        onMenuClick={() => setIsSidebarOpen(true)}
      />
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <CartPanel isOpen={isCartOpen} onClose={() => setIsCartOpen(false)} />
      <main className="app-main">{children}</main>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Homepage />} />
            <Route path="/store/:id" element={<StorePage />} />
            <Route path="/restaurant/:id" element={<RedirectToStore />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/orders/:orderId" element={<OrderTracking />} />
            <Route path="/favorites" element={<Favorites />} />
            <Route path="/account" element={<Account />} />
            <Route path="/go" element={<Go />} />
            {/* The cart is a drawer, not a page; a /cart deep-link used to hit no
                route and render a blank <main>. Send it to the full cart view. */}
            <Route path="/cart" element={<Navigate to="/checkout" replace />} />
            {/* Any stray gym path lands somewhere real instead of a blank page. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AppProvider>
  );
}
