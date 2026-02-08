import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { loansApi } from '@/api/loans';
import type { LoanCreate, LoanUpdate } from '@/api/types';

export function useLoans() {
  return useQuery({
    queryKey: ['loans'],
    queryFn: () => loansApi.list(),
  });
}

export function useCreateLoan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<LoanCreate, 'external_id'>) =>
      loansApi.create({
        ...data,
        external_id: crypto.randomUUID(),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['loans'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useUpdateLoan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: LoanUpdate }) =>
      loansApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['loans'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}

export function useDeleteLoan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => loansApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['loans'] });
      qc.invalidateQueries({ queryKey: ['portfolio-summary'] });
    },
  });
}
