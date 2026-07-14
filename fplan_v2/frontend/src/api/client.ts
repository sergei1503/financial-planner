import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token provider - will be set by ClerkTokenProvider component
let tokenProvider: (() => Promise<string | null>) | null = null;

export function setTokenProvider(provider: () => Promise<string | null>) {
  tokenProvider = provider;
}

// Active portfolio — sent as the X-Portfolio-Id header on every request so reads/writes
// are scoped to the selected portfolio. When null, the backend falls back to the user's
// default portfolio. Initialized from localStorage so a returning user's first requests
// already carry the right portfolio (the PortfolioProvider keeps it in sync thereafter).
const PORTFOLIO_STORAGE_KEY = 'fplan.activePortfolioId';

let activePortfolioId: number | null = (() => {
  try {
    const v = localStorage.getItem(PORTFOLIO_STORAGE_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
})();

export function setActivePortfolioId(id: number | null) {
  activePortfolioId = id;
  try {
    if (id == null) localStorage.removeItem(PORTFOLIO_STORAGE_KEY);
    else localStorage.setItem(PORTFOLIO_STORAGE_KEY, String(id));
  } catch {
    /* localStorage unavailable — header still works for the session */
  }
}

export function getActivePortfolioId(): number | null {
  return activePortfolioId;
}

// Request interceptor: attach auth token + active portfolio
apiClient.interceptors.request.use(async (config) => {
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  if (activePortfolioId != null) {
    config.headers['X-Portfolio-Id'] = String(activePortfolioId);
  }
  return config;
});

// Response interceptor: handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to sign-in on auth failure only if Clerk is enabled
      // and a token provider was set (i.e., user was previously signed in).
      // In demo mode (no token provider), don't redirect.
      if (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY && tokenProvider) {
        window.location.href = '/sign-in';
      }
    }
    if (error.response?.data?.detail) {
      error.message = error.response.data.detail;
    }
    return Promise.reject(error);
  }
);

export default apiClient;
