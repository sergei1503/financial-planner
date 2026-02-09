import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDemoMode } from '@/contexts/demo-context';

const DISMISSED_KEY = 'demo-banner-dismissed';

export function DemoBanner() {
  const { isDemo } = useDemoMode();
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISSED_KEY) === '1'
  );

  if (!isDemo || dismissed) return null;

  const dismiss = () => {
    sessionStorage.setItem(DISMISSED_KEY, '1');
    setDismissed(true);
  };

  return (
    <div className="flex items-center justify-center gap-3 bg-amber-100 px-4 py-2 text-sm text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">
      <span>{t('demo.banner')}</span>
      <Button variant="outline" size="sm" asChild className="h-7 text-xs">
        <Link to="/sign-in">{t('demo.sign_in')}</Link>
      </Button>
      <button
        onClick={dismiss}
        className="ms-auto rounded p-0.5 hover:bg-amber-200 dark:hover:bg-amber-800"
        aria-label="Dismiss"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
