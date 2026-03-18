import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  BudgetResponse,
  CreateBudgetRequest,
  BudgetSummary,
  OptimizationReport,
} from './types';

export function useActiveBudget(scope = 'global', scopeId?: string) {
  const params = new URLSearchParams({ scope });
  if (scopeId) params.set('scope_id', scopeId);
  return useQuery({
    queryKey: ['budget', 'active', scope, scopeId],
    queryFn: () => api.get<BudgetResponse>(`/budget/active?${params}`),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 15_000),
    retry: false,
  });
}

export function useBudgetSummary(budgetId: string | undefined) {
  return useQuery({
    queryKey: ['budget', budgetId, 'summary'],
    queryFn: () => api.get<BudgetSummary>(`/budget/periods/${budgetId}/summary`),
    enabled: !!budgetId,
    refetchInterval: (query) => (query.state.status === 'error' ? false : 15_000),
  });
}

export function useOptimization(budgetId: string | undefined) {
  return useQuery({
    queryKey: ['budget', budgetId, 'optimize'],
    queryFn: () => api.get<OptimizationReport>(`/budget/periods/${budgetId}/optimize`),
    enabled: !!budgetId,
  });
}

export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateBudgetRequest) => api.post<BudgetResponse>('/budget/periods', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['budget'] }),
  });
}
