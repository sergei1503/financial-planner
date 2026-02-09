import { createContext, useContext, useMemo } from 'react';

interface DemoContextValue {
  isDemo: boolean;
}

const DemoContext = createContext<DemoContextValue>({ isDemo: false });

export function DemoProvider({
  isDemo,
  children,
}: {
  isDemo: boolean;
  children: React.ReactNode;
}) {
  const value = useMemo(() => ({ isDemo }), [isDemo]);
  return (
    <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
  );
}

export function useDemoMode() {
  return useContext(DemoContext);
}
