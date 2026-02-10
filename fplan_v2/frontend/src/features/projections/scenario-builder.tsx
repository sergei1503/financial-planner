import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Plus, Trash2 } from 'lucide-react';
import { AssetType, LoanType, RevenueStreamType, Period, ScenarioActionType } from '@/api/types';
import type { ScenarioResponse } from '@/api/types';
import { useAssets } from '@/hooks/use-assets';
import { useLoans } from '@/hooks/use-loans';
import { useRevenueStreams } from '@/hooks/use-revenue-streams';
import { useCreateScenario, useUpdateScenario } from '@/hooks/use-scenarios';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// --- Zod schema ---

const actionSchema = z.object({
  type: z.string().min(1),
  target_type: z.string().nullable().optional(),
  target_id: z.number().nullable().optional(),
  field: z.string().nullable().optional(),
  value: z.unknown().optional(),
  changes: z.record(z.string(), z.unknown()).nullable().optional(),
  params: z.record(z.string(), z.unknown()).nullable().optional(),
  crash_pct: z.number().nullable().optional(),
  crash_date: z.string().nullable().optional(),
  affected_asset_types: z.array(z.string()).nullable().optional(),
  amount: z.number().nullable().optional(),
  action_date: z.string().nullable().optional(),
});

const scenarioFormSchema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  actions: z.array(actionSchema).min(1, 'At least one action is required'),
});

type ScenarioFormValues = z.infer<typeof scenarioFormSchema>;

// --- Helper ---

function NumberInput({
  value,
  onChange,
  ...props
}: Omit<React.ComponentProps<typeof Input>, 'onChange' | 'value'> & {
  value: number | undefined | null;
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

const ACTION_TYPES = Object.values(ScenarioActionType);

const ASSET_TYPES_LIST = [
  AssetType.STOCK,
  AssetType.REAL_ESTATE,
  AssetType.PENSION,
  AssetType.CASH,
] as const;

const LOAN_TYPES_LIST = [
  LoanType.FIXED,
  LoanType.PRIME_PEGGED,
  LoanType.CPI_PEGGED,
  LoanType.VARIABLE,
] as const;

const STREAM_TYPES_LIST = [
  RevenueStreamType.SALARY,
  RevenueStreamType.RENT,
  RevenueStreamType.DIVIDEND,
  RevenueStreamType.PENSION,
] as const;

const PERIODS_LIST = [
  Period.MONTHLY,
  Period.QUARTERLY,
  Period.YEARLY,
] as const;

const PARAM_CHANGE_FIELDS: Record<string, string[]> = {
  asset: ['appreciation_rate_annual_pct', 'yearly_fee_pct', 'current_value', 'sell_date'],
  loan: ['interest_rate_annual_pct'],
  revenue_stream: ['amount', 'growth_rate', 'tax_rate', 'end_date'],
};

interface ScenarioBuilderProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scenario?: ScenarioResponse;
}

export function ScenarioBuilder({ open, onOpenChange, scenario }: ScenarioBuilderProps) {
  const { t } = useTranslation();
  const createMutation = useCreateScenario();
  const updateMutation = useUpdateScenario();
  const { data: assets } = useAssets();
  const { data: loans } = useLoans();
  const { data: revenueStreams } = useRevenueStreams();
  const isEditing = !!scenario;

  const form = useForm<ScenarioFormValues>({
    resolver: zodResolver(scenarioFormSchema),
    defaultValues: {
      name: scenario?.name ?? '',
      description: scenario?.description ?? '',
      actions: scenario?.actions?.length
        ? scenario.actions.map((a) => ({ ...a }))
        : [{ type: ScenarioActionType.PARAM_CHANGE }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: 'actions',
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: scenario?.name ?? '',
        description: scenario?.description ?? '',
        actions: scenario?.actions?.length
          ? scenario.actions.map((a) => ({ ...a }))
          : [{ type: ScenarioActionType.PARAM_CHANGE }],
      });
    }
  }, [open, scenario, form]);

  async function onSubmit(values: ScenarioFormValues) {
    try {
      const actions = values.actions.map((a) => ({
        type: a.type as ScenarioActionType,
        target_type: a.target_type || null,
        target_id: a.target_id || null,
        field: a.field || null,
        value: a.value ?? null,
        changes: a.changes || null,
        params: a.params || null,
        crash_pct: a.crash_pct ?? null,
        crash_date: a.crash_date || null,
        affected_asset_types: a.affected_asset_types?.length ? a.affected_asset_types : null,
        amount: a.amount ?? null,
        action_date: a.action_date || null,
      }));

      if (isEditing) {
        await updateMutation.mutateAsync({
          id: scenario.id,
          data: { name: values.name, description: values.description || null, actions },
        });
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          description: values.description || null,
          actions,
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
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto" data-testid="scenario-builder">
        <SheetHeader>
          <SheetTitle>{t('scenarios.builder_title')}</SheetTitle>
        </SheetHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 p-1">
          {/* Name */}
          <div className="space-y-2">
            <Label>{t('scenarios.name')}</Label>
            <Input
              data-testid="scenario-name-input"
              placeholder={t('placeholders.enter_name')}
              {...form.register('name')}
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">{t('validation.required')}</p>
            )}
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label>{t('scenarios.description')}</Label>
            <Input
              data-testid="scenario-description-input"
              placeholder={t('fields.description')}
              {...form.register('description')}
            />
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-base font-semibold">{t('scenarios.add_action')}</Label>
              <Badge variant="secondary">
                {t('scenarios.actions_count', { count: fields.length })}
              </Badge>
            </div>

            {fields.map((field, index) => (
              <ActionCard
                key={field.id}
                index={index}
                form={form}
                assets={assets ?? []}
                loans={loans ?? []}
                revenueStreams={revenueStreams ?? []}
                onRemove={() => remove(index)}
                canRemove={fields.length > 1}
              />
            ))}

            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => append({ type: ScenarioActionType.PARAM_CHANGE })}
              data-testid="scenario-add-action-button"
            >
              <Plus className="size-4 me-2" />
              {t('scenarios.add_action')}
            </Button>
          </div>

          {form.formState.errors.actions && (
            <p className="text-sm text-destructive">
              {form.formState.errors.actions.message || form.formState.errors.actions.root?.message}
            </p>
          )}

          {/* Save / Cancel */}
          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t('actions.cancel')}
            </Button>
            <Button type="submit" disabled={isPending} data-testid="scenario-save-button">
              {t('actions.save')}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}

