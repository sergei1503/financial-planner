import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Pencil, Trash2, Check, X } from 'lucide-react';
import type { HistoricalMeasurementResponse } from '@/api/types';
import {
  useHistoricalMeasurements,
  useUpdateMeasurement,
  useDeleteMeasurement,
} from '@/hooks/use-historical-measurements';
import { formatCurrency, formatDate } from '@/lib/formatters';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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

interface MeasurementHistoryDialogProps {
  entityType: 'asset' | 'loan';
  entityId: number;
  entityName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MeasurementHistoryDialog({
  entityType,
  entityId,
  entityName,
  open,
  onOpenChange,
}: MeasurementHistoryDialogProps) {
  const { t } = useTranslation();
  const { data: measurements, isLoading } = useHistoricalMeasurements(
    open ? entityType : '',
    open ? entityId : 0
  );
  const updateMutation = useUpdateMeasurement();
  const deleteMutation = useDeleteMeasurement();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editDate, setEditDate] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);

  function startEdit(m: HistoricalMeasurementResponse) {
    setEditingId(m.id);
    setEditValue(String(m.actual_value));
    setEditDate(m.measurement_date);
    setEditNotes(m.notes ?? '');
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit() {
    if (editingId === null) return;
    const numValue = Number(editValue);
    if (isNaN(numValue) || numValue < 0) {
      toast.error(t('validation.must_be_positive'));
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: editingId,
        data: {
          actual_value: numValue,
          measurement_date: editDate,
          notes: editNotes || null,
        },
      });
      toast.success(t('messages.data_saved'));
      setEditingId(null);
    } catch {
      toast.error(t('messages.error_saving'));
    }
  }

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

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {t('measurements.history')} — {entityName}
            </DialogTitle>
          </DialogHeader>

          {isLoading ? (
            <p className="py-8 text-center text-muted-foreground">
              {t('projections.computing')}
            </p>
          ) : !measurements || measurements.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              {t('measurements.no_measurements')}
            </p>
          ) : (
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('fields.date')}</TableHead>
                    <TableHead>{t('fields.value')}</TableHead>
                    <TableHead>{t('fields.description')}</TableHead>
                    <TableHead>{t('measurements.source')}</TableHead>
                    <TableHead>{t('table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {measurements.map((m) =>
                    editingId === m.id ? (
                      <TableRow key={m.id}>
                        <TableCell>
                          <Input
                            type="date"
                            value={editDate}
                            onChange={(e) => setEditDate(e.target.value)}
                            className="w-36"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="w-32"
                            dir="ltr"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            className="w-40"
                          />
                        </TableCell>
                        <TableCell />
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={saveEdit}
                              disabled={updateMutation.isPending}
                            >
                              <Check className="size-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={cancelEdit}>
                              <X className="size-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ) : (
                      <TableRow key={m.id}>
                        <TableCell>
                          <span dir="ltr" className="inline-block">
                            {formatDate(m.measurement_date)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span dir="ltr" className="inline-block">
                            {formatCurrency(m.actual_value)}
                          </span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {m.notes ?? '—'}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-xs">
                          {t(`measurements.source_${m.source}`, m.source)}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => startEdit(m)}
                            >
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => setDeleteId(m.id)}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>

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
    </>
  );
}
