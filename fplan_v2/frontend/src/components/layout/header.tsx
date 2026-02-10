import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { UserButton } from '@clerk/clerk-react';
import { Moon, Sun, LogIn } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDemoMode } from '@/contexts/demo-context';

const clerkEnabled = !!import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

export function Header() {
  const { t, i18n } = useTranslation();
  const { isDemo } = useDemoMode();
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains('dark')
  );

  const toggleLanguage = () => {
    const newLang = i18n.language === 'he' ? 'en' : 'he';
    i18n.changeLanguage(newLang);
    document.documentElement.dir = newLang === 'he' ? 'rtl' : 'ltr';
    document.documentElement.lang = newLang;
  };

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [dark]);

  return (
    <header className="flex items-center justify-between border-b px-6 py-3">
      <h1 className="text-lg font-semibold">{t('app.title')}</h1>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setDark(d => !d)}
          aria-label="Toggle theme"
        >
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
        <Button variant="outline" size="sm" onClick={toggleLanguage}>
          {i18n.language === 'he' ? 'EN' : '\u05E2\u05D1'}
        </Button>
        {clerkEnabled && isDemo && (
          <Button variant="default" size="sm" asChild>
            <Link to="/sign-in">
              <LogIn className="me-1 size-4" />
              {t('demo.sign_in')}
            </Link>
          </Button>
        )}
        {clerkEnabled && !isDemo && <div dir="ltr"><UserButton afterSignOutUrl="/" /></div>}
      </div>
    </header>
  );
}
