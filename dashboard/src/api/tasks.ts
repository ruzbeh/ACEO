import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { TaskResponse, CreateTaskRequest } from './types';

export function useTasks() {
  return useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.get<TaskResponse[]>('/tasks'),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 10_000),
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: ['tasks', id],
    queryFn: () => api.get<TaskResponse>(`/tasks/${id}`),
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false;
      const status = query.state.data?.status;
      return status && status !== 'done' && status !== 'blocked' ? 3_000 : false;
    },
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateTaskRequest) => api.post<TaskResponse>('/tasks', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  });
}
