import apiClient from './client';
import type { Portfolio } from './types';

export const portfoliosApi = {
  list: () =>
    apiClient.get<Portfolio[]>('/api/portfolios').then(r => r.data),

  create: (name: string) =>
    apiClient.post<Portfolio>('/api/portfolios', { name }).then(r => r.data),

  rename: (id: number, name: string) =>
    apiClient.put<Portfolio>(`/api/portfolios/${id}`, { name }).then(r => r.data),

  remove: (id: number) =>
    apiClient.delete(`/api/portfolios/${id}`),

  setDefault: (id: number) =>
    apiClient.post<Portfolio>(`/api/portfolios/${id}/set-default`).then(r => r.data),

  // Returns the full-fidelity export document (assets, loans, streams, flows, measurements).
  export: (id: number) =>
    apiClient.get<Record<string, unknown>>(`/api/portfolios/${id}/export`).then(r => r.data),

  // Uploads an export document as a new portfolio owned by the current user.
  import: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient
      .post<Portfolio>('/api/portfolios/import', form)
      .then(r => r.data);
  },
};
