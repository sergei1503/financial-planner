import type { ReactNode } from 'react';

interface PageContainerProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}

export function PageContainer({ title, action, children }: PageContainerProps) {
  return (
    <div className="flex-1 p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}
