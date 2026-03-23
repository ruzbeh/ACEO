import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { aecoWs } from './ws';
import type {
  PortfolioStatusResponse,
  PortfolioListItem,
  PortfolioRunResponse,
  RunPortfolioRequest,
  ApprovalRequest,
} from './types';

export function usePortfolioRuns() {
  const qc = useQueryClient();

  useEffect(() => {
    return aecoWs.on('portfolio.*', () => {
      qc.invalidateQueries({ queryKey: ['portfolio'] });
    });
  }, [qc]);

  return useQuery({
    queryKey: ['portfolio'],
    queryFn: () => api.get<PortfolioListItem[]>('/portfolio'),
    refetchInterval: (query) => {
      const runs = query.state.data ?? [];
      const hasRunning = runs.some((r) => r.status === 'running');
      return hasRunning ? 5_000 : 15_000;
    },
  });
}

export function usePortfolioStatus(portfolioId: string | undefined) {
  const qc = useQueryClient();

  useEffect(() => {
    if (!portfolioId) return;
    return aecoWs.on('portfolio.*', (event) => {
      if (event.data.portfolio_id === portfolioId) {
        qc.invalidateQueries({ queryKey: ['portfolio', portfolioId] });
      }
    });
  }, [portfolioId, qc]);

  return useQuery({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => api.get<PortfolioStatusResponse>(`/portfolio/${portfolioId}/status`),
    enabled: !!portfolioId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // WebSocket invalidates on portfolio.*; this is fallback when WS unavailable
      return status === 'running' ? 2_000 : 30_000;
    },
  });
}

export function useRunPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RunPortfolioRequest) =>
      api.post<PortfolioRunResponse>('/portfolio/run', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  });
}

export function useStopPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (portfolioId: string) =>
      api.post<{ message: string }>(`/portfolio/${portfolioId}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  });
}

export function useApprovalQueue() {
  const qc = useQueryClient();

  useEffect(() => {
    return aecoWs.on('portfolio.*', () => {
      qc.invalidateQueries({ queryKey: ['approvals'] });
    });
  }, [qc]);

  return useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.get<ApprovalRequest[]>('/portfolio/approvals'),
    refetchInterval: 10_000,
  });
}

export function useApproveAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      api.post(`/portfolio/approvals/${id}/${action}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] });
      qc.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}
