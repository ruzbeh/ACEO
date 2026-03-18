import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { WorkflowResponse, RunWorkflowRequest } from './types';

export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: () => api.get<WorkflowResponse[]>('/workflows'),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 10_000),
  });
}

export function useWorkflow(id: string | null) {
  return useQuery({
    queryKey: ['workflows', id],
    queryFn: () => api.get<WorkflowResponse>(`/workflows/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false;
      return query.state.data?.status === 'running' ? 3_000 : false;
    },
  });
}

export function useRunWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RunWorkflowRequest) => api.post<WorkflowResponse>('/workflows/run', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workflows'] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}
