import { useQuery } from '@tanstack/react-query';
import type { HealthResponse } from './types';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<HealthResponse> => {
      const res = await fetch('/health').catch(() => null);
      if (!res || !res.ok) throw new Error('Backend offline');
      return res.json() as Promise<HealthResponse>;
    },
    refetchInterval: 10_000,
    retry: false,
  });
}
