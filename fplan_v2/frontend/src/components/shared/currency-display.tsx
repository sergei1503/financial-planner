import { formatCurrency } from '@/lib/formatters';

interface CurrencyDisplayProps {
  value: number;
  currency?: string;
  className?: string;
}

export function CurrencyDisplay({ value, currency = 'ILS', className }: CurrencyDisplayProps) {
  return (
    <span dir="ltr" className={`inline-block ${className || ''}`}>
      {formatCurrency(value, currency)}
    </span>
  );
}
