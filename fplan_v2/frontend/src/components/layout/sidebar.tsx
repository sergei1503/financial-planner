import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

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

export function Sidebar() {
  return (
    <aside className="hidden md:block w-56 border-e bg-muted/40 p-4">
      <NavContent />
    </aside>
  );
}

export { NavContent, navItems };
