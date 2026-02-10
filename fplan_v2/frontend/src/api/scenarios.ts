import apiClient from './client';
import type {
  ScenarioCreate,
  ScenarioUpdate,
  ScenarioResponse,
  ProjectionRequest,
  ProjectionResponse,
} from './types';

export const scenariosApi = {
  list: () =>
    apiClient.get<ScenarioResponse[]>('/api/scenarios/').then(r => r.data),

  get: (id: number) =>
    apiClient.get<ScenarioResponse>(`/api/scenarios/${id}`).then(r => r.data),

  create: (data: ScenarioCreate) =>
    apiClient.post<ScenarioResponse>('/api/scenarios/', data).then(r => r.data),

  update: (id: number, data: ScenarioUpdate) =>
    apiClient.put<ScenarioResponse>(`/api/scenarios/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/scenarios/${id}`),

  run: (id: number, params?: ProjectionRequest) =>
    apiClient.post<ProjectionResponse>(`/api/scenarios/${id}/run`, params ?? {}).then(r => r.data),
};