// --- Action Card ---

interface ActionCardProps {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  assets: { id: number; name: string; asset_type: string }[];
  loans: { id: number; name: string; loan_type: string }[];
  revenueStreams: { id: number; name: string; stream_type: string }[];
  onRemove: () => void;
  canRemove: boolean;
}

function ActionCard({ index, form, assets, loans, revenueStreams, onRemove, canRemove }: ActionCardProps) {
  const { t } = useTranslation();
  const actionType = form.watch(`actions.${index}.type`);

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">
            {t(`scenarios.action_types.${actionType}`, actionType)}
          </CardTitle>
          {canRemove && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-destructive"
              onClick={onRemove}
            >
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-4 pb-4">
        {/* Action Type Selector */}
        <div className="space-y-1">
          <Label className="text-xs">{t('fields.type')}</Label>
          <Controller
            control={form.control}
            name={`actions.${index}.type`}
            render={({ field }) => (
              <Select onValueChange={field.onChange} value={field.value}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('scenarios.select_action_type')} />
                </SelectTrigger>
                <SelectContent>
                  {ACTION_TYPES.map((at) => (
                    <SelectItem key={at} value={at}>
                      {t(`scenarios.action_types.${at}`, at)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        {/* Effective Date (common to all actions) */}
        <div className="space-y-1">
          <Label className="text-xs">{t('scenarios.effective_date')}</Label>
          <Input type="date" {...form.register(`actions.${index}.action_date`)} />
        </div>

        {/* Type-specific form fields */}
        {actionType === ScenarioActionType.PARAM_CHANGE && (
          <ParamChangeFields index={index} form={form} assets={assets} loans={loans} revenueStreams={revenueStreams} />
        )}
        {actionType === ScenarioActionType.NEW_ASSET && (
          <NewAssetFields index={index} form={form} />
        )}
        {actionType === ScenarioActionType.NEW_LOAN && (
          <NewLoanFields index={index} form={form} />
        )}
        {actionType === ScenarioActionType.REPAY_LOAN && (
          <RepayLoanFields index={index} form={form} loans={loans} />
        )}
        {actionType === ScenarioActionType.TRANSFORM_ASSET && (
          <TransformAssetFields index={index} form={form} assets={assets} />
        )}
        {(actionType === ScenarioActionType.WITHDRAW_FROM_ASSET ||
          actionType === ScenarioActionType.DEPOSIT_TO_ASSET) && (
          <WithdrawDepositFields index={index} form={form} assets={assets} />
        )}
        {actionType === ScenarioActionType.MARKET_CRASH && (
          <MarketCrashFields index={index} form={form} />
        )}
        {actionType === ScenarioActionType.ADD_REVENUE_STREAM && (
          <AddRevenueStreamFields index={index} form={form} assets={assets} />
        )}
      </CardContent>
    </Card>
  );
}

// --- PARAM_CHANGE ---

function ParamChangeFields({
  index, form, assets, loans, revenueStreams,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  assets: { id: number; name: string }[];
  loans: { id: number; name: string }[];
  revenueStreams: { id: number; name: string }[];
}) {
  const { t } = useTranslation();
  const targetType = form.watch(`actions.${index}.target_type`);

  const entities =
    targetType === 'asset' ? assets :
    targetType === 'loan' ? loans :
    targetType === 'revenue_stream' ? revenueStreams : [];

  const fieldOptions = targetType ? (PARAM_CHANGE_FIELDS[targetType] ?? []) : [];

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.select_entity')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.target_type`}
          render={({ field }) => (
            <Select onValueChange={(v) => { field.onChange(v); form.setValue(`actions.${index}.target_id`, null); form.setValue(`actions.${index}.field`, null); }} value={field.value ?? ''}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t('scenarios.select_entity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="asset">{t('common.assets')}</SelectItem>
                <SelectItem value="loan">{t('common.loans')}</SelectItem>
                <SelectItem value="revenue_stream">{t('common.revenue_streams')}</SelectItem>
              </SelectContent>
            </Select>
          )}
        />
      </div>

      {targetType && (
        <div className="space-y-1">
          <Label className="text-xs">{t('scenarios.select_entity')}</Label>
          <Controller
            control={form.control}
            name={`actions.${index}.target_id`}
            render={({ field }) => (
              <Select onValueChange={(v) => field.onChange(Number(v))} value={field.value?.toString() ?? ''}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('scenarios.select_entity')} />
                </SelectTrigger>
                <SelectContent>
                  {entities.map((e) => (
                    <SelectItem key={e.id} value={e.id.toString()}>{e.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>
      )}

      {fieldOptions.length > 0 && (
        <div className="space-y-1">
          <Label className="text-xs">{t('scenarios.select_field')}</Label>
          <Controller
            control={form.control}
            name={`actions.${index}.field`}
            render={({ field }) => (
              <Select onValueChange={field.onChange} value={field.value ?? ''}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('scenarios.select_field')} />
                </SelectTrigger>
                <SelectContent>
                  {fieldOptions.map((f) => (
                    <SelectItem key={f} value={f}>{f}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>
      )}

      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.new_value')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.value`}
          render={({ field }) => (
            <Input
              placeholder={t('scenarios.new_value')}
              value={(field.value as string) ?? ''}
              onChange={(e) => {
                const num = Number(e.target.value);
                field.onChange(isNaN(num) ? e.target.value : num);
              }}
            />
          )}
        />
      </div>
    </>
  );
}

// --- NEW_ASSET ---

function NewAssetFields({
  index, form,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
}) {
  const { t } = useTranslation();

  // Store all new asset fields in params
  const params = (form.watch(`actions.${index}.params`) ?? {}) as Record<string, unknown>;
  const setParam = (key: string, val: unknown) => {
    form.setValue(`actions.${index}.params`, { ...params, [key]: val });
  };

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.type')}</Label>
        <Select onValueChange={(v) => setParam('asset_type', v)} value={(params.asset_type as string) ?? ''}>
          <SelectTrigger className="w-full"><SelectValue placeholder={t('placeholders.select_type')} /></SelectTrigger>
          <SelectContent>
            {ASSET_TYPES_LIST.map((at) => (
              <SelectItem key={at} value={at}>{t(`asset_types.${at}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.name')}</Label>
        <Input placeholder={t('placeholders.enter_name')} value={(params.name as string) ?? ''} onChange={(e) => setParam('name', e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.value')}</Label>
        <NumberInput type="number" min={0} value={(params.original_value as number) ?? undefined} onChange={(v) => setParam('original_value', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.appreciation_rate')}</Label>
        <NumberInput type="number" step="0.1" value={(params.appreciation_rate_annual_pct as number) ?? undefined} onChange={(v) => setParam('appreciation_rate_annual_pct', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.start_date')}</Label>
        <Input type="date" value={(params.start_date as string) ?? ''} onChange={(e) => setParam('start_date', e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.sell_date')}</Label>
        <Input type="date" value={(params.sell_date as string) ?? ''} onChange={(e) => setParam('sell_date', e.target.value || null)} />
      </div>
    </>
  );
}

// --- NEW_LOAN ---

function NewLoanFields({
  index, form,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
}) {
  const { t } = useTranslation();
  const params = (form.watch(`actions.${index}.params`) ?? {}) as Record<string, unknown>;
  const setParam = (key: string, val: unknown) => {
    form.setValue(`actions.${index}.params`, { ...params, [key]: val });
  };

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.type')}</Label>
        <Select onValueChange={(v) => setParam('loan_type', v)} value={(params.loan_type as string) ?? ''}>
          <SelectTrigger className="w-full"><SelectValue placeholder={t('placeholders.select_type')} /></SelectTrigger>
          <SelectContent>
            {LOAN_TYPES_LIST.map((lt) => (
              <SelectItem key={lt} value={lt}>{t(`loan_types.${lt}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.name')}</Label>
        <Input placeholder={t('placeholders.enter_name')} value={(params.name as string) ?? ''} onChange={(e) => setParam('name', e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.principal')}</Label>
        <NumberInput type="number" min={0} value={(params.original_value as number) ?? undefined} onChange={(v) => setParam('original_value', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.interest_rate')}</Label>
        <NumberInput type="number" step="0.01" value={(params.interest_rate_annual_pct as number) ?? undefined} onChange={(v) => setParam('interest_rate_annual_pct', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.duration_months')}</Label>
        <NumberInput type="number" min={1} value={(params.duration_months as number) ?? undefined} onChange={(v) => setParam('duration_months', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.start_date')}</Label>
        <Input type="date" value={(params.start_date as string) ?? ''} onChange={(e) => setParam('start_date', e.target.value)} />
      </div>
    </>
  );
}

// --- REPAY_LOAN ---

function RepayLoanFields({
  index, form, loans,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  loans: { id: number; name: string }[];
}) {
  const { t } = useTranslation();

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.target_loan')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.target_id`}
          render={({ field }) => (
            <Select onValueChange={(v) => { field.onChange(Number(v)); form.setValue(`actions.${index}.target_type`, 'loan'); }} value={field.value?.toString() ?? ''}>
              <SelectTrigger className="w-full"><SelectValue placeholder={t('scenarios.target_loan')} /></SelectTrigger>
              <SelectContent>
                {loans.map((l) => (
                  <SelectItem key={l.id} value={l.id.toString()}>{l.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.amount')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.amount`}
          render={({ field }) => (
            <NumberInput type="number" min={0} placeholder={t('placeholders.enter_amount')} value={field.value} onChange={field.onChange} />
          )}
        />
      </div>
    </>
  );
}

// --- TRANSFORM_ASSET ---

function TransformAssetFields({
  index, form, assets,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  assets: { id: number; name: string }[];
}) {
  const { t } = useTranslation();
  const changes = (form.watch(`actions.${index}.changes`) ?? {}) as Record<string, unknown>;
  const setChange = (key: string, val: unknown) => {
    form.setValue(`actions.${index}.changes`, { ...changes, [key]: val });
  };

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.target_asset')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.target_id`}
          render={({ field }) => (
            <Select onValueChange={(v) => { field.onChange(Number(v)); form.setValue(`actions.${index}.target_type`, 'asset'); }} value={field.value?.toString() ?? ''}>
              <SelectTrigger className="w-full"><SelectValue placeholder={t('scenarios.target_asset')} /></SelectTrigger>
              <SelectContent>
                {assets.map((a) => (
                  <SelectItem key={a.id} value={a.id.toString()}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.appreciation_rate')}</Label>
        <NumberInput type="number" step="0.1" value={(changes.appreciation_rate_annual_pct as number) ?? undefined} onChange={(v) => setChange('appreciation_rate_annual_pct', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.yearly_fee')}</Label>
        <NumberInput type="number" step="0.1" value={(changes.yearly_fee_pct as number) ?? undefined} onChange={(v) => setChange('yearly_fee_pct', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.sell_date')}</Label>
        <Input type="date" value={(changes.sell_date as string) ?? ''} onChange={(e) => setChange('sell_date', e.target.value || null)} />
      </div>
    </>
  );
}

// --- WITHDRAW / DEPOSIT ---

function WithdrawDepositFields({
  index, form, assets,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  assets: { id: number; name: string }[];
}) {
  const { t } = useTranslation();

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.target_asset')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.target_id`}
          render={({ field }) => (
            <Select onValueChange={(v) => { field.onChange(Number(v)); form.setValue(`actions.${index}.target_type`, 'asset'); }} value={field.value?.toString() ?? ''}>
              <SelectTrigger className="w-full"><SelectValue placeholder={t('scenarios.target_asset')} /></SelectTrigger>
              <SelectContent>
                {assets.map((a) => (
                  <SelectItem key={a.id} value={a.id.toString()}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.amount')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.amount`}
          render={({ field }) => (
            <NumberInput type="number" min={0} placeholder={t('placeholders.enter_amount')} value={field.value} onChange={field.onChange} />
          )}
        />
      </div>
    </>
  );
}

// --- MARKET_CRASH ---

function MarketCrashFields({
  index, form,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
}) {
  const { t } = useTranslation();
  const affectedTypes = (form.watch(`actions.${index}.affected_asset_types`) ?? []) as string[];

  const toggleType = (type: string) => {
    const current = [...affectedTypes];
    const idx = current.indexOf(type);
    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      current.push(type);
    }
    form.setValue(`actions.${index}.affected_asset_types`, current.length > 0 ? current : null);
  };

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.crash_pct')}</Label>
        <Controller
          control={form.control}
          name={`actions.${index}.crash_pct`}
          render={({ field }) => (
            <NumberInput
              type="number"
              min={1}
              max={100}
              step="1"
              placeholder="30"
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('scenarios.crash_date')}</Label>
        <Input type="date" {...form.register(`actions.${index}.crash_date`)} />
      </div>
      <div className="space-y-2">
        <Label className="text-xs">{t('scenarios.affected_types')}</Label>
        <div className="flex flex-wrap gap-3">
          {ASSET_TYPES_LIST.map((at) => (
            <label key={at} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={affectedTypes.includes(at)}
                onCheckedChange={() => toggleType(at)}
              />
              {t(`asset_types.${at}`)}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {affectedTypes.length === 0 ? t('scenarios.all_types') : ''}
        </p>
      </div>
    </>
  );
}

// --- ADD_REVENUE_STREAM ---

function AddRevenueStreamFields({
  index, form, assets,
}: {
  index: number;
  form: ReturnType<typeof useForm<ScenarioFormValues>>;
  assets: { id: number; name: string }[];
}) {
  const { t } = useTranslation();
  const params = (form.watch(`actions.${index}.params`) ?? {}) as Record<string, unknown>;
  const setParam = (key: string, val: unknown) => {
    form.setValue(`actions.${index}.params`, { ...params, [key]: val });
  };

  const NONE_VALUE = '__none__';

  return (
    <>
      <div className="space-y-1">
        <Label className="text-xs">{t('revenue.stream_type')}</Label>
        <Select onValueChange={(v) => setParam('stream_type', v)} value={(params.stream_type as string) ?? ''}>
          <SelectTrigger className="w-full"><SelectValue placeholder={t('placeholders.select_type')} /></SelectTrigger>
          <SelectContent>
            {STREAM_TYPES_LIST.map((st) => (
              <SelectItem key={st} value={st}>{t(`revenue.${st}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.name')}</Label>
        <Input placeholder={t('placeholders.enter_name')} value={(params.name as string) ?? ''} onChange={(e) => setParam('name', e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.amount')}</Label>
        <NumberInput type="number" min={0} value={(params.amount as number) ?? undefined} onChange={(v) => setParam('amount', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('revenue.period')}</Label>
        <Select onValueChange={(v) => setParam('period', v)} value={(params.period as string) ?? Period.MONTHLY}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PERIODS_LIST.map((p) => (
              <SelectItem key={p} value={p}>{t(`period.${p}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.start_date')}</Label>
        <Input type="date" value={(params.start_date as string) ?? ''} onChange={(e) => setParam('start_date', e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('fields.end_date')}</Label>
        <Input type="date" value={(params.end_date as string) ?? ''} onChange={(e) => setParam('end_date', e.target.value || null)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('revenue.growth_rate')}</Label>
        <NumberInput type="number" step="0.1" value={(params.growth_rate as number) ?? undefined} onChange={(v) => setParam('growth_rate', v)} />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('revenue.linked_asset')}</Label>
        <Select
          onValueChange={(v) => setParam('asset_id', v === NONE_VALUE ? null : Number(v))}
          value={(params.asset_id as number)?.toString() ?? NONE_VALUE}
        >
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_VALUE}>{t('cashFlow.noLink')}</SelectItem>
            {assets.map((a) => (
              <SelectItem key={a.id} value={a.id.toString()}>{a.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
}
