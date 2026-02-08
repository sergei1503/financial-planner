import { Routes, Route } from 'react-router-dom';
import { SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';
import { Toaster } from 'sonner';
import { AppShell } from '@/components/layout/app-shell';
import { DashboardPage } from '@/features/dashboard/dashboard-page';
import { AssetsPage } from '@/features/assets/assets-page';
import { LoansPage } from '@/features/loans/loans-page';
import { CashFlowsPage } from '@/features/cash-flows/cash-flows-page';
import { ProjectionsPage } from '@/features/projections/projections-page';
import { SignInPage } from '@/features/auth/sign-in-page';
import { SignUpPage } from '@/features/auth/sign-up-page';

const clerkEnabled = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!clerkEnabled) return <>{children}</>;
  return (
    <>
      <SignedIn>{children}</SignedIn>
      <SignedOut>
        <RedirectToSignIn />
      </SignedOut>
    </>
  );
}

function App() {
  return (
    <>
      <Routes>
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />
        <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/loans" element={<LoansPage />} />
          <Route path="/cash-flows" element={<CashFlowsPage />} />
          <Route path="/projections" element={<ProjectionsPage />} />
        </Route>
      </Routes>
      <Toaster position="top-center" dir="rtl" />
    </>
  );
}

export default App;
