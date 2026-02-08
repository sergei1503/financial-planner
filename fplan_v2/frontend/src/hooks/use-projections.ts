import { useMutation, useQuery } from '@tanstack/react-query';
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
  });
}
