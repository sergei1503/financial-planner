import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { LoanType } from '@/api/types';
import type { LoanResponse } from '@/api/types';
import { useCreateLoan, useUpdateLoan } from '@/hooks/use-loans';
import { useAssets } from '@/hooks/use-assets';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';

const loanSchema = z.object({
  loan_type: z.string().min(1),
  name: z.string().min(1),
  start_date: z.string().min(1),
  original_value: z.number().min(0),
  interest_rate_annual_pct: z.number().min(0),
  end_date: z.string().min(1),
  collateral_asset_id: z.string().optional(),
});

type LoanFormValues = z.infer<typeof loanSchema>;

function monthsBetween(start: string, end: string): number {
  const s = new Date(start);
  const e = new Date(end);
  return (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth());
}

function addMonths(dateStr: string, months: number): string {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + months);
  return d.toISOString().slice(0, 10);
}

interface LoanFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loan?: LoanResponse;
}

const LOAN_TYPES = [
  LoanType.FIXED,
  LoanType.PRIME_PEGGED,
  LoanType.CPI_PEGGED,
  LoanType.VARIABLE,
] as const;

const NONE_VALUE = '__none__';

function NumberInput({
  value,
  onChange,
  ...props
}: Omit<React.ComponentProps<typeof Input>, 'onChange' | 'value'> & {
  value: number | undefined;
  onChange: (v: number) => void;
}) {
  return (
    <Input
      {...props}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.valueAsNumber || 0)}
    />
  );
}

export function LoanForm({ open, onOpenChange, loan }: LoanFormProps) {
  const { t } = useTranslation();
  const createMutation = useCreateLoan();
  const updateMutation = useUpdateLoan();
  const { data: assets } = useAssets();
  const isEditing = !!loan;

  function deriveEndDate(l?: LoanResponse): string {
    if (l?.config_json?.end_date) return String(l.config_json.end_date);
    if (l?.start_date && l?.duration_months) {
      return addMonths(l.start_date.slice(0, 10), l.duration_months);
    }
    return '';
  }

  const form = useForm<LoanFormValues>({
    resolver: zodResolver(loanSchema),
    defaultValues: {
      loan_type: loan?.loan_type ?? LoanType.FIXED,
      name: loan?.name ?? '',
      start_date: loan?.start_date?.slice(0, 10) ?? '',
      original_value: loan?.original_value ?? 0,
      interest_rate_annual_pct: loan?.interest_rate_annual_pct ?? 0,
      end_date: deriveEndDate(loan),
      collateral_asset_id: loan?.collateral_asset_id?.toString() ?? NONE_VALUE,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        loan_type: loan?.loan_type ?? LoanType.FIXED,
        name: loan?.name ?? '',
        start_date: loan?.start_date?.slice(0, 10) ?? '',
        original_value: loan?.original_value ?? 0,
        interest_rate_annual_pct: loan?.interest_rate_annual_pct ?? 0,
        end_date: deriveEndDate(loan),
        collateral_asset_id: loan?.collateral_asset_id?.toString() ?? NONE_VALUE,
      });
    }
  }, [open, loan, form]);

  async function onSubmit(values: LoanFormValues) {
    const collateralId =
      values.collateral_asset_id && values.collateral_asset_id !== NONE_VALUE
        ? Number(values.collateral_asset_id)
        : null;

    const durationMonths = monthsBetween(values.start_date, values.end_date);

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: loan.id,
          data: {
            name: values.name,
            interest_rate_annual_pct: values.interest_rate_annual_pct,
            config_json: { ...loan.config_json, end_date: values.end_date },
          },
        });
      } else {
        await createMutation.mutateAsync({
          loan_type: values.loan_type as LoanType,
          name: values.name,
          start_date: values.start_date,
          original_value: values.original_value,
          interest_rate_annual_pct: values.interest_rate_annual_pct,
          duration_months: durationMonths,
          collateral_asset_id: collateralId,
          config_json: { end_date: values.end_date },
        });
      }
      toast.success(t('messages.data_saved'));
      onOpenChange(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('messages.error_saving');
      toast.error(message);
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('forms.loan_form')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="loan_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.type')}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={isEditing}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={t('placeholders.select_type')} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {LOAN_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {t(`loan_types.${type}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.name')}</FormLabel>
                  <FormControl>
                    <Input placeholder={t('placeholders.enter_name')} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="start_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.start_date')}</FormLabel>
                  <FormControl>
                    <Input type="date" disabled={isEditing} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="original_value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.principal')}</FormLabel>
                  <FormControl>
                    <NumberInput
                      type="number"
                      min={0}
                      placeholder={t('placeholders.enter_amount')}
                      disabled={isEditing}
                      value={field.value}
                      onChange={field.onChange}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="interest_rate_annual_pct"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.interest_rate')}</FormLabel>
                  <FormControl>
                    <NumberInput
                      type="number"
                      step="0.01"
                      value={field.value}
                      onChange={field.onChange}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="end_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.end_date')}</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="collateral_asset_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.linked_asset')}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value ?? NONE_VALUE}
                    disabled={isEditing}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NONE_VALUE}>-</SelectItem>
                      {assets?.map((a) => (
                        <SelectItem key={a.id} value={a.id.toString()}>
                          {a.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                {t('actions.cancel')}
              </Button>
              <Button type="submit" disabled={isPending}>
                {t('actions.save')}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
