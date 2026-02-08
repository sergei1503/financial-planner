import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cashFlowsApi } from '@/api/cash-flows';
import type { CashFlowResponse } from '@/api/types';

type CashFlowCreate = Omit<CashFlowResponse, 'id' | 'user_id' | 'created_at'>;
type CashFlowUpdate = Partial<CashFlowCreate>;

export function useCashFlows() {
  return useQuery({
    queryKey: ['cash-flows'],
    queryFn: () => cashFlowsApi.list(),
  });
}

export function useCreateCashFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CashFlowCreate) =>
      cashFlowsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cash-flows'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useUpdateCashFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CashFlowUpdate }) =>
      cashFlowsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cash-flows'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useDeleteCashFlow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cashFlowsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cash-flows'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}
