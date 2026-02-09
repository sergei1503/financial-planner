import { Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AppShell } from '@/components/layout/app-shell';
import { DashboardPage } from '@/features/dashboard/dashboard-page';
import { AssetsPage } from '@/features/assets/assets-page';
import { LoansPage } from '@/features/loans/loans-page';
import { CashFlowsPage } from '@/features/cash-flows/cash-flows-page';
import { ProjectionsPage } from '@/features/projections/projections-page';
import { SignInPage } from '@/features/auth/sign-in-page';
import { SignUpPage } from '@/features/auth/sign-up-page';

function App() {
  return (
    <>
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
      <Toaster position="top-center" dir="rtl" />
    </>
  );
}

export default App;
