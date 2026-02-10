import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { LoanProjection } from '@/api/types';
import { ChartTooltip } from './chart-tooltip';
import { Button } from '@/components/ui/button';

interface LoanAmortizationChartProps {
  loanProjections: LoanProjection[];
  historicalLoanProjections?: LoanProjection[];
  scenarioLoanProjections?: LoanProjection[];
  scenarioName?: string;
}

const COLORS = ['#ef4444', '#f97316', '#8b5cf6', '#ec4899', '#06b6d4', '#14b8a6', '#3b82f6', '#22c55e'];

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

export function LoanAmortizationChart({ loanProjections, scenarioLoanProjections, scenarioName }: LoanAmortizationChartProps) {
  const { t } = useTranslation();
  const [hiddenLoans, setHiddenLoans] = useState<Set<string>>(new Set());

  const toggleLoan = useCallback((loanName: string) => {
    setHiddenLoans(prev => {
      const next = new Set(prev);
      if (next.has(loanName)) {
        next.delete(loanName);
      } else {
        next.add(loanName);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (hiddenLoans.size === 0) {
      // Hide all
      setHiddenLoans(new Set(loanProjections.map(l => l.loan_name)));
    } else {
      // Show all
      setHiddenLoans(new Set());
    }
  }, [hiddenLoans.size, loanProjections]);

  const handleLegendDoubleClick = useCallback(() => {
    toggleAll();
  }, [toggleAll]);

  if (loanProjections.length === 0) return null;

  // Build merged data: each date has a balance value for each loan
  const dateMap = new Map<string, Record<string, number>>();
  for (const loan of loanProjections) {
    for (const point of loan.balance_series) {
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

  // Merge measurement markers into chart data
  const hasMeasurements = loanProjections.some(l => l.measurements && l.measurements.length > 0);
  if (hasMeasurements) {
    const dateIndex = new Map(chartData.map((d, i) => [d.date, i]));
    for (const loan of loanProjections) {
      if (!loan.measurements) continue;
      for (const m of loan.measurements) {
        const formattedDate = formatChartDate(m.date);
        const idx = dateIndex.get(formattedDate);
        if (idx !== undefined) {
          (chartData[idx] as Record<string, unknown>)[`_m_${loan.loan_name}`] = m.actual_value;
        }
      }
    }
  }

  // Merge scenario loan data if available
  const hasScenario = scenarioLoanProjections && scenarioLoanProjections.length > 0;
  if (hasScenario) {
    const dateIndex = new Map(chartData.map((d, i) => [d.date, i]));
    for (const loan of scenarioLoanProjections) {
      const key = `_s_${loan.loan_name}`;
      for (const point of loan.balance_series) {
        const formatted = formatChartDate(point.date);
        const idx = dateIndex.get(formatted);
        if (idx !== undefined) {
          (chartData[idx] as Record<string, unknown>)[key] = point.value;
        }
      }
    }
  }

  return (
    <div>
      {/* Custom clickable legend with toggle all controls */}
      <div className="flex flex-col gap-2 mb-4" dir="ltr">
        <div className="flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleAll}
            className="text-xs h-7"
            data-testid="toggle-all-loans-button"
          >
            {hiddenLoans.size === 0 ? t('charts.hide_all') : t('charts.show_all')}
          </Button>
        </div>
        <div
          className="flex flex-wrap gap-3 justify-center"
          onDoubleClick={handleLegendDoubleClick}
        >
          {loanProjections.map((loan, idx) => {
            const color = COLORS[idx % COLORS.length];
            const isHidden = hiddenLoans.has(loan.loan_name);
            return (
              <button
                key={loan.loan_id}
                type="button"
                onClick={() => toggleLoan(loan.loan_name)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-opacity cursor-pointer border-0 bg-transparent ${isHidden ? 'opacity-30 line-through' : 'opacity-100'}`}
                data-testid={`loan-legend-${loan.loan_id}`}
              >
                <span
                  className="inline-block w-3 h-3 rounded-sm shrink-0"
                  style={{ backgroundColor: color }}
                />
                {loan.loan_name}
              </button>
            );
          })}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis tickFormatter={formatYAxis} />
          <Tooltip content={<ChartTooltip formatValue={formatTooltipValue} />} />
          {loanProjections.map((loan, idx) => (
            <Line
              key={loan.loan_id}
              type="monotone"
              dataKey={loan.loan_name}
              stroke={COLORS[idx % COLORS.length]}
              strokeWidth={2}
              dot={false}
              hide={hiddenLoans.has(loan.loan_name)}
            />
          ))}
          {hasMeasurements && loanProjections.map((loan, idx) => {
            if (!loan.measurements || loan.measurements.length === 0) return null;
            if (hiddenLoans.has(loan.loan_name)) return null;
            return (
              <Scatter
                key={`scatter-${loan.loan_id}`}
                dataKey={`_m_${loan.loan_name}`}
                fill={COLORS[idx % COLORS.length]}
                stroke="#fff"
                strokeWidth={2}
                r={5}
                shape="diamond"
              />
            );
          })}
          {hasScenario && scenarioLoanProjections!.map((loan, idx) => {
            if (hiddenLoans.has(loan.loan_name)) return null;
            return (
              <Line
                key={`scenario-${loan.loan_id}`}
                type="monotone"
                dataKey={`_s_${loan.loan_name}`}
                name={`${scenarioName ?? t('scenarios.scenario')}: ${loan.loan_name}`}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={2}
                strokeDasharray="8 4"
                dot={false}
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
