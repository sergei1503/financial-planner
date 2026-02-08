import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { TimeSeriesDataPoint, MeasurementMarker } from '@/api/types';
import { ChartTooltip } from './chart-tooltip';

interface NetWorthChartProps {
  netWorth: TimeSeriesDataPoint[];
  totalAssets: TimeSeriesDataPoint[];
  totalLiabilities: TimeSeriesDataPoint[];
  measurementMarkers?: MeasurementMarker[];
  historicalNetWorth?: TimeSeriesDataPoint[];
  historicalAsOfDate?: string | null;
}

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

export function NetWorthChart({
  netWorth,
  totalAssets,
  totalLiabilities,
  measurementMarkers = [],
  historicalNetWorth,
}: NetWorthChartProps) {
  const { t } = useTranslation();

  type MergedData = {
    date: string;
    netWorth: number;
    assets: number;
    liabilities: number;
    historicalNetWorth?: number;
  };

  const merged: MergedData[] = netWorth.map((point, i) => ({
    date: formatChartDate(point.date),
    netWorth: point.value,
    assets: totalAssets[i]?.value ?? 0,
    liabilities: totalLiabilities[i]?.value ?? 0,
  }));

  // Merge historical data if available
  if (historicalNetWorth && historicalNetWorth.length > 0) {
    const historicalMap = new Map(
      historicalNetWorth.map((p) => [formatChartDate(p.date), p.value])
    );

    merged.forEach((point) => {
      const historicalValue = historicalMap.get(point.date);
      if (historicalValue !== undefined) {
        point.historicalNetWorth = historicalValue;
      }
    });
  }

  // Group measurements by date, sum by entity_type for aggregated markers
  const hasMeasurements = measurementMarkers.length > 0;
  if (hasMeasurements) {
    const dateIndex = new Map(merged.map((d, i) => [d.date, i]));
    for (const m of measurementMarkers) {
      const formattedDate = formatChartDate(m.date);
      const idx = dateIndex.get(formattedDate);
      if (idx !== undefined) {
        const row = merged[idx] as Record<string, unknown>;
        if (m.entity_type === 'asset') {
          row._m_asset = m.actual_value;
          row._m_asset_name = m.entity_name;
        } else {
          row._m_loan = m.actual_value;
          row._m_loan_name = m.entity_name;
        }
      }
    }
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <ComposedChart data={merged} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis tickFormatter={formatYAxis} />
        <Tooltip content={<ChartTooltip formatValue={formatTooltipValue} />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="netWorth"
          name={t('charts.net_worth')}
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="assets"
          name={t('charts.total_assets')}
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="liabilities"
          name={t('charts.total_liabilities')}
          stroke="#ef4444"
          strokeWidth={2}
          dot={false}
        />
        {historicalNetWorth && historicalNetWorth.length > 0 && (
          <Line
            type="monotone"
            dataKey="historicalNetWorth"
            name={t('charts.historical_projection')}
            stroke="#9333ea"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />
        )}
        {hasMeasurements && (
          <>
            <Scatter
              dataKey="_m_asset"
              fill="#22c55e"
              stroke="#fff"
              strokeWidth={2}
              r={6}
              shape="diamond"
              legendType="none"
            />
            <Scatter
              dataKey="_m_loan"
              fill="#ef4444"
              stroke="#fff"
              strokeWidth={2}
              r={6}
              shape="diamond"
              legendType="none"
            />
          </>
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
