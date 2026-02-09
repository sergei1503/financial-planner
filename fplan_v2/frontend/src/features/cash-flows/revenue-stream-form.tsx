import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { RevenueStreamType, Period } from '@/api/types';
import type { RevenueStreamResponse } from '@/api/types';
import { useCreateRevenueStream, useUpdateRevenueStream } from '@/hooks/use-revenue-streams';
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

const NONE_VALUE = '__none__';

const revenueStreamSchema = z.object({
  stream_type: z.string().min(1),
  name: z.string().min(1),
  amount: z.number().min(0),
  period: z.string(),
  start_date: z.string().min(1),
  end_date: z.string().optional(),
  tax_rate: z.number().min(0).max(100),
  growth_rate: z.number(),
  asset_id: z.number().nullable(),
});

type RevenueStreamFormValues = z.infer<typeof revenueStreamSchema>;

interface RevenueStreamFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  revenueStream?: RevenueStreamResponse;
}

const STREAM_TYPES = [
  RevenueStreamType.SALARY,
  RevenueStreamType.RENT,
  RevenueStreamType.DIVIDEND,
  RevenueStreamType.PENSION,
] as const;

const PERIODS = [
  Period.MONTHLY,
  Period.QUARTERLY,
  Period.YEARLY,
] as const;

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

export function RevenueStreamForm({ open, onOpenChange, revenueStream }: RevenueStreamFormProps) {
  const { t } = useTranslation();
  const createMutation = useCreateRevenueStream();
  const updateMutation = useUpdateRevenueStream();
  const { data: assets } = useAssets();
  const isEditing = !!revenueStream;

  const form = useForm<RevenueStreamFormValues>({
    resolver: zodResolver(revenueStreamSchema),
    defaultValues: {
      stream_type: revenueStream?.stream_type ?? RevenueStreamType.SALARY,
      name: revenueStream?.name ?? '',
      amount: revenueStream?.amount ?? 0,
      period: revenueStream?.period ?? Period.MONTHLY,
      start_date: revenueStream?.start_date?.slice(0, 10) ?? '',
      end_date: revenueStream?.end_date?.slice(0, 10) ?? '',
      tax_rate: revenueStream?.tax_rate ?? 0,
      growth_rate: revenueStream?.growth_rate ?? 0,
      asset_id: revenueStream?.asset_id ?? null,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        stream_type: revenueStream?.stream_type ?? RevenueStreamType.SALARY,
        name: revenueStream?.name ?? '',
        amount: revenueStream?.amount ?? 0,
        period: revenueStream?.period ?? Period.MONTHLY,
        start_date: revenueStream?.start_date?.slice(0, 10) ?? '',
        end_date: revenueStream?.end_date?.slice(0, 10) ?? '',
        tax_rate: revenueStream?.tax_rate ?? 0,
        growth_rate: revenueStream?.growth_rate ?? 0,
        asset_id: revenueStream?.asset_id ?? null,
      });
    }
  }, [open, revenueStream, form]);

  async function onSubmit(values: RevenueStreamFormValues) {
    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: revenueStream.id,
          data: {
            name: values.name,
            amount: values.amount,
            end_date: values.end_date || null,
            tax_rate: values.tax_rate,
            growth_rate: values.growth_rate,
          },
        });
      } else {
        await createMutation.mutateAsync({
          stream_type: values.stream_type as RevenueStreamType,
          name: values.name,
          amount: values.amount,
          period: values.period as Period,
          start_date: values.start_date,
          end_date: values.end_date || null,
          tax_rate: values.tax_rate,
          growth_rate: values.growth_rate,
          asset_id: values.asset_id,
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
          <DialogTitle>{t('cashFlow.tab_income')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="stream_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.stream_type')}</FormLabel>
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
                      {STREAM_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {t(`revenue.${type}`)}
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
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.amount')}</FormLabel>
                  <FormControl>
                    <NumberInput
                      type="number"
                      min={0}
                      placeholder={t('placeholders.enter_amount')}
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
              name="period"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.period')}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={isEditing}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {PERIODS.map((p) => (
                        <SelectItem key={p} value={p}>
                          {t(`period.${p}`)}
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
              name="tax_rate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.tax_rate')}</FormLabel>
                  <FormControl>
                    <NumberInput
                      type="number"
                      step="0.1"
                      min={0}
                      max={100}
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
              name="growth_rate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.growth_rate')}</FormLabel>
                  <FormControl>
                    <NumberInput
                      type="number"
                      step="0.1"
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
              name="asset_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('revenue.linked_asset')}</FormLabel>
                  <Select
                    onValueChange={(value) => field.onChange(value === NONE_VALUE ? null : parseInt(value))}
                    value={field.value?.toString() ?? NONE_VALUE}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={t('placeholders.select_type')} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NONE_VALUE}>
                        {t('cashFlow.noLink')}
                      </SelectItem>
                      {assets?.map((asset) => (
                        <SelectItem key={asset.id} value={asset.id.toString()}>
                          {asset.name}
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
