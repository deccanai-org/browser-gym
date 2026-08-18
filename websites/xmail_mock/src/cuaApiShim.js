// CUA-Gym-Hub API shim — injected by tools/inject-api-shim.mjs. Do not edit per-app.
//
// The mock apps call the state contract with relative paths (fetch('/state?sid=...')),
// which only works when the same server hosts both the SPA and the API. When the
// frontend is served from S3/CloudFront and the API is a separate backend, this shim
// redirects those calls to `${VITE_API_BASE}/api/${VITE_MOCK_ID}<path>`.
//
// With VITE_API_BASE unset/empty (local dev), the shim is a no-op and the app keeps
// talking to the vite middleware exactly as before.

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');
const MOCK_ID = import.meta.env.VITE_MOCK_ID || '';

const API_PATH_RE = /^\/(post|state|go|upload|files)(\/|\?|$)/;

if (API_BASE && MOCK_ID && typeof window !== 'undefined') {
  const rawFetch = window.fetch.bind(window);

  const rewrite = (path) => `${API_BASE}/api/${MOCK_ID}${path}`;

  window.fetch = (input, init) => {
    try {
      if (typeof input === 'string' && API_PATH_RE.test(input)) {
        return rawFetch(rewrite(input), init);
      }
      if (input instanceof URL && input.origin === window.location.origin
          && API_PATH_RE.test(input.pathname + input.search)) {
        return rawFetch(rewrite(input.pathname + input.search), init);
      }
      if (input instanceof Request) {
        const url = new URL(input.url);
        if (url.origin === window.location.origin && API_PATH_RE.test(url.pathname + url.search)) {
          return rawFetch(new Request(rewrite(url.pathname + url.search), input), init);
        }
      }
    } catch (e) {
      // fall through to the original request on any shim error
    }
    return rawFetch(input, init);
  };
}
