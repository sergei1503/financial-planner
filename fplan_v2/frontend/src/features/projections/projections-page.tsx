import { useEffect, useState, lazy, Suspense, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, History, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { PageContainer } from '@/components/layout/page-container';
import { EmptyState } from '@/components/shared/empty-state';
import { DatePicker } from '@/components/shared/date-picker';
import { ScenarioPanel } from './scenario-panel';
import { useProjectionQuery, useRunProjection } from '@/hooks/use-projections';
import type { ProjectionResponse } from '@/api/types';

const NetWorthChart = lazy(() =>
  import('./net-worth-chart').then(m => ({ default: m.NetWorthChart }))
);

const CashFlowChart = lazy(() =>
  import('./cash-flow-chart').then(m => ({ default: m.CashFlowChart }))
);

const AssetBreakdownChart = lazy(() =>
  import('./asset-breakdown-chart').then(m => ({ default: m.AssetBreakdownChart }))
);

const LoanAmortizationChart = lazy(() =>
  import('./loan-amortization-chart').then(m => ({ default: m.LoanAmortizationChart }))
);

const LoanPaymentChart = lazy(() =>
  import('./loan-payment-chart').then(m => ({ default: m.LoanPaymentChart }))
);

export function ProjectionsPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useProjectionQuery();
  const { mutate: runHistorical, data: historicalData, isPending: isHistoricalPending } = useRunProjection();
  const [historicalDate, setHistoricalDate] = useState<Date | undefined>(undefined);
  const [currentProjection, setCurrentProjection] = useState(data);
  const [historicalProjection, setHistoricalProjection] = useState<typeof data | undefined>(undefined);
  const [scenarioProjection, setScenarioProjection] = useState<ProjectionResponse | undefined>(undefined);
  const [scenarioName, setScenarioName] = useState<string | undefined>(undefined);

  // Update current projection when data changes
  useEffect(() => {
    if (data && !data.is_historical) {
      setCurrentProjection(data);
    }
  }, [data]);

  // Update historical projection when historical data arrives
  useEffect(() => {
    if (historicalData && historicalData.is_historical) {
      setHistoricalProjection(historicalData);
    }
  }, [historicalData]);

  const handleRunHistoricalProjection = () => {
    if (historicalDate) {
      runHistorical({ as_of_date: historicalDate.toISOString().split('T')[0] });
    }
  };

  const handleClearHistorical = () => {
    setHistoricalDate(undefined);
    setHistoricalProjection(undefined);
  };

  const displayData = currentProjection || data;
  const hasHistorical = historicalProjection !== undefined;
  const hasLoans = displayData?.loan_projections && displayData.loan_projections.length > 0;

  const handleScenarioProjection = useCallback((data: ProjectionResponse | undefined, name?: string) => {
    setScenarioProjection(data);
    setScenarioName(name);
  }, []);

  return (
    <PageContainer
      title={t('common.projections')}
      action={
        <div className="flex gap-2">
          <Button onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`size-4 me-2 ${isLoading ? 'animate-spin' : ''}`} />
            {t('projections.refresh')}
          </Button>
        </div>
      }
    >
      {/* Historical Projection Controls */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="size-5" />
            {t('projections.historical_projection')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            <DatePicker
              date={historicalDate}
              onDateChange={setHistoricalDate}
              placeholder={t('projections.select_past_date')}
              maxDate={new Date()}
            />
            <Button
              onClick={handleRunHistoricalProjection}
              disabled={!historicalDate || isHistoricalPending}
              variant="secondary"
            >
              <History className="size-4 me-2" />
              {t('projections.run_historical')}
            </Button>
            {hasHistorical && (
              <>
                <Badge variant="outline" className="flex items-center gap-2">
                  {t('projections.historical_mode')}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0"
                    onClick={handleClearHistorical}
                  >
                    <X className="size-3" />
                  </Button>
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {t('projections.comparing_to')}: {historicalProjection?.historical_as_of_date}
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>
      {/* Scenario Simulation */}
      <ScenarioPanel onScenarioProjection={handleScenarioProjection} />

      {isLoading && !displayData ? (
        <div className="space-y-6">
          <Skeleton className="h-[400px] w-full" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-[300px]" />
            <Skeleton className="h-[300px]" />
          </div>
        </div>
      ) : isError ? (
        <div className="text-center py-8">
          <p className="text-destructive">{t('messages.error_loading')}</p>
          <Button variant="outline" className="mt-4" onClick={() => refetch()}>
            {t('actions.retry')}
          </Button>
        </div>
      ) : !displayData || (displayData.asset_projections.length === 0 && displayData.loan_projections.length === 0) ? (
        <EmptyState message={t('projections.no_data')} />
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('projections.net_worth_over_time')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                <NetWorthChart
                  netWorth={displayData.net_worth_series}
                  totalAssets={displayData.total_assets_series}
                  totalLiabilities={displayData.total_liabilities_series}
                  measurementMarkers={displayData.measurement_markers}
                  historicalNetWorth={historicalProjection?.net_worth_series}
                  historicalAsOfDate={historicalProjection?.historical_as_of_date}
                  scenarioNetWorth={scenarioProjection?.net_worth_series}
                  scenarioTotalAssets={scenarioProjection?.total_assets_series}
                  scenarioTotalLiabilities={scenarioProjection?.total_liabilities_series}
                  scenarioName={scenarioName}
                />
              </Suspense>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>{t('projections.cash_flow_over_time')}</CardTitle>
              </CardHeader>
              <CardContent>
                <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                  <CashFlowChart
                    data={displayData.monthly_cash_flow_series}
                    breakdown={displayData.cash_flow_breakdown}
                    historicalData={historicalProjection?.monthly_cash_flow_series}
                    scenarioBreakdown={scenarioProjection?.cash_flow_breakdown}
                    scenarioName={scenarioName}
                  />
                </Suspense>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('projections.asset_breakdown')}</CardTitle>
              </CardHeader>
              <CardContent>
                <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                  <AssetBreakdownChart
                    assetProjections={displayData.asset_projections}
                    historicalAssetProjections={historicalProjection?.asset_projections}
                    scenarioAssetProjections={scenarioProjection?.asset_projections}
                    scenarioName={scenarioName}
                  />
                </Suspense>
              </CardContent>
            </Card>
          </div>

          {hasLoans && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>{t('projections.loan_balance_over_time')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                    <LoanAmortizationChart
                      loanProjections={displayData.loan_projections}
                      historicalLoanProjections={historicalProjection?.loan_projections}
                      scenarioLoanProjections={scenarioProjection?.loan_projections}
                      scenarioName={scenarioName}
                    />
                  </Suspense>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('projections.loan_payments_over_time')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                    <LoanPaymentChart
                      loanProjections={displayData.loan_projections}
                      scenarioLoanProjections={scenarioProjection?.loan_projections}
                      scenarioName={scenarioName}
                    />
                  </Suspense>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}
    </PageContainer>
  );
}
