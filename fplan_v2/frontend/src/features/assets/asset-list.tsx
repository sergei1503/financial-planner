import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Search, ClipboardList, History, Plus, Edit2 } from 'lucide-react';
import type { AssetResponse, CashFlowResponse } from '@/api/types';
import { LogValueDialog } from '@/components/shared/log-value-dialog';
import { MeasurementHistoryDialog } from '@/components/shared/measurement-history-dialog';
import { useDeleteAsset } from '@/hooks/use-assets';
import { useCashFlows } from '@/hooks/use-cash-flows';
import { formatCurrency, formatPercent, formatDate } from '@/lib/formatters';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { AssetForm } from './asset-form';
import { CashFlowForm } from '@/features/cash-flows/cash-flow-form';

interface AssetListProps {
  assets: AssetResponse[];
}

export function AssetList({ assets }: AssetListProps) {
  const { t } = useTranslation();
  const deleteMutation = useDeleteAsset();
  const { data: allCashFlows } = useCashFlows();
  const [editAsset, setEditAsset] = useState<AssetResponse | undefined>();
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [logAsset, setLogAsset] = useState<AssetResponse | null>(null);
  const [historyAsset, setHistoryAsset] = useState<AssetResponse | null>(null);
  const [cashFlowForm, setCashFlowForm] = useState<{ asset: AssetResponse; cashFlow?: CashFlowResponse } | null>(null);

  const filtered = useMemo(() => {
    if (!search.trim()) return assets;
    const q = search.trim().toLowerCase();
    return assets.filter(a =>
      a.name.toLowerCase().includes(q) ||
      a.asset_type.toLowerCase().includes(q)
    );
  }, [assets, search]);

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success(t('messages.asset_deleted'));
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteId(null);
  }

  function getAssetCashFlows(assetId: number): CashFlowResponse[] {
    return allCashFlows?.filter(cf => cf.target_asset_id === assetId && cf.amount > 0) ?? [];
  }

  function hasSellDate(asset: AssetResponse): boolean {
    return !!asset.sell_date && asset.sell_date !== '2100-01-01';
  }

  if (assets.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        {t('table.no_assets')}
      </p>
    );
  }

  return (
    <>
      <div className="mb-4 relative max-w-sm">
        <Search className="absolute start-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder={t('placeholders.search')}
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="ps-9"
        />
      </div>
      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8"></TableHead>
              <TableHead>{t('fields.name')}</TableHead>
              <TableHead>{t('fields.type')}</TableHead>
              <TableHead>{t('fields.current_value')}</TableHead>
              <TableHead>{t('fields.appreciation_rate')}</TableHead>
              <TableHead>{t('fields.currency')}</TableHead>
              <TableHead>{t('table.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((asset) => {
              const cashFlows = getAssetCashFlows(asset.id);
              const hasDetails = cashFlows.length > 0 || hasSellDate(asset);
              const isExpanded = expandedId === asset.id;

              return (
                <>
                  <TableRow
                    key={asset.id}
                    className={hasDetails ? 'cursor-pointer' : ''}
                    onClick={() => hasDetails && setExpandedId(isExpanded ? null : asset.id)}
                  >
                    <TableCell className="w-8 text-center text-muted-foreground">
                      {hasDetails ? (isExpanded ? '▾' : '▸') : ''}
                    </TableCell>
                    <TableCell className="font-medium">{asset.name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {t(`asset_types.${asset.asset_type}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span dir="ltr" className="inline-block">
                        {formatCurrency(asset.current_value ?? asset.original_value, asset.currency)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span dir="ltr" className="inline-block">
                        {formatPercent(asset.appreciation_rate_annual_pct)}
                      </span>
                    </TableCell>
                    <TableCell>{asset.currency}</TableCell>
                    <TableCell>
                      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setLogAsset(asset)}
                          title={t('actions.record_measurement')}
                        >
                          <ClipboardList className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setHistoryAsset(asset)}
                          title={t('measurements.history')}
                        >
                          <History className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditAsset(asset)}
                        >
                          {t('actions.edit')}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => setDeleteId(asset.id)}
                        >
                          {t('actions.delete')}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>

                  {/* Expanded details row */}
                  {isExpanded && (
                    <TableRow key={`${asset.id}-details`} className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={7} className="p-0">
                        <div className="px-6 py-3 ps-12 space-y-2 text-sm">
                          {/* Sell date info */}
                          {hasSellDate(asset) && (
                            <div className="flex gap-4 items-center">
                              <Badge variant="outline" className="text-xs">
                                {t('fields.sell_date') || 'מועד מכירה'}
                              </Badge>
                              <span dir="ltr" className="inline-block">
                                {formatDate(asset.sell_date!)}
                              </span>
                              {asset.sell_tax > 0 && (
                                <span className="text-muted-foreground">
                                  ({t('fields.sell_tax') || 'מס מכירה'}: <span dir="ltr">{formatPercent(asset.sell_tax)}</span>)
                                </span>
                              )}
                            </div>
                          )}

                          {/* Cash flows (deposits/withdrawals) */}
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground font-medium">
                                {t('cash_flows.deposits') || 'הפקדות'}:
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setCashFlowForm({ asset });
                                }}
                              >
                                <Plus className="size-4 me-1" />
                                {t('actions.add_revenue_stream')}
                              </Button>
                            </div>
                            {cashFlows.length > 0 && (
                              <div className="space-y-1">
                                {cashFlows.map(cf => {
                                  // Determine badge label and style based on source
                                  const isOwnCapital = cf.from_own_capital;
                                  const badgeLabel = cf.flow_type === 'deposit'
                                    ? (isOwnCapital
                                        ? (t('cash_flows.own_capital') || 'Own Capital')
                                        : (t('cash_flows.employer') || 'Employer'))
                                    : (t('cash_flows.withdrawal') || 'Withdrawal');

                                  // Style badges: own capital = expense (red), employer = income (green)
                                  const badgeVariant = isOwnCapital ? 'destructive' : 'default';

                                  return (
                                    <div key={cf.id} className="flex gap-4 items-center ps-4 group">
                                      <Badge variant={badgeVariant} className="text-xs">
                                        {badgeLabel}
                                      </Badge>
                                      <span>{cf.name}</span>
                                      <span dir="ltr" className="inline-block font-medium">
                                        {formatCurrency(cf.amount, 'ILS')}/{t('period.monthly') || 'חודשי'}
                                      </span>
                                      <span className="text-muted-foreground">
                                        <span dir="ltr">{formatDate(cf.from_date)}</span>
                                        {' — '}
                                        <span dir="ltr">{formatDate(cf.to_date)}</span>
                                      </span>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setCashFlowForm({ asset, cashFlow: cf });
                                        }}
                                      >
                                        <Edit2 className="size-3" />
                                      </Button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <AssetForm
        open={!!editAsset}
        onOpenChange={(open) => {
          if (!open) setEditAsset(undefined);
        }}
        asset={editAsset}
      />

      <AlertDialog
        open={deleteId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('actions.delete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('messages.confirm_delete')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('actions.cancel')}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete}>
              {t('actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <LogValueDialog
        open={!!logAsset}
        onOpenChange={(open) => { if (!open) setLogAsset(null); }}
        entityType="asset"
        entityId={logAsset?.id ?? 0}
        entityName={logAsset?.name ?? ''}
      />

      <MeasurementHistoryDialog
        open={!!historyAsset}
        onOpenChange={(open) => { if (!open) setHistoryAsset(null); }}
        entityType="asset"
        entityId={historyAsset?.id ?? 0}
        entityName={historyAsset?.name ?? ''}
      />

      <CashFlowForm
        open={!!cashFlowForm}
        onOpenChange={(open) => {
          if (!open) setCashFlowForm(null);
        }}
        cashFlow={cashFlowForm?.cashFlow}
        initialAssetId={cashFlowForm?.asset.id}
      />
    </>
  );
}
