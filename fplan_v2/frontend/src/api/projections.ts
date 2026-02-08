import apiClient from './client';
import type { ProjectionRequest, ProjectionResponse, PortfolioSummary } from './types';

export const projectionsApi = {
  run: (data: ProjectionRequest) =>
    apiClient.post<ProjectionResponse>('/api/projections/run', data).then(r => r.data),

  portfolioSummary: () =>
    apiClient.get<PortfolioSummary>('/api/projections/portfolio/summary').then(r => r.data),

  health: () =>
    apiClient.get('/api/projections/health').then(r => r.data),
};
