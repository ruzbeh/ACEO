import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  BudgetResponse,
  CreateBudgetRequest,
  BudgetSummary,
  OptimizationReport,
  SpendOverTimeResponse,
  SpendByInitiativeItem,
  RecentSpendItem,
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

export function useSpendOverTime(
  budgetId: string | undefined,
  opts?: { from?: string; to?: string; groupBy?: 'day' | 'week' }
) {
  const params = new URLSearchParams();
  if (opts?.from) params.set('from_date', opts.from);
  if (opts?.to) params.set('to_date', opts.to);
  if (opts?.groupBy) params.set('group_by', opts.groupBy);
  const qs = params.toString();
  return useQuery({
    queryKey: ['budget', budgetId, 'spend-over-time', opts?.from, opts?.to, opts?.groupBy],
    queryFn: () =>
      api.get<SpendOverTimeResponse>(`/budget/periods/${budgetId}/spend-over-time${qs ? `?${qs}` : ''}`),
    enabled: !!budgetId,
  });
}

export function useSpendByInitiative(budgetId: string | undefined) {
  return useQuery({
    queryKey: ['budget', budgetId, 'by-initiative'],
    queryFn: () => api.get<SpendByInitiativeItem[]>(`/budget/periods/${budgetId}/by-initiative`),
    enabled: !!budgetId,
  });
}

export function useRecentSpend(budgetId: string | undefined, limit = 50) {
  return useQuery({
    queryKey: ['budget', budgetId, 'recent-spend', limit],
    queryFn: () =>
      api.get<RecentSpendItem[]>(`/budget/periods/${budgetId}/recent-spend?limit=${limit}`),
    enabled: !!budgetId,
  });
}
