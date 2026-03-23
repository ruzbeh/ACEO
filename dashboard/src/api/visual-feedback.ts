import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError, NetworkError } from './client';

const API_BASE = '/api';

export interface VisualFeedbackItem {
  id: string;
  initiative_id: string | null;
  feedback: string;
  screenshot_url: string | null;
  status: 'pending' | 'running' | 'done' | 'error';
  result: string | null;
  created_at: string;
}

interface SubmitVisualFeedbackParams {
  file: File;
  feedback: string;
  workspace_path?: string;
  initiative_id?: string;
}

async function postFormData<T>(path: string, formData: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type — browser sets it with multipart boundary
    });
  } catch {
    throw new NetworkError(`Backend unreachable: ${API_BASE}${path}`);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch {
    throw new NetworkError(`Backend unreachable: ${API_BASE}${path}`);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}

export function useSubmitVisualFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, feedback, workspace_path, initiative_id }: SubmitVisualFeedbackParams) => {
      const formData = new FormData();
      formData.append('screenshot', file);
      formData.append('feedback', feedback);
      if (workspace_path) formData.append('workspace_path', workspace_path);
      if (initiative_id) formData.append('initiative_id', initiative_id);
      return postFormData<VisualFeedbackItem>('/visual-feedback', formData);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['visual-feedback'] });
    },
  });
}

export function useVisualFeedbackStatus(taskId: string) {
  return useQuery({
    queryKey: ['visual-feedback', taskId],
    queryFn: () => get<VisualFeedbackItem>(`/visual-feedback/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 3_000 : false;
    },
  });
}

export function useVisualFeedbackList(initiativeId?: string) {
  const params = initiativeId ? `?initiative_id=${encodeURIComponent(initiativeId)}` : '';
  return useQuery({
    queryKey: ['visual-feedback', 'list', initiativeId],
    queryFn: () => get<VisualFeedbackItem[]>(`/visual-feedback${params}`),
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      const hasRunning = items.some((i) => i.status === 'running' || i.status === 'pending');
      return hasRunning ? 5_000 : false;
    },
  });
}
