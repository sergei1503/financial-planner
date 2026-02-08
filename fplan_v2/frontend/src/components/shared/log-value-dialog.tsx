import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { useCreateMeasurement } from '@/hooks/use-historical-measurements';

interface LogValueDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entityType: 'asset' | 'loan';
  entityId: number;
  entityName: string;
}

export function LogValueDialog({
  open,
  onOpenChange,
  entityType,
  entityId,
  entityName,
}: LogValueDialogProps) {
  const { t } = useTranslation();
  const createMutation = useCreateMeasurement();
  const [value, setValue] = useState('');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const numValue = Number(value);
    if (isNaN(numValue) || numValue < 0) {
      toast.error(t('validation.must_be_positive'));
      return;
    }

    try {
      await createMutation.mutateAsync({
        entity_type: entityType,
        entity_id: entityId,
        measurement_date: date,
        actual_value: numValue,
        notes: notes || null,
        source: 'manual',
      });
      toast.success(t('messages.data_saved'));
      setValue('');
      setNotes('');
      onOpenChange(false);
    } catch {
      toast.error(t('messages.error_saving'));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t('actions.record_measurement')} — {entityName}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="measurement-date">{t('fields.date')}</Label>
            <Input
              id="measurement-date"
              type="date"
              value={date}
              onChange={e => setDate(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="measurement-value">{t('fields.value')}</Label>
            <Input
              id="measurement-value"
              type="number"
              step="0.01"
              min="0"
              placeholder={t('placeholders.enter_amount')}
              value={value}
              onChange={e => setValue(e.target.value)}
              required
              dir="ltr"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="measurement-notes">{t('fields.description')}</Label>
            <Input
              id="measurement-notes"
              placeholder=""
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('actions.cancel')}
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {t('actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
