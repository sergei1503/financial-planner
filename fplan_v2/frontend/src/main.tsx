import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ClerkProvider, useAuth } from '@clerk/clerk-react';
import { ClerkTokenProvider } from '@/components/clerk-token-provider';
import { DemoProvider } from '@/contexts/demo-context';
import App from './App';
import './i18n';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

// Set initial direction
document.documentElement.dir = 'rtl';
document.documentElement.lang = 'he';

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

/** Reads Clerk auth state and provides DemoProvider accordingly. */
function ClerkDemoGate({ children }: { children: React.ReactNode }) {
  const { isSignedIn } = useAuth();
  return <DemoProvider isDemo={!isSignedIn}>{children}</DemoProvider>;
}

const AppTree = (
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  clerkPubKey ? (
    <ClerkProvider publishableKey={clerkPubKey} afterSignOutUrl="/">
      <ClerkTokenProvider>
        <ClerkDemoGate>
          {AppTree}
        </ClerkDemoGate>
      </ClerkTokenProvider>
    </ClerkProvider>
  ) : (
    <DemoProvider isDemo={false}>
      {AppTree}
    </DemoProvider>
  )
);
