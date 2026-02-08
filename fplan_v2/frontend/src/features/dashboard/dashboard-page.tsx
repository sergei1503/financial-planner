import { useTranslation } from 'react-i18next';
import { PageContainer } from '@/components/layout/page-container';
import { usePortfolioSummary } from '@/hooks/use-portfolio';
import { useProjectionQuery } from '@/hooks/use-projections';
import { formatCurrency, formatDate } from '@/lib/formatters';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { LoanProjection, TimeSeriesDataPoint } from '@/api/types';

function KpiCard({
  title,
  value,
  colorClass,
}: {
  title: string;
  value: string;
  colorClass?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <span dir="ltr" className={`inline-block text-2xl font-bold ${colorClass ?? ''}`}>
          {value}
        </span>
      </CardContent>
    </Card>
  );
}

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <span className="text-xl font-semibold">{value}</span>
      </CardContent>
    </Card>
  );
}

function formatTooltipValue(value: number) {
  return new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS',
    maximumFractionDigits: 0,
  }).format(value);
}

function NetWorthSparkline({ data }: { data: TimeSeriesDataPoint[] }) {
  // Take last 24 data points for a compact view
  const recent = data.slice(-24).map(p => ({ value: p.value }));
  if (recent.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height={120}>
      <AreaChart data={recent} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
        <defs>
          <linearGradient id="nwGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#nwGradient)"
          dot={false}
        />
        <Tooltip
          formatter={(value) => formatTooltipValue(Number(value))}
          labelFormatter={() => ''}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function LoanPayoffTimeline({ loanProjections }: { loanProjections: LoanProjection[] }) {
  const { t } = useTranslation();

  const payoffData = loanProjections.map(loan => {
    // Find the first point where balance reaches 0 or the last point
    const zeroIdx = loan.balance_series.findIndex(p => p.value <= 0);
    const payoffPoint = zeroIdx >= 0 ? loan.balance_series[zeroIdx] : loan.balance_series[loan.balance_series.length - 1];
    const monthsRemaining = zeroIdx >= 0 ? zeroIdx : loan.balance_series.length;

    return {
      name: loan.loan_name,
      months: monthsRemaining,
      payoffDate: payoffPoint?.date ?? '',
      type: loan.loan_type,
    };
  }).sort((a, b) => a.months - b.months);

  if (payoffData.length === 0) return null;

  const COLORS: Record<string, string> = {
    fixed: '#3b82f6',
    prime_pegged: '#f59e0b',
    cpi_pegged: '#8b5cf6',
    variable: '#06b6d4',
  };

  return (
    <div className="space-y-3">
      {payoffData.map((loan) => {
        const maxMonths = Math.max(...payoffData.map(l => l.months));
        const pct = maxMonths > 0 ? (loan.months / maxMonths) * 100 : 100;
        return (
          <div key={loan.name} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{loan.name}</span>
              <span className="text-muted-foreground" dir="ltr">
                {loan.payoffDate ? formatDate(loan.payoffDate) : `${loan.months} ${t('projections.months_remaining')}`}
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  backgroundColor: COLORS[loan.type] ?? '#64748b',
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CashFlowTrend({ data }: { data: TimeSeriesDataPoint[] }) {
  const recent = data.slice(-24).map(p => ({
    value: p.value,
  }));
  if (recent.length < 2) return null;

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={recent} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
        <Tooltip
          formatter={(value) => formatTooltipValue(Number(value))}
          labelFormatter={() => ''}
        />
        <Bar dataKey="value">
          {recent.map((entry, idx) => (
            <rect key={idx} fill={entry.value >= 0 ? '#22c55e' : '#ef4444'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = usePortfolioSummary();
  const { data: projectionData, isLoading: projLoading } = useProjectionQuery();

  if (isLoading) {
    return (
      <PageContainer title={t('nav.dashboard')}>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="mt-6 grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-20" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-6 w-12" />
              </CardContent>
            </Card>
          ))}
        </div>
      </PageContainer>
    );
  }

  if (isError || !data) {
    return (
      <PageContainer title={t('nav.dashboard')}>
        <div className="flex flex-col items-center gap-4 py-8">
          <p className="text-destructive">{t('messages.error_loading')}</p>
          <Button variant="outline" onClick={() => refetch()}>
            {t('actions.retry')}
          </Button>
        </div>
      </PageContainer>
    );
  }

  const hasProjections = !!projectionData;
  const hasLoans = hasProjections && projectionData.loan_projections.length > 0;

  return (
    <PageContainer title={t('nav.dashboard')}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          title={t('dashboard.net_worth')}
          value={formatCurrency(data.net_worth)}
          colorClass="text-primary"
        />
        <KpiCard
          title={t('dashboard.total_assets')}
          value={formatCurrency(data.total_assets)}
          colorClass="text-green-600"
        />
        <KpiCard
          title={t('dashboard.total_liabilities')}
          value={formatCurrency(data.total_liabilities)}
          colorClass="text-red-600"
        />
        <KpiCard
          title={t('dashboard.monthly_cash_flow')}
          value={formatCurrency(data.monthly_net_cash_flow)}
          colorClass="text-blue-600"
        />
      </div>

      <div className="mt-6 grid grid-cols-3 gap-4">
        <StatCard title={t('dashboard.asset_count')} value={data.asset_count} />
        <StatCard title={t('dashboard.loan_count')} value={data.loan_count} />
        <StatCard
          title={t('dashboard.revenue_stream_count')}
          value={data.revenue_stream_count}
        />
      </div>

      {/* Projection widgets */}
      {projLoading && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-[120px]" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {hasProjections && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('projections.net_worth_trend')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <NetWorthSparkline data={projectionData.net_worth_series} />
            </CardContent>
          </Card>

          {hasLoans && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {t('projections.loan_payoff_timeline')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <LoanPayoffTimeline loanProjections={projectionData.loan_projections} />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t('projections.cash_flow_trend')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CashFlowTrend data={projectionData.monthly_cash_flow_series} />
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
