import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Area,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { AssetProjection } from '@/api/types';
import { ChartTooltip } from './chart-tooltip';
import { Button } from '@/components/ui/button';

interface AssetBreakdownChartProps {
  assetProjections: AssetProjection[];
  historicalAssetProjections?: AssetProjection[];
}

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6'];

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

export function AssetBreakdownChart({ assetProjections }: AssetBreakdownChartProps) {
  const { t } = useTranslation();
  const [hiddenAssets, setHiddenAssets] = useState<Set<string>>(new Set());

  const toggleAsset = useCallback((assetName: string) => {
    setHiddenAssets(prev => {
      const next = new Set(prev);
      if (next.has(assetName)) {
        next.delete(assetName);
      } else {
        next.add(assetName);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (hiddenAssets.size === 0) {
      // Hide all
      setHiddenAssets(new Set(assetProjections.map(a => a.asset_name)));
    } else {
      // Show all
      setHiddenAssets(new Set());
    }
  }, [hiddenAssets.size, assetProjections]);

  const handleLegendDoubleClick = useCallback(() => {
    toggleAll();
  }, [toggleAll]);

  if (assetProjections.length === 0) return null;

  // Build merged data: each date has a value for each asset
  const dateSet = new Map<string, Record<string, number>>();
  for (const asset of assetProjections) {
    for (const point of asset.time_series) {
      const existing = dateSet.get(point.date) ?? {};
      existing[asset.asset_name] = point.value;
      dateSet.set(point.date, existing);
    }
  }

  const chartData: Array<{ date: string; [key: string]: number | string }> = Array.from(dateSet.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({
      date: formatChartDate(date),
      ...values,
    }));

  // Build measurement marker data keyed by asset name
  // Each measurement becomes a data point with a unique key for the scatter layer
  const measurementData: Record<string, number>[] = [];
  const hasMeasurements = assetProjections.some(a => a.measurements && a.measurements.length > 0);

  if (hasMeasurements) {
    for (const asset of assetProjections) {
      if (!asset.measurements) continue;
      for (const m of asset.measurements) {
        const formattedDate = formatChartDate(m.date);
        const markerKey = `_m_${asset.asset_name}`;
        measurementData.push({
          date: formattedDate as unknown as number,
          [markerKey]: m.actual_value,
        } as Record<string, number>);
      }
    }
  }

  // Merge measurement data into chart data
  if (measurementData.length > 0) {
    const dateIndex = new Map(chartData.map((d, i) => [d.date, i]));
    for (const md of measurementData) {
      const dateKey = md.date as unknown as string;
      const idx = dateIndex.get(dateKey);
      if (idx !== undefined) {
        // Merge measurement data, keeping the formatted date string
        Object.assign(chartData[idx], { ...md, date: dateKey });
      }
    }
  }

  // Fill missing asset values with 0 to prevent jumps in stacked areas
  const assetNames = assetProjections.map(a => a.asset_name);
  for (const row of chartData) {
    for (const name of assetNames) {
      if (row[name] === undefined) {
        row[name] = 0;
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
            data-testid="toggle-all-assets-button"
          >
            {hiddenAssets.size === 0 ? t('charts.hide_all') : t('charts.show_all')}
          </Button>
        </div>
        <div
          className="flex flex-wrap gap-3 justify-center"
          onDoubleClick={handleLegendDoubleClick}
        >
          {assetProjections.map((asset, idx) => {
            const color = COLORS[idx % COLORS.length];
            const isHidden = hiddenAssets.has(asset.asset_name);
            return (
              <button
                key={asset.asset_id}
                type="button"
                onClick={() => toggleAsset(asset.asset_name)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-opacity cursor-pointer border-0 bg-transparent ${isHidden ? 'opacity-30 line-through' : 'opacity-100'}`}
                data-testid={`asset-legend-${asset.asset_id}`}
              >
                <span
                  className="inline-block w-3 h-3 rounded-sm shrink-0"
                  style={{ backgroundColor: color }}
                />
                {asset.asset_name}
              </button>
            );
          })}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis tickFormatter={formatYAxis} />
          <Tooltip content={<ChartTooltip formatValue={formatTooltipValue} />} />
          {assetProjections.map((asset, idx) => (
            <Area
              key={asset.asset_id}
              type="monotone"
              dataKey={asset.asset_name}
              stackId="1"
              fill={COLORS[idx % COLORS.length]}
              stroke={COLORS[idx % COLORS.length]}
              fillOpacity={hiddenAssets.has(asset.asset_name) ? 0 : 0.6}
              strokeOpacity={hiddenAssets.has(asset.asset_name) ? 0 : 1}
              hide={hiddenAssets.has(asset.asset_name)}
            />
          ))}
          {hasMeasurements && assetProjections.map((asset, idx) => {
            if (!asset.measurements || asset.measurements.length === 0) return null;
            if (hiddenAssets.has(asset.asset_name)) return null;
            return (
              <Scatter
                key={`scatter-${asset.asset_id}`}
                dataKey={`_m_${asset.asset_name}`}
                fill={COLORS[idx % COLORS.length]}
                stroke="#fff"
                strokeWidth={2}
                r={5}
                shape="diamond"
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
