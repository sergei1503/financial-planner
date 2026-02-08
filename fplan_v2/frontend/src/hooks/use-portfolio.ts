import { useQuery } from '@tanstack/react-query';
import { projectionsApi } from '@/api/projections';

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ['portfolio-summary'],
    queryFn: () => projectionsApi.portfolioSummary(),
  });
}
