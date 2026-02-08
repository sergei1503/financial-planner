import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageContainer } from '@/components/layout/page-container';
import { useLoans } from '@/hooks/use-loans';
import { useProjectionQuery } from '@/hooks/use-projections';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoanAmortizationChart } from '@/features/projections/loan-amortization-chart';
import { LoanPaymentChart } from '@/features/projections/loan-payment-chart';
import { LoanForm } from './loan-form';
import { LoanList } from './loan-list';

export function LoansPage() {
  const { t } = useTranslation();
  const { data: loans, isLoading, isError } = useLoans();
  const { data: projection } = useProjectionQuery();
  const [formOpen, setFormOpen] = useState(false);

  const hasLoanProjections = projection?.loan_projections && projection.loan_projections.length > 0;

  if (isLoading) {
    return (
      <PageContainer title={t('nav.loans')}>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </PageContainer>
    );
  }

  if (isError) {
    return (
      <PageContainer title={t('nav.loans')}>
        <p className="text-destructive">{t('messages.error_loading')}</p>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={t('nav.loans')}
      action={
        <Button onClick={() => setFormOpen(true)}>
          {t('actions.add_loan')}
        </Button>
      }
    >
      <LoanList loans={loans ?? []} />

      {hasLoanProjections && (
        <div className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('projections.loan_balance_over_time')}</CardTitle>
            </CardHeader>
            <CardContent>
              <LoanAmortizationChart loanProjections={projection!.loan_projections} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('projections.loan_payments_over_time')}</CardTitle>
            </CardHeader>
            <CardContent>
              <LoanPaymentChart loanProjections={projection!.loan_projections} />
            </CardContent>
          </Card>
        </div>
      )}

      <LoanForm open={formOpen} onOpenChange={setFormOpen} />
    </PageContainer>
  );
}
