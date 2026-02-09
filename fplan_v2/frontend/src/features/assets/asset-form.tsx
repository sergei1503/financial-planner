import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { AssetType } from '@/api/types';
import type { AssetResponse } from '@/api/types';
import { useCreateAsset, useUpdateAsset } from '@/hooks/use-assets';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
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

const assetSchema = z.object({
  asset_type: z.string().min(1),
  name: z.string().min(1),
  start_date: z.string().min(1),
  original_value: z.number().min(0),
  appreciation_rate_annual_pct: z.number(),
  yearly_fee_pct: z.number(),
  currency: z.string(),
  sell_date: z.string().optional(),
  sell_tax: z.number().optional(),
  conversion_date: z.string().optional(),
  conversion_coefficient: z.number().optional(),
});

type AssetFormValues = z.infer<typeof assetSchema>;

interface AssetFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  asset?: AssetResponse;
}

const ASSET_TYPES = [
  AssetType.REAL_ESTATE,
  AssetType.STOCK,
  AssetType.PENSION,
  AssetType.CASH,
] as const;

const CURRENCIES = ['ILS', 'USD', 'EUR'] as const;

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

export function AssetForm({ open, onOpenChange, asset }: AssetFormProps) {
  const { t } = useTranslation();
  const createMutation = useCreateAsset();
  const updateMutation = useUpdateAsset();
  const isEditing = !!asset;

  const form = useForm<AssetFormValues>({
    resolver: zodResolver(assetSchema),
    defaultValues: {
      asset_type: asset?.asset_type ?? AssetType.REAL_ESTATE,
      name: asset?.name ?? '',
      start_date: asset?.start_date?.slice(0, 10) ?? '',
      original_value: asset?.original_value ?? 0,
      appreciation_rate_annual_pct: asset?.appreciation_rate_annual_pct ?? 0,
      yearly_fee_pct: asset?.yearly_fee_pct ?? 0,
      currency: asset?.currency ?? 'ILS',
      sell_date: asset?.sell_date?.slice(0, 10) ?? '',
      sell_tax: asset?.sell_tax ?? 0,
      conversion_date: (asset?.config_json?.conversion_date as string) ?? '',
      conversion_coefficient: (asset?.config_json?.conversion_coefficient as number) ?? 200,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        asset_type: asset?.asset_type ?? AssetType.REAL_ESTATE,
        name: asset?.name ?? '',
        start_date: asset?.start_date?.slice(0, 10) ?? '',
        original_value: asset?.original_value ?? 0,
        appreciation_rate_annual_pct: asset?.appreciation_rate_annual_pct ?? 0,
        yearly_fee_pct: asset?.yearly_fee_pct ?? 0,
        currency: asset?.currency ?? 'ILS',
        sell_date: asset?.sell_date?.slice(0, 10) ?? '',
        sell_tax: asset?.sell_tax ?? 0,
        conversion_date: (asset?.config_json?.conversion_date as string) ?? '',
        conversion_coefficient: (asset?.config_json?.conversion_coefficient as number) ?? 200,
      });
    }
  }, [open, asset, form]);

  async function onSubmit(values: AssetFormValues) {
    try {
      const isPension = values.asset_type === 'pension';
      const pensionConfig = isPension ? {
        conversion_date: values.conversion_date || undefined,
        conversion_coefficient: values.conversion_coefficient ?? 200,
      } : undefined;

      // For pension, conversion_date replaces sell_date — they are mutually exclusive
      const sellDate = isPension ? (values.conversion_date || null) : (values.sell_date || null);
      const sellTax = isPension ? 0 : (values.sell_tax ?? 0);

      if (isEditing) {
        await updateMutation.mutateAsync({
          id: asset.id,
          data: {
            name: values.name,
            appreciation_rate_annual_pct: values.appreciation_rate_annual_pct,
            yearly_fee_pct: values.yearly_fee_pct,
            sell_date: sellDate,
            sell_tax: sellTax,
            ...(pensionConfig && { config_json: { ...asset?.config_json, ...pensionConfig } }),
          },
        });
      } else {
        await createMutation.mutateAsync({
          asset_type: values.asset_type as AssetType,
          name: values.name,
          start_date: values.start_date,
          original_value: values.original_value,
          appreciation_rate_annual_pct: values.appreciation_rate_annual_pct,
          yearly_fee_pct: values.yearly_fee_pct,
          currency: values.currency,
          sell_date: sellDate,
          sell_tax: sellTax,
          ...(pensionConfig && { config_json: pensionConfig }),
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
  const assetType = form.watch('asset_type');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('forms.asset_form')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="asset_type"
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
                      {ASSET_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {t(`asset_types.${type}`)}
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
                  <FormLabel>{t('fields.value')}</FormLabel>
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
              name="appreciation_rate_annual_pct"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.appreciation_rate')}</FormLabel>
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
              name="yearly_fee_pct"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.yearly_fee')}</FormLabel>
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
              name="currency"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('fields.currency')}</FormLabel>
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
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {assetType === 'pension' && (
              <>
                <FormField
                  control={form.control}
                  name="conversion_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('pension.conversion_date')}</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="conversion_coefficient"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('pension.conversion_coefficient')}</FormLabel>
                      <FormControl>
                        <NumberInput
                          type="number"
                          step="1"
                          min={1}
                          value={field.value}
                          onChange={field.onChange}
                        />
                      </FormControl>
                      <FormDescription>
                        {t('pension.conversion_help')}
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            {assetType !== 'pension' && (
              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {t('actions.advanced')}
                </summary>
                <div className="mt-3 space-y-4">
                  <FormField
                    control={form.control}
                    name="sell_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('fields.sell_date')}</FormLabel>
                        <div className="flex gap-2 items-center">
                          <FormControl>
                            <Input type="date" {...field} />
                          </FormControl>
                          {field.value && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="text-destructive shrink-0"
                              onClick={() => form.setValue('sell_date', '')}
                            >
                              {t('actions.clear', 'Clear')}
                            </Button>
                          )}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="sell_tax"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('fields.sell_tax')}</FormLabel>
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
                </div>
              </details>
            )}

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
