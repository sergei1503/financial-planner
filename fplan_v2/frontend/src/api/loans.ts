import apiClient from './client';
import type { LoanCreate, LoanUpdate, LoanResponse } from './types';

export const loansApi = {
  list: () =>
    apiClient.get<LoanResponse[]>('/api/loans/').then(r => r.data),

  get: (id: number) =>
    apiClient.get<LoanResponse>(`/api/loans/${id}`).then(r => r.data),

  create: (data: LoanCreate) =>
    apiClient.post<LoanResponse>('/api/loans/', data).then(r => r.data),

  update: (id: number, data: LoanUpdate) =>
    apiClient.put<LoanResponse>(`/api/loans/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/api/loans/${id}`),
};
