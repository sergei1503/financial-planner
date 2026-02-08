import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PageContainer } from '@/components/layout/page-container';
import { useAssets } from '@/hooks/use-assets';
import { useProjectionQuery } from '@/hooks/use-projections';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AssetBreakdownChart } from '@/features/projections/asset-breakdown-chart';
import { AssetForm } from './asset-form';
import { AssetList } from './asset-list';

export function AssetsPage() {
  const { t } = useTranslation();
  const { data: assets, isLoading, isError } = useAssets();
  const { data: projection } = useProjectionQuery();
  const [formOpen, setFormOpen] = useState(false);

  if (isLoading) {
    return (
      <PageContainer title={t('nav.assets')}>
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
      <PageContainer title={t('nav.assets')}>
        <p className="text-destructive">{t('messages.error_loading')}</p>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={t('nav.assets')}
      action={
        <Button onClick={() => setFormOpen(true)}>
          {t('actions.add_asset')}
        </Button>
      }
    >
      <AssetList assets={assets ?? []} />

      {projection?.asset_projections && projection.asset_projections.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>{t('projections.asset_breakdown')}</CardTitle>
          </CardHeader>
          <CardContent>
            <AssetBreakdownChart assetProjections={projection.asset_projections} />
          </CardContent>
        </Card>
      )}

      <AssetForm open={formOpen} onOpenChange={setFormOpen} />
    </PageContainer>
  );
}
