interface ChartTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  formatValue?: (value: number) => string;
  measurementPrefix?: string; // e.g., '_m_'
  measurementLabel?: string; // e.g., '(בפועל)'
}

export function ChartTooltip({
  active,
  payload,
  label,
  formatValue,
  measurementPrefix = '_m_',
  measurementLabel = '(בפועל)',
}: ChartTooltipProps) {

  if (!active || !payload || payload.length === 0) {
    return null;
  }

  // Filter out entries with undefined/null/NaN values
  // Also exclude entries where dataKey is 'date' or name/dataKey is the label
  const validEntries = payload.filter((entry: any) => {
    const value = entry.value;
    const nameStr = String(entry.name || entry.dataKey);

    // Exclude if value is invalid
    if (value === null || value === undefined || Number.isNaN(value)) {
      return false;
    }

    // Exclude if the entry is the date/label field itself
    if (nameStr === 'date' || nameStr === label) {
      return false;
    }

    return true;
  });

  if (validEntries.length === 0) {
    return null;
  }

  const defaultFormatter = (val: number) => {
    return new Intl.NumberFormat('he-IL', {
      style: 'currency',
      currency: 'ILS',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(val);
  };

  const formatter = formatValue || defaultFormatter;

  return (
    <div className="rounded-lg border bg-background p-3 shadow-md">
      <p className="mb-2 font-semibold text-sm">{label}</p>
      <div className="space-y-1">
        {validEntries.map((entry: any, index: number) => {
          const nameStr = String(entry.name || entry.dataKey);
          const isMeasurement = nameStr.startsWith(measurementPrefix);
          const displayName = isMeasurement
            ? `${nameStr.slice(measurementPrefix.length)} ${measurementLabel}`
            : nameStr;

          return (
            <div key={`${nameStr}-${index}`} className="flex items-center gap-2 text-sm">
              <div
                className="size-3 rounded-sm flex-shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-muted-foreground">{displayName}:</span>
              <span className="font-medium" dir="ltr">
                {formatter(Number(entry.value))}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
