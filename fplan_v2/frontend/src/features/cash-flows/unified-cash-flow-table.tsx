import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ExternalLink } from 'lucide-react';
import type { RevenueStreamResponse, CashFlowResponse, CashFlowItem } from '@/api/types';
import { useDeleteRevenueStream } from '@/hooks/use-revenue-streams';
import { useDeleteCashFlow } from '@/hooks/use-cash-flows';
import { useAssets } from '@/hooks/use-assets';
import { formatCurrency, formatDate } from '@/lib/formatters';
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
import { RevenueStreamForm } from './revenue-stream-form';
import { CashFlowForm } from './cash-flow-form';

// Unified row type for the table
type RowKind = 'income' | 'deposit' | 'withdrawal' | 'loan_payment';

interface UnifiedRow {
  key: string;
  name: string;
  kind: RowKind;
  amount: number | null;
  linkedAsset: string;
  period: string;
  // Edit/delete support
  editableType?: 'revenue_stream' | 'cash_flow';
  sourceData?: RevenueStreamResponse | CashFlowResponse;
  // Navigation for projection items
  entityType?: 'asset' | 'loan' | null;
  entityId?: number | null;
}

interface UnifiedCashFlowTableProps {
  revenueStreams: RevenueStreamResponse[];
  cashFlows: CashFlowResponse[];
  breakdownItems: CashFlowItem[];
}

export function UnifiedCashFlowTable({ revenueStreams, cashFlows, breakdownItems }: UnifiedCashFlowTableProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: assets } = useAssets();
  const deleteRevenueMutation = useDeleteRevenueStream();
  const deleteCashFlowMutation = useDeleteCashFlow();

  const [editStream, setEditStream] = useState<RevenueStreamResponse | undefined>();
  const [editCashFlow, setEditCashFlow] = useState<CashFlowResponse | undefined>();
  const [deleteTarget, setDeleteTarget] = useState<{ type: 'revenue_stream' | 'cash_flow'; id: number } | null>(null);

  function getAssetName(assetId: number | null | undefined): string {
    if (!assetId) return '—';
    const asset = assets?.find(a => a.id === assetId);
    return asset?.name ?? `#${assetId}`;
  }

  // Build unified rows
  const rows = useMemo<UnifiedRow[]>(() => {
    const result: UnifiedRow[] = [];

    // Revenue streams → income rows
    for (const stream of revenueStreams) {
      if (stream.amount <= 0) continue;
      const startStr = formatDate(stream.start_date);
      const endStr = stream.end_date ? formatDate(stream.end_date) : '—';
      result.push({
        key: `rs-${stream.id}`,
        name: stream.name,
        kind: 'income',
        amount: stream.amount,
        linkedAsset: getAssetName(stream.asset_id),
        period: `${startStr} → ${endStr}`,
        editableType: 'revenue_stream',
        sourceData: stream,
      });
    }

    // Cash flows → deposit or withdrawal rows (filter out employer deposits)
    for (const cf of cashFlows) {
      if (cf.flow_type === 'deposit' && !cf.from_own_capital) continue;
      const startStr = formatDate(cf.from_date);
      const endStr = formatDate(cf.to_date);
      result.push({
        key: `cf-${cf.id}`,
        name: cf.name,
        kind: cf.flow_type === 'deposit' ? 'deposit' : 'withdrawal',
        amount: cf.amount,
        linkedAsset: getAssetName(cf.target_asset_id),
        period: `${startStr} → ${endStr}`,
        editableType: 'cash_flow',
        sourceData: cf,
      });
    }

    // Breakdown items from projections — only loan payments (others already covered above)
    for (const item of breakdownItems) {
      if (item.category !== 'loan_payment') continue;
      result.push({
        key: `proj-${item.source_name}`,
        name: item.source_name,
        kind: 'loan_payment',
        amount: null, // series data, no single amount
        linkedAsset: '—',
        period: '—',
        entityType: item.entity_type,
        entityId: item.entity_id,
      });
    }

    return result;
  }, [revenueStreams, cashFlows, breakdownItems, assets]);

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === 'revenue_stream') {
        await deleteRevenueMutation.mutateAsync(deleteTarget.id);
        toast.success(t('messages.revenue_stream_deleted'));
      } else {
        await deleteCashFlowMutation.mutateAsync(deleteTarget.id);
        toast.success(t('messages.cash_flow_deleted'));
      }
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteTarget(null);
  }

  function handleNavigate(entityType: 'asset' | 'loan', entityId: number) {
    if (entityType === 'asset') {
      navigate('/assets', { state: { scrollToId: entityId } });
    } else {
      navigate('/loans', { state: { scrollToId: entityId } });
    }
  }

  const kindBadgeVariant: Record<RowKind, 'default' | 'destructive' | 'secondary' | 'outline'> = {
    income: 'default',
    deposit: 'secondary',
    withdrawal: 'destructive',
    loan_payment: 'outline',
  };

  const kindLabel: Record<RowKind, string> = {
    income: t('cashFlow.income'),
    deposit: t('cash_flows.deposit'),
    withdrawal: t('cash_flows.withdrawal'),
    loan_payment: t('cashFlow.categories.loan_payment', 'Loan Payment'),
  };

  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        {t('table.no_cash_flows')}
      </p>
    );
  }

  return (
    <>
      <div className="rounded-lg border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('fields.name')}</TableHead>
              <TableHead>{t('fields.type')}</TableHead>
              <TableHead>{t('fields.amount')}</TableHead>
              <TableHead>{t('revenue.linked_asset')}</TableHead>
              <TableHead>{t('revenue.period')}</TableHead>
              <TableHead>{t('table.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.key}>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell>
                  <Badge variant={kindBadgeVariant[row.kind]}>
                    {kindLabel[row.kind]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {row.amount != null ? (
                    <span dir="ltr" className="inline-block">
                      {formatCurrency(row.amount, 'ILS')}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>{row.linkedAsset}</TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">{row.period}</span>
                </TableCell>
                <TableCell>
                  {row.editableType ? (
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (row.editableType === 'revenue_stream') {
                            setEditStream(row.sourceData as RevenueStreamResponse);
                          } else {
                            setEditCashFlow(row.sourceData as CashFlowResponse);
                          }
                        }}
                      >
                        {t('actions.edit')}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => {
                          const id = row.editableType === 'revenue_stream'
                            ? (row.sourceData as RevenueStreamResponse).id
                            : (row.sourceData as CashFlowResponse).id;
                          setDeleteTarget({ type: row.editableType!, id });
                        }}
                      >
                        {t('actions.delete')}
                      </Button>
                    </div>
                  ) : row.entityType && row.entityId ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleNavigate(row.entityType!, row.entityId!)}
                      className="gap-1"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {t('cashFlow.viewEntity')}
                    </Button>
                  ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Edit forms */}
      <RevenueStreamForm
        key={editStream?.id ?? 'new'}
        open={!!editStream}
        onOpenChange={(open) => {
          if (!open) setEditStream(undefined);
        }}
        revenueStream={editStream}
      />

      <CashFlowForm
        open={!!editCashFlow}
        onOpenChange={(open) => {
          if (!open) setEditCashFlow(undefined);
        }}
        cashFlow={editCashFlow}
      />

      {/* Delete confirmation */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
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
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={handleDelete}>
              {t('actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
