import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { historicalMeasurementsApi } from '@/api/historical-measurements';
import type { HistoricalMeasurementCreate, HistoricalMeasurementUpdate } from '@/api/types';

export function useHistoricalMeasurements(entityType: string, entityId: number) {
  return useQuery({
    queryKey: ['historical-measurements', entityType, entityId],
    queryFn: () => historicalMeasurementsApi.listByEntity(entityType, entityId),
    enabled: !!entityType && !!entityId,
  });
}

export function useCreateMeasurement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: HistoricalMeasurementCreate) =>
      historicalMeasurementsApi.create(data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: ['historical-measurements', variables.entity_type, variables.entity_id],
      });
    },
  });
}

export function useUpdateMeasurement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: HistoricalMeasurementUpdate }) =>
      historicalMeasurementsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['historical-measurements'] });
    },
  });
}

export function useDeleteMeasurement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => historicalMeasurementsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['historical-measurements'] });
    },
  });
}
