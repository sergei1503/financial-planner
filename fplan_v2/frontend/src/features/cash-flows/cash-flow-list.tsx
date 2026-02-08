import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { CashFlowResponse } from '@/api/types';
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
import { CashFlowForm } from './cash-flow-form';

interface CashFlowListProps {
  cashFlows: CashFlowResponse[];
}

export function CashFlowList({ cashFlows }: CashFlowListProps) {
  const { t } = useTranslation();
  const deleteMutation = useDeleteCashFlow();
  const { data: assets } = useAssets();
  const [editCashFlow, setEditCashFlow] = useState<CashFlowResponse | undefined>();
  const [deleteId, setDeleteId] = useState<number | null>(null);

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success(t('messages.cash_flow_deleted'));
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteId(null);
  }

  function getAssetName(assetId: number | null): string {
    if (!assetId) return t('cashFlow.noLink');
    const asset = assets?.find(a => a.id === assetId);
    return asset?.name ?? `#${assetId}`;
  }

  // Filter out employer deposits — only show own-capital flows
  const visibleFlows = cashFlows.filter(cf => cf.flow_type !== 'deposit' || cf.from_own_capital);

  if (visibleFlows.length === 0) {
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
              <TableHead>{t('fields.start_date')}</TableHead>
              <TableHead>{t('fields.end_date')}</TableHead>
              <TableHead>{t('cash_flows.deposit_origin')}</TableHead>
              <TableHead>{t('table.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleFlows.map((cf) => (
              <TableRow key={cf.id}>
                <TableCell className="font-medium">{cf.name}</TableCell>
                <TableCell>
                  <Badge variant={cf.flow_type === 'deposit' ? 'default' : 'destructive'}>
                    {t(`cash_flows.${cf.flow_type}`)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatCurrency(cf.amount, 'ILS')}
                  </span>
                </TableCell>
                <TableCell>{getAssetName(cf.target_asset_id)}</TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">{formatDate(cf.from_date)}</span>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">{formatDate(cf.to_date)}</span>
                </TableCell>
                <TableCell>
                  {cf.flow_type === 'deposit' && (
                    <Badge variant={cf.from_own_capital ? 'destructive' : 'default'}>
                      {cf.from_own_capital ? t('cash_flows.own_capital') : t('cash_flows.employer')}
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditCashFlow(cf)}
                    >
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => setDeleteId(cf.id)}
                    >
                      {t('actions.delete')}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <CashFlowForm
        open={!!editCashFlow}
        onOpenChange={(open) => {
          if (!open) setEditCashFlow(undefined);
        }}
        cashFlow={editCashFlow}
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
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={handleDelete}>
              {t('actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
