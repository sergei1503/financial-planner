import apiClient from './client';
import type {
  HistoricalMeasurementCreate,
  HistoricalMeasurementUpdate,
  HistoricalMeasurementResponse,
} from './types';

export const historicalMeasurementsApi = {
  create: (data: HistoricalMeasurementCreate) =>
    apiClient.post<HistoricalMeasurementResponse>('/api/historical-measurements/', data).then(r => r.data),

  get: (id: number) =>
    apiClient.get<HistoricalMeasurementResponse>(`/api/historical-measurements/${id}`).then(r => r.data),

  listAll: () =>
    apiClient.get<HistoricalMeasurementResponse[]>('/api/historical-measurements/').then(r => r.data),

  listByEntity: (entityType: string, entityId: number) =>
    apiClient.get<HistoricalMeasurementResponse[]>(
      `/api/historical-measurements/entity/${entityType}/${entityId}`
    ).then(r => r.data),

  update: (id: number, data: HistoricalMeasurementUpdate) =>
    apiClient.put<HistoricalMeasurementResponse>(`/api/historical-measurements/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/historical-measurements/${id}`),
};
