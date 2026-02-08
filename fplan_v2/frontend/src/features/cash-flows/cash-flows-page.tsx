import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageContainer } from '@/components/layout/page-container';
import { CashFlowChart } from '@/features/projections/cash-flow-chart';
import { useProjectionQuery } from '@/hooks/use-projections';
import { useRevenueStreams } from '@/hooks/use-revenue-streams';
import { useCashFlows } from '@/hooks/use-cash-flows';
import { UnifiedCashFlowTable } from './unified-cash-flow-table';
import { RevenueStreamForm } from './revenue-stream-form';
import { CashFlowForm } from './cash-flow-form';

export function CashFlowsPage() {
  const { t } = useTranslation();
  const { data: projection, isLoading: projLoading, isError: projError, refetch } = useProjectionQuery();
  const { data: revenueStreams, isLoading: streamsLoading } = useRevenueStreams();
  const { data: cashFlows, isLoading: cashFlowsLoading } = useCashFlows();

  const [showRevenueForm, setShowRevenueForm] = useState(false);
  const [showCashFlowForm, setShowCashFlowForm] = useState(false);

  const isLoading = projLoading || streamsLoading || cashFlowsLoading;

  return (
    <PageContainer title={t('nav.cash_flows')}>
      <div className="space-y-6">
        {/* Chart section */}
        {projLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : projError ? (
          <div className="text-center py-8">
            <p className="text-destructive">{t('messages.failed_to_load_projections')}</p>
            <Button variant="outline" className="mt-4" onClick={() => refetch()}>
              {t('actions.retry')}
            </Button>
          </div>
        ) : projection?.cash_flow_breakdown ? (
          <div className="rounded-lg border bg-card p-4">
            <h3 className="text-lg font-semibold mb-4">
              {t('charts.cash_flow_over_time')}
            </h3>
            <CashFlowChart
              data={projection.monthly_cash_flow_series}
              breakdown={projection.cash_flow_breakdown}
            />
          </div>
        ) : null}

        {/* Add buttons */}
        <div className="flex gap-2 justify-end">
          <Button onClick={() => setShowRevenueForm(true)}>
            <Plus className="size-4 me-1" />
            {t('actions.add_revenue_stream')}
          </Button>
          <Button onClick={() => setShowCashFlowForm(true)}>
            <Plus className="size-4 me-1" />
            {t('actions.add_cash_flow')}
          </Button>
        </div>

        {/* Unified table */}
        {isLoading ? (
          <Skeleton className="h-[200px] w-full" />
        ) : (
          <UnifiedCashFlowTable
            revenueStreams={revenueStreams ?? []}
            cashFlows={cashFlows ?? []}
            breakdownItems={projection?.cash_flow_breakdown?.items ?? []}
          />
        )}

        {/* Forms */}
        <RevenueStreamForm
          open={showRevenueForm}
          onOpenChange={setShowRevenueForm}
        />
        <CashFlowForm
          open={showCashFlowForm}
          onOpenChange={setShowCashFlowForm}
        />
      </div>
    </PageContainer>
  );
}
