import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { CashFlowType } from '@/api/types';
import type { CashFlowResponse } from '@/api/types';
import { useCreateCashFlow, useUpdateCashFlow } from '@/hooks/use-cash-flows';
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
  FormDescription,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

const NONE_VALUE = '__none__';

const cashFlowSchema = z.object({
  flow_type: z.enum(['deposit', 'withdrawal']),
  name: z.string().min(1),
  amount: z.number().min(0),
  from_date: z.string().min(1),
  to_date: z.string().min(1),
  target_asset_id: z.number().nullable(),
  from_own_capital: z.boolean(),
});

type CashFlowFormValues = z.infer<typeof cashFlowSchema>;

interface CashFlowFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  cashFlow?: CashFlowResponse;
  initialAssetId?: number;
}

const FLOW_TYPES = [
  CashFlowType.DEPOSIT,
  CashFlowType.WITHDRAWAL,
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

export function CashFlowForm({ open, onOpenChange, cashFlow, initialAssetId }: CashFlowFormProps) {
  const { t } = useTranslation();
  const createMutation = useCreateCashFlow();
  const updateMutation = useUpdateCashFlow();
  const { data: assets } = useAssets();
  const isEditing = !!cashFlow;

  const form = useForm<CashFlowFormValues>({
    resolver: zodResolver(cashFlowSchema),
    defaultValues: {
      flow_type: cashFlow?.flow_type ?? CashFlowType.DEPOSIT,
      name: cashFlow?.name ?? '',
      amount: cashFlow?.amount ?? 0,
      from_date: cashFlow?.from_date?.slice(0, 10) ?? '',
      to_date: cashFlow?.to_date?.slice(0, 10) ?? '',
      target_asset_id: cashFlow?.target_asset_id ?? initialAssetId ?? null,
      from_own_capital: cashFlow?.from_own_capital ?? true,
    },
  });

  const flowType = form.watch('flow_type');

  useEffect(() => {
    if (open) {
      form.reset({
        flow_type: cashFlow?.flow_type ?? CashFlowType.DEPOSIT,
        name: cashFlow?.name ?? '',
        amount: cashFlow?.amount ?? 0,
        from_date: cashFlow?.from_date?.slice(0, 10) ?? '',
        to_date: cashFlow?.to_date?.slice(0, 10) ?? '',
        target_asset_id: cashFlow?.target_asset_id ?? initialAssetId ?? null,
        from_own_capital: cashFlow?.from_own_capital ?? true,
      });
    }
  }, [open, cashFlow, initialAssetId, form]);

  async function onSubmit(values: CashFlowFormValues) {
    try {
      if (isEditing) {
        await updateMutation.mutateAsync({
          id: cashFlow.id,
          data: {
            name: values.name,
            amount: values.amount,
            from_date: values.from_date,
            to_date: values.to_date,
            target_asset_id: values.target_asset_id,
            from_own_capital: values.from_own_capital,
          },
        });
      } else {
        await createMutation.mutateAsync({
          flow_type: values.flow_type as CashFlowType,
          name: values.name,
          amount: values.amount,
          from_date: values.from_date,
          to_date: values.to_date,
          target_asset_id: values.target_asset_id,
          from_own_capital: values.from_own_capital,
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
          <DialogTitle>{t('forms.revenue_stream_form')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="flow_type"
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
                      {FLOW_TYPES.map((type) => (
                        <SelectItem key={type} value={type}>
                          {t(`cash_flows.${type}`)}
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

            {flowType === CashFlowType.DEPOSIT && (
              <FormField
                control={form.control}
                name="from_own_capital"
                render={({ field }) => (
                  <FormItem className="space-y-3">
                    <FormLabel>{t('cash_flows.deposit_origin')}</FormLabel>
                    <FormDescription>
                      {t('cash_flows.deposit_origin_description')}
                    </FormDescription>
                    <FormControl>
                      <RadioGroup
                        onValueChange={(value) => field.onChange(value === 'true')}
                        value={field.value ? 'true' : 'false'}
                        className="flex flex-col space-y-2"
                      >
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="true" id="own-capital" />
                          <Label htmlFor="own-capital" className="font-normal cursor-pointer">
                            {t('cash_flows.deposit_origin_own')}
                          </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="false" id="employer" />
                          <Label htmlFor="employer" className="font-normal cursor-pointer">
                            {t('cash_flows.deposit_origin_employer')}
                          </Label>
                        </div>
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={form.control}
              name="from_date"
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
              name="to_date"
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
              name="target_asset_id"
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
