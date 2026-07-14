import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Analytics } from '@vercel/analytics/react';
import { Loader2 } from 'lucide-react';
import { AppShell } from '@/components/layout/app-shell';
import { SignInPage } from '@/features/auth/sign-in-page';
import { SignUpPage } from '@/features/auth/sign-up-page';

// Lazy-loaded authenticated pages for code splitting
const DashboardPage = lazy(() =>
  import('@/features/dashboard/dashboard-page').then(m => ({ default: m.DashboardPage }))
);
const AssetsPage = lazy(() =>
  import('@/features/assets/assets-page').then(m => ({ default: m.AssetsPage }))
);
const LoansPage = lazy(() =>
  import('@/features/loans/loans-page').then(m => ({ default: m.LoansPage }))
);
const CashFlowsPage = lazy(() =>
  import('@/features/cash-flows/cash-flows-page').then(m => ({ default: m.CashFlowsPage }))
);
const ProjectionsPage = lazy(() =>
  import('@/features/projections/projections-page').then(m => ({ default: m.ProjectionsPage }))
);

function App() {
  return (
    <>
      <Suspense
        fallback={
          <div className="flex items-center justify-center min-h-screen">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <Routes>
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/assets" element={<AssetsPage />} />
            <Route path="/loans" element={<LoansPage />} />
            <Route path="/cash-flows" element={<CashFlowsPage />} />
            <Route path="/projections" element={<ProjectionsPage />} />
          </Route>
        </Routes>
      </Suspense>
      <Toaster position="top-center" dir="rtl" />
      <Analytics />
    </>
  );
}

export default App;
