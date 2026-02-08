import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { revenueStreamsApi } from '@/api/revenue-streams';
import type { RevenueStreamCreate, RevenueStreamUpdate } from '@/api/types';

export function useRevenueStreams() {
  return useQuery({
    queryKey: ['revenue-streams'],
    queryFn: () => revenueStreamsApi.list(),
  });
}

export function useCreateRevenueStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RevenueStreamCreate) =>
      revenueStreamsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['revenue-streams'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useUpdateRevenueStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RevenueStreamUpdate }) =>
      revenueStreamsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['revenue-streams'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useDeleteRevenueStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => revenueStreamsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['revenue-streams'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}
