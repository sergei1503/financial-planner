import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Header } from './header';
import { Sidebar, NavContent } from './sidebar';

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {/* Mobile menu button */}
        <div className="md:hidden fixed bottom-4 start-4 z-50">
          <Button
            size="icon"
            className="rounded-full shadow-lg size-12"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-5" />
          </Button>
        </div>

        {/* Mobile sidebar sheet */}
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="right" className="w-64 p-4">
            <SheetHeader>
              <SheetTitle className="text-start">Menu</SheetTitle>
            </SheetHeader>
            <div className="mt-4">
              <NavContent onItemClick={() => setMobileOpen(false)} />
            </div>
          </SheetContent>
        </Sheet>

        <Sidebar />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <Toaster position="top-center" dir="rtl" />
    </div>
  );
}
