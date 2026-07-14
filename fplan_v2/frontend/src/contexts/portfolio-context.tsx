import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { portfoliosApi } from '@/api/portfolios';
import { getActivePortfolioId, setActivePortfolioId } from '@/api/client';
import type { Portfolio } from '@/api/types';

interface PortfolioContextValue {
  portfolios: Portfolio[];
  activeId: number | null;
  activePortfolio: Portfolio | null;
  isLoading: boolean;
  /** Switch the active portfolio and refetch all portfolio-scoped data. */
  switchPortfolio: (id: number) => void;
}

const PortfolioContext = createContext<PortfolioContextValue>({
  portfolios: [],
  activeId: null,
  activePortfolio: null,
  isLoading: true,
  switchPortfolio: () => {},
});

export function PortfolioProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { data: portfolios, isLoading } = useQuery({
    queryKey: ['portfolios'],
    queryFn: () => portfoliosApi.list(),
  });

  // Start from whatever the api client already restored from localStorage, so the very
  // first render agrees with the header the client is already sending.
  const [activeId, setActiveIdState] = useState<number | null>(() => getActivePortfolioId());

  // Keep the api client's header in sync with our state.
  useEffect(() => {
    setActivePortfolioId(activeId);
  }, [activeId]);

  // Once portfolios load, make sure the active id points at a real portfolio. If the stored
  // id was deleted elsewhere, fall back to the default portfolio and refetch scoped data.
  useEffect(() => {
    if (!portfolios || portfolios.length === 0) return;
    const stillExists = activeId != null && portfolios.some(p => p.id === activeId);
    if (stillExists) return;

    const fallback = portfolios.find(p => p.is_default) ?? portfolios[0];
    const wasStale = activeId != null; // had a value that no longer resolves
    setActivePortfolioId(fallback.id);
    setActiveIdState(fallback.id);
    if (wasStale) {
      // The effective portfolio changed under us — refresh everything, including
      // inactive queries (some, e.g. projections, opt out of refetch-on-mount).
      queryClient.invalidateQueries({ refetchType: 'all' });
    }
  }, [portfolios, activeId, queryClient]);

  const switchPortfolio = useCallback(
    (id: number) => {
      if (id === activeId) return;
      // Update the client header synchronously so the refetches below carry the new portfolio.
      setActivePortfolioId(id);
      setActiveIdState(id);
      // Portfolio-scoped queries have no portfolio in their key, so invalidate broadly.
      // refetchType:'all' also refetches inactive queries (e.g. projection charts, which
      // opt out of refetch-on-mount) so navigating to them shows the new portfolio, not stale data.
      queryClient.invalidateQueries({ refetchType: 'all' });
    },
    [activeId, queryClient]
  );

  const value = useMemo<PortfolioContextValue>(() => {
    const list = portfolios ?? [];
    return {
      portfolios: list,
      activeId,
      activePortfolio: list.find(p => p.id === activeId) ?? null,
      isLoading,
      switchPortfolio,
    };
  }, [portfolios, activeId, isLoading, switchPortfolio]);

  return (
    <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>
  );
}

export function usePortfolioContext() {
  return useContext(PortfolioContext);
}
