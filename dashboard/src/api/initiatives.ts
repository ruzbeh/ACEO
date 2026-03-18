import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { aecoWs } from './ws';
import type {
  InitiativeResponse,
  CreateInitiativeRequest,
  RunInitiativeRequest,
  DecisionsResponse,
  InitiativeSpend,
} from './types';

export function useInitiatives() {
  const qc = useQueryClient();

  // Invalidate on any initiative event via WebSocket
  useEffect(() => {
    return aecoWs.on('initiative.*', () => {
      qc.invalidateQueries({ queryKey: ['initiatives'] });
    });
  }, [qc]);

  return useQuery({
    queryKey: ['initiatives'],
    queryFn: () => api.get<InitiativeResponse[]>('/initiatives'),
    // Fallback polling if WebSocket is disconnected
    refetchInterval: (query) => (query.state.status === 'error' ? false : 30_000),
  });
}

export function useInitiative(id: string) {
  const qc = useQueryClient();

  useEffect(() => {
    return aecoWs.on('initiative.*', (event) => {
      if (event.data.initiative_id === id) {
        qc.invalidateQueries({ queryKey: ['initiatives', id] });
      }
    });
  }, [id, qc]);

  return useQuery({
    queryKey: ['initiatives', id],
    queryFn: () => api.get<InitiativeResponse>(`/initiatives/${id}`),
    // Fallback polling at 30s (WebSocket handles real-time)
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false;
      const status = query.state.data?.status;
      return status && status !== 'closed' ? 30_000 : false;
    },
  });
}

export function useDecisions(initiativeId: string) {
  const qc = useQueryClient();

  useEffect(() => {
    return aecoWs.on('initiative.decision_recorded', (event) => {
      if (event.data.initiative_id === initiativeId) {
        qc.invalidateQueries({ queryKey: ['initiatives', initiativeId, 'decisions'] });
      }
    });
  }, [initiativeId, qc]);

  return useQuery({
    queryKey: ['initiatives', initiativeId, 'decisions'],
    queryFn: () => api.get<DecisionsResponse>(`/initiatives/${initiativeId}/decisions`),
    // Fallback polling at 30s
    refetchInterval: (query) => (query.state.status === 'error' ? false : 30_000),
  });
}

export function useCreateInitiative() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateInitiativeRequest) =>
      api.post<InitiativeResponse>('/initiatives', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['initiatives'] }),
  });
}

export function useRunInitiative() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RunInitiativeRequest) =>
      api.post<{ initiative_id: string; status: string }>('/initiatives/run', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['initiatives'] }),
  });
}

export function useKillInitiative() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (initiativeId: string) =>
      api.post<InitiativeResponse>(`/initiatives/${initiativeId}/kill`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['initiatives'] }),
  });
}

export function useInitiativeSpend(initiativeId: string | undefined, budgetId?: string) {
  const params = budgetId ? `?budget_id=${encodeURIComponent(budgetId)}` : '';
  return useQuery({
    queryKey: ['initiatives', initiativeId, 'spend', budgetId],
    queryFn: () => api.get<InitiativeSpend>(`/initiatives/${initiativeId}/spend${params}`),
    enabled: !!initiativeId,
    refetchInterval: (query) => (query.state.status === 'error' ? false : 10_000),
  });
}
