import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useDemoMode } from '@/contexts/demo-context';
import apiClient from '@/api/client';

const navItems = [
  { path: '/', labelKey: 'nav.dashboard' },
  { path: '/assets', labelKey: 'nav.assets' },
  { path: '/loans', labelKey: 'nav.loans' },
  { path: '/cash-flows', labelKey: 'nav.cash_flows' },
  { path: '/projections', labelKey: 'nav.projections' },
];

function NavContent({ onItemClick }: { onItemClick?: () => void }) {
  const { t } = useTranslation();

  return (
    <nav className="flex flex-col gap-1">
      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          onClick={onItemClick}
          className={({ isActive }) =>
            cn(
              'rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-muted'
            )
          }
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  );
}

function DemoResetButton() {
  const { isDemo } = useDemoMode();
  const { t } = useTranslation();

  if (!isDemo) return null;

  const handleReset = async () => {
    try {
      await apiClient.post('/api/demo/reset');
      toast.success(t('demo.reset_success'));
      // Reload to refresh all queries
      window.location.reload();
    } catch {
      toast.error(t('messages.error_saving'));
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className="w-full justify-start gap-2"
      onClick={handleReset}
    >
      <RotateCcw className="size-3.5" />
      {t('demo.reset')}
    </Button>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex md:flex-col md:justify-between w-56 border-e bg-muted/40 p-4">
      <NavContent />
      <DemoResetButton />
    </aside>
  );
}

export { NavContent, navItems };
