import { useTranslation } from 'react-i18next';
import { formatDate } from '@/lib/formatters';

interface DateDisplayProps {
  date: string;
  className?: string;
}

export function DateDisplay({ date, className }: DateDisplayProps) {
  const { i18n } = useTranslation();
  const locale = i18n.language === 'he' ? 'he-IL' : 'en-US';
  return <span className={className}>{formatDate(date, locale)}</span>;
}
