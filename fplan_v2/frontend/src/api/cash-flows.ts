import apiClient from './client';
import type { CashFlowResponse } from './types';

type CashFlowCreate = Omit<CashFlowResponse, 'id' | 'user_id' | 'created_at'>;
type CashFlowUpdate = Partial<CashFlowCreate>;

export const cashFlowsApi = {
  list: () =>
    apiClient.get<CashFlowResponse[]>('/api/cash-flows/').then(r => r.data),

  get: (id: number) =>
    apiClient.get<CashFlowResponse>(`/api/cash-flows/${id}`).then(r => r.data),

  create: (data: CashFlowCreate) =>
    apiClient.post<CashFlowResponse>('/api/cash-flows/', data).then(r => r.data),

  update: (id: number, data: CashFlowUpdate) =>
    apiClient.put<CashFlowResponse>(`/api/cash-flows/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/cash-flows/${id}`),
};
