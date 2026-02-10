import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scenariosApi } from '@/api/scenarios';
import type { ScenarioCreate, ScenarioUpdate, ProjectionRequest } from '@/api/types';

export function useScenarios() {
  return useQuery({
    queryKey: ['scenarios'],
    queryFn: () => scenariosApi.list(),
  });
}

export function useScenario(id: number | null) {
  return useQuery({
    queryKey: ['scenarios', id],
    queryFn: () => scenariosApi.get(id!),
    enabled: id !== null,
  });
}

export function useCreateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ScenarioCreate) => scenariosApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scenarios'] });
    },
  });
}

export function useUpdateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ScenarioUpdate }) =>
      scenariosApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scenarios'] });
    },
  });
}

export function useDeleteScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scenariosApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scenarios'] });
    },
  });
}

export function useRunScenario() {
  return useMutation({
    mutationFn: ({ id, params }: { id: number; params?: ProjectionRequest }) =>
      scenariosApi.run(id, params),
  });
}
