import apiClient from './client';
import type { RevenueStreamCreate, RevenueStreamUpdate, RevenueStreamResponse } from './types';

export const revenueStreamsApi = {
  list: () =>
    apiClient.get<RevenueStreamResponse[]>('/api/revenue-streams/').then(r => r.data),

  get: (id: number) =>
    apiClient.get<RevenueStreamResponse>(`/api/revenue-streams/${id}`).then(r => r.data),

  create: (data: RevenueStreamCreate) =>
    apiClient.post<RevenueStreamResponse>('/api/revenue-streams/', data).then(r => r.data),

  update: (id: number, data: RevenueStreamUpdate) =>
    apiClient.put<RevenueStreamResponse>(`/api/revenue-streams/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/revenue-streams/${id}`),
};
