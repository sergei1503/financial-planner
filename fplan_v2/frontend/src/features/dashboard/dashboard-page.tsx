import { useTranslation } from 'react-i18next';
import { PageContainer } from '@/components/layout/page-container';
import { usePortfolioSummary } from '@/hooks/use-portfolio';
import { formatCurrency } from '@/lib/formatters';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';

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


export function DashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = usePortfolioSummary();

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

    </PageContainer>
  );
}
