import { useQuery } from '@tanstack/react-query';
import { api } from './client';
import type { AgentResponse } from './types';

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get<AgentResponse[]>('/agents'),
    staleTime: 30_000,
    refetchInterval: (query) => (query.state.status === 'error' ? false : 30_000),
  });
}
