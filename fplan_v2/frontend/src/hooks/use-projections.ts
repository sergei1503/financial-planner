import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { projectionsApi } from '@/api/projections';
import type { ProjectionRequest } from '@/api/types';

export function useRunProjection() {
  return useMutation({
    mutationFn: (params: ProjectionRequest = {}) => projectionsApi.run(params),
  });
}

export function useProjectionQuery(params: ProjectionRequest = {}) {
  return useQuery({
    queryKey: ['projection', params],
    queryFn: () => projectionsApi.run(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    // Keep the previous projection visible while a refetch (after an edit) is in flight,
    // so the chart doesn't blank out during the ~0.2-1.9s recompute.
    placeholderData: keepPreviousData,
  });
}
