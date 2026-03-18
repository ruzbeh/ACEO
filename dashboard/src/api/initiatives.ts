import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  InitiativeResponse,
  CreateInitiativeRequest,
  RunInitiativeRequest,
  DecisionsResponse,
} from './types';

export function useInitiatives() {
  return useQuery({
    queryKey: ['initiatives'],
    queryFn: () => api.get<InitiativeResponse[]>('/initiatives'),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 5_000),
  });
}

export function useInitiative(id: string) {
  return useQuery({
    queryKey: ['initiatives', id],
    queryFn: () => api.get<InitiativeResponse>(`/initiatives/${id}`),
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false;
      const status = query.state.data?.status;
      return status && status !== 'closed' ? 5_000 : false;
    },
  });
}

export function useDecisions(initiativeId: string) {
  return useQuery({
    queryKey: ['initiatives', initiativeId, 'decisions'],
    queryFn: () => api.get<DecisionsResponse>(`/initiatives/${initiativeId}/decisions`),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 5_000),
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
