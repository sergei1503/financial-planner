import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { RevenueStreamResponse } from '@/api/types';
import { useDeleteRevenueStream } from '@/hooks/use-revenue-streams';
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

interface RevenueStreamListProps {
  streams: RevenueStreamResponse[];
}

export function RevenueStreamList({ streams }: RevenueStreamListProps) {
  const { t } = useTranslation();
  const deleteMutation = useDeleteRevenueStream();
  const [editStream, setEditStream] = useState<RevenueStreamResponse | undefined>();
  const [deleteId, setDeleteId] = useState<number | null>(null);

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success(t('messages.revenue_stream_deleted'));
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteId(null);
  }

  // Filter out zero-amount streams
  const visibleStreams = streams.filter(s => s.amount > 0);

  if (visibleStreams.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        {t('table.no_revenue_streams')}
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
              <TableHead>{t('revenue.stream_type')}</TableHead>
              <TableHead>{t('fields.amount')}</TableHead>
              <TableHead>{t('revenue.period')}</TableHead>
              <TableHead>{t('revenue.tax_rate')}</TableHead>
              <TableHead>{t('revenue.growth_rate')}</TableHead>
              <TableHead>{t('table.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleStreams.map((stream) => (
              <TableRow key={stream.id}>
                <TableCell className="font-medium">{stream.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    {t(`revenue.${stream.stream_type}`)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatCurrency(stream.amount, 'ILS')}
                  </span>
                </TableCell>
                <TableCell>{t(`period.${stream.period}`)}</TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatPercent(stream.tax_rate)}
                  </span>
                </TableCell>
                <TableCell>
                  <span dir="ltr" className="inline-block">
                    {formatPercent(stream.growth_rate)}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditStream(stream)}
                    >
                      {t('actions.edit')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => setDeleteId(stream.id)}
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

      <RevenueStreamForm
        key={editStream?.id ?? 'new'}
        open={!!editStream}
        onOpenChange={(open) => {
          if (!open) setEditStream(undefined);
        }}
        revenueStream={editStream}
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
