import apiClient from './client';
import type { AssetCreate, AssetUpdate, AssetResponse } from './types';

export const assetsApi = {
  list: () =>
    apiClient.get<AssetResponse[]>('/api/assets/').then(r => r.data),

  get: (id: number) =>
    apiClient.get<AssetResponse>(`/api/assets/${id}`).then(r => r.data),

  create: (data: AssetCreate) =>
    apiClient.post<AssetResponse>('/api/assets/', data).then(r => r.data),

  update: (id: number, data: AssetUpdate) =>
    apiClient.put<AssetResponse>(`/api/assets/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/assets/${id}`),
};
