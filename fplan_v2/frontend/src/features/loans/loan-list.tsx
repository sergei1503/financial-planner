import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Search, ClipboardList, History } from 'lucide-react';
import type { LoanResponse } from '@/api/types';
import { LogValueDialog } from '@/components/shared/log-value-dialog';
import { MeasurementHistoryDialog } from '@/components/shared/measurement-history-dialog';
import { useDeleteLoan } from '@/hooks/use-loans';
import { formatCurrency, formatPercent } from '@/lib/formatters';
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
import { LoanForm } from './loan-form';

interface LoanListProps {
  loans: LoanResponse[];
}

export function LoanList({ loans }: LoanListProps) {
  const { t } = useTranslation();
  const deleteMutation = useDeleteLoan();
  const [editLoan, setEditLoan] = useState<LoanResponse | undefined>();
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [logLoan, setLogLoan] = useState<LoanResponse | null>(null);
  const [historyLoan, setHistoryLoan] = useState<LoanResponse | null>(null);

  const filtered = useMemo(() => {
    if (!search.trim()) return loans;
    const q = search.trim().toLowerCase();
    return loans.filter(l =>
      l.name.toLowerCase().includes(q) ||
      l.loan_type.toLowerCase().includes(q)
    );
  }, [loans, search]);

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success(t('messages.loan_deleted'));
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteId(null);
  }

  if (loans.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        {t('table.no_loans')}
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
              <TableHead>{t('fields.name')}</TableHead>
              <TableHead>{t('fields.type')}</TableHead>
              <TableHead>{t('fields.current_value')}</TableHead>
              <TableHead>{t('fields.interest_rate')}</TableHead>
              <TableHead>{t('fields.end_date')}</TableHead>
              <TableHead>{t('table.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((loan) => (
              <TableRow key={loan.id}>
                <TableCell className="font-medium">{loan.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    {t(`loan_types.${loan.loan_type}`)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatCurrency(loan.current_balance ?? loan.original_value)}
                  </span>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatPercent(loan.interest_rate_annual_pct)}
                  </span>
                </TableCell>
                <TableCell>
                  {(loan.config_json?.end_date as string) ??
                    (() => {
                      const d = new Date(loan.start_date);
                      d.setMonth(d.getMonth() + loan.duration_months);
                      return d.toISOString().slice(0, 10);
                    })()}
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setLogLoan(loan)}
                      title={t('actions.record_measurement')}
                    >
                      <ClipboardList className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHistoryLoan(loan)}
                      title={t('measurements.history')}
                    >
                      <History className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditLoan(loan)}
                    >
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => setDeleteId(loan.id)}
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

      <LoanForm
        open={!!editLoan}
        onOpenChange={(open) => {
          if (!open) setEditLoan(undefined);
        }}
        loan={editLoan}
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
        open={!!logLoan}
        onOpenChange={(open) => { if (!open) setLogLoan(null); }}
        entityType="loan"
        entityId={logLoan?.id ?? 0}
        entityName={logLoan?.name ?? ''}
      />

      <MeasurementHistoryDialog
        open={!!historyLoan}
        onOpenChange={(open) => { if (!open) setHistoryLoan(null); }}
        entityType="loan"
        entityId={historyLoan?.id ?? 0}
        entityName={historyLoan?.name ?? ''}
      />
    </>
  );
}
