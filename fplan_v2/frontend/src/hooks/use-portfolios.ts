import { useMutation, useQueryClient } from '@tanstack/react-query';
import { portfoliosApi } from '@/api/portfolios';

/** Mutations for managing portfolios. The list itself lives in PortfolioProvider. */

export function useCreatePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => portfoliosApi.create(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolios'] }),
  });
}

export function useRenamePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      portfoliosApi.rename(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolios'] }),
  });
}

export function useDeletePortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => portfoliosApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolios'] }),
  });
}

export function useSetDefaultPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => portfoliosApi.setDefault(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolios'] }),
  });
}

export function useImportPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => portfoliosApi.import(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolios'] }),
  });
}
