import { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { TimeSeriesDataPoint, CashFlowBreakdown } from '@/api/types';
import { ChartTooltip } from './chart-tooltip';
import { Button } from '@/components/ui/button';

interface CashFlowChartProps {
  data: TimeSeriesDataPoint[];
  breakdown?: CashFlowBreakdown | null;
  historicalData?: TimeSeriesDataPoint[];
  scenarioBreakdown?: CashFlowBreakdown | null;
  scenarioName?: string;
}

const COLORS = ['#22c55e', '#3b82f6', '#f97316', '#8b5cf6', '#ec4899', '#06b6d4', '#ef4444', '#14b8a6', '#eab308'];

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

export function CashFlowChart({ data, breakdown, scenarioBreakdown, scenarioName }: CashFlowChartProps) {
  const { t } = useTranslation();
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());

  // Build per-source series from breakdown items, deduplicating by source_name
  const sources = useMemo(() => {
    if (!breakdown?.items?.length) return [];
    // Deduplicate items with the same source_name by keeping only the first
    const seen = new Set<string>();
    return breakdown.items.filter(item => {
      if (seen.has(item.source_name)) return false;
      seen.add(item.source_name);
      return item.time_series.some(p => Number(p.value) !== 0);
    });
  }, [breakdown]);

  const chartData = useMemo(() => {
    if (sources.length > 0) {
      // Key by raw ISO date for correct chronological sorting
      const dateMap = new Map<string, Record<string, number>>();

      for (const item of sources) {
        for (const point of item.time_series) {
          const rawDate = point.date; // ISO string e.g. "2025-01-01"
          const existing = dateMap.get(rawDate) ?? {};
          const val = Number(point.value);
          existing[item.source_name] = item.source_type === 'expense' ? -val : val;
          dateMap.set(rawDate, existing);
        }
      }

      if (breakdown?.net_series) {
        for (const point of breakdown.net_series) {
          const existing = dateMap.get(point.date) ?? {};
          existing['__net__'] = Number(point.value);
          dateMap.set(point.date, existing);
        }
      }

      // Sort by ISO date (chronological), then format for display
      return Array.from(dateMap.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([isoDate, values]) => ({ date: formatChartDate(isoDate), ...values }));
    }

    // Fallback: net-only
    return data.map(point => ({
      date: formatChartDate(point.date),
      __net__: Number(point.value),
    }));
  }, [data, breakdown, sources]);

  // Merge scenario net cash flow into chart data
  const hasScenario = scenarioBreakdown?.net_series && scenarioBreakdown.net_series.length > 0;
  const chartDataWithScenario = useMemo(() => {
    if (!hasScenario) return chartData;
    const scenarioMap = new Map(
      scenarioBreakdown!.net_series.map(p => [formatChartDate(p.date), Number(p.value)])
    );
    return chartData.map(row => ({
      ...row,
      __scenario_net__: scenarioMap.get(row.date as string),
    }));
  }, [chartData, hasScenario, scenarioBreakdown]);

  const toggleSeries = useCallback((name: string) => {
    setHiddenSeries(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const allNames = useMemo(() =>
    sources.map(s => s.source_name).concat(['__net__']),
    [sources]
  );

  const toggleAll = useCallback(() => {
    if (hiddenSeries.size === 0) {
      setHiddenSeries(new Set(allNames));
    } else {
      setHiddenSeries(new Set());
    }
  }, [hiddenSeries.size, allNames]);

  const netLabel = t('charts.net_cash_flow', 'Net Cash Flow');

  return (
    <div>
      {/* Clickable legend */}
      <div className="flex flex-col gap-2 mb-4" dir="ltr">
        <div className="flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleAll}
            className="text-xs h-7"
          >
            {hiddenSeries.size === 0 ? t('charts.hide_all') : t('charts.show_all')}
          </Button>
        </div>
        <div className="flex flex-wrap gap-3 justify-center">
          {sources.map((item, idx) => {
            const color = COLORS[idx % COLORS.length];
            const isHidden = hiddenSeries.has(item.source_name);
            return (
              <button
                key={item.source_name}
                type="button"
                onClick={() => toggleSeries(item.source_name)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-opacity cursor-pointer border-0 bg-transparent ${isHidden ? 'opacity-30 line-through' : 'opacity-100'}`}
              >
                <span
                  className="inline-block w-3 h-3 rounded-sm shrink-0"
                  style={{ backgroundColor: color }}
                />
                {item.source_name}
              </button>
            );
          })}
          {/* Net line legend entry */}
          <button
            type="button"
            onClick={() => toggleSeries('__net__')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-opacity cursor-pointer border-0 bg-transparent ${hiddenSeries.has('__net__') ? 'opacity-30 line-through' : 'opacity-100'}`}
          >
            <span
              className="inline-block w-3 h-3 rounded-sm shrink-0"
              style={{ backgroundColor: '#6b7280' }}
            />
            {netLabel}
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={chartDataWithScenario} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis tickFormatter={formatYAxis} />
          <Tooltip content={<ChartTooltip formatValue={formatTooltipValue} />} />
          {sources.map((item, idx) => (
            <Line
              key={item.source_name}
              type="monotone"
              dataKey={item.source_name}
              stroke={COLORS[idx % COLORS.length]}
              strokeWidth={2}
              dot={false}
              hide={hiddenSeries.has(item.source_name)}
            />
          ))}
          <Line
            type="monotone"
            dataKey="__net__"
            name={netLabel}
            stroke="#6b7280"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            hide={hiddenSeries.has('__net__')}
          />
          {hasScenario && (
            <Line
              type="monotone"
              dataKey="__scenario_net__"
              name={`${scenarioName ?? t('scenarios.scenario')}: ${netLabel}`}
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="8 4"
              dot={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
