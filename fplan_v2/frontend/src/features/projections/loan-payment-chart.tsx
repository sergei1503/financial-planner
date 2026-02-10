import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { LoanProjection } from '@/api/types';

interface LoanPaymentChartProps {
  loanProjections: LoanProjection[];
  scenarioLoanProjections?: LoanProjection[];
  scenarioName?: string;
}

const COLORS: Record<string, string> = {
  fixed: '#3b82f6',
  prime_pegged: '#f59e0b',
  cpi_pegged: '#8b5cf6',
  variable: '#06b6d4',
};

const FALLBACK_COLORS = ['#3b82f6', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];

function formatChartDate(dateStr: string) {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(-2)}`;
}

function formatYAxis(value: number) {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

function formatTooltipValue(value: number) {
  return new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS',
    maximumFractionDigits: 0,
  }).format(value);
}

export function LoanPaymentChart({ loanProjections, scenarioLoanProjections, scenarioName }: LoanPaymentChartProps) {
  const { t } = useTranslation();

  if (loanProjections.length === 0) return null;

  // Build merged data: each date has a payment value for each loan
  const dateMap = new Map<string, Record<string, number>>();
  for (const loan of loanProjections) {
    for (const point of loan.payment_series) {
      const existing = dateMap.get(point.date) ?? {};
      existing[loan.loan_name] = point.value;
      dateMap.set(point.date, existing);
    }
  }

  const chartData = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({
      date: formatChartDate(date),
      ...values,
    }));

  // Merge scenario payment data if available
  const hasScenario = scenarioLoanProjections && scenarioLoanProjections.length > 0;
  if (hasScenario) {
    const dateIndex = new Map(chartData.map((d, i) => [d.date, i]));
    for (const loan of scenarioLoanProjections) {
      const key = `_s_${loan.loan_name}`;
      for (const point of loan.payment_series) {
        const formatted = formatChartDate(point.date);
        const idx = dateIndex.get(formatted);
        if (idx !== undefined) {
          (chartData[idx] as Record<string, unknown>)[key] = point.value;
        }
      }
    }
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis tickFormatter={formatYAxis} />
        <Tooltip formatter={(value) => formatTooltipValue(Number(value))} />
        <Legend />
        {loanProjections.map((loan, idx) => (
          <Bar
            key={loan.loan_id}
            dataKey={loan.loan_name}
            name={`${loan.loan_name} (${t(`loan_types.${loan.loan_type}`)})`}
            fill={COLORS[loan.loan_type] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length]}
            stackId="payments"
          />
        ))}
        {hasScenario && scenarioLoanProjections!.map((loan, idx) => (
          <Bar
            key={`scenario-${loan.loan_id}`}
            dataKey={`_s_${loan.loan_name}`}
            name={`${scenarioName ?? t('scenarios.scenario')}: ${loan.loan_name}`}
            fill={COLORS[loan.loan_type] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length]}
            fillOpacity={0.35}
            stackId="scenario-payments"
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
