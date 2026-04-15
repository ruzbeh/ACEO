import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type ReelStatus =
  | 'draft'
  | 'rendering'
  | 'rendered'
  | 'publishing'
  | 'published'
  | 'failed';

export interface Reel {
  id: string;
  title: string;
  status: ReelStatus;
  headline: string;
  subheadline: string;
  cta_text: string;
  brand: string;
  before_image_url: string | null;
  after_image_urls: string[];
  mp4_url: string | null;
  duration_sec: number | null;
  fb_ad_id: string | null;
  fb_ads_manager_url: string | null;
  fb_adset_id: string | null;
  progress_log: Array<{ ts: string; stage: string; message: string }>;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImageUploadResponse {
  id: string;
  path: string;
  url: string;
}

export interface CreateReelRequest {
  title?: string;
  before_image_path: string;
  after_image_paths: string[];
  headline?: string;
  subheadline?: string;
  cta_text?: string;
  brand?: string;
  brief?: string;
  composition?: string;
  auto_script?: boolean;
}

export interface PublishRequest {
  adset_id?: string;
  page_id?: string;
  link?: string;
}

/* ─── Queries ─── */

export function useReels() {
  return useQuery({
    queryKey: ['reels'],
    queryFn: () => api.get<Reel[]>('/reels'),
    // While any reel is mid-pipeline, keep polling.
    refetchInterval: (q) => {
      const data = q.state.data as Reel[] | undefined;
      if (!data) return false;
      return data.some((r) => r.status === 'rendering' || r.status === 'publishing')
        ? 2000
        : false;
    },
  });
}

export function useReel(id: string | undefined) {
  return useQuery({
    queryKey: ['reel', id],
    queryFn: () => api.get<Reel>(`/reels/${id}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const data = q.state.data as Reel | undefined;
      if (!data) return false;
      return data.status === 'rendering' || data.status === 'publishing' ? 1500 : false;
    },
  });
}

/* ─── Mutations ─── */

export function useUploadImage() {
  return useMutation({
    mutationFn: async (file: File): Promise<ImageUploadResponse> => {
      const form = new FormData();
      form.append('file', file);
      return api.postForm<ImageUploadResponse>('/reels/images', form);
    },
  });
}

export function useCreateReel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CreateReelRequest) => api.post<Reel>('/reels', req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reels'] }),
  });
}

export function usePublishReel(reelId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: PublishRequest) => api.post<Reel>(`/reels/${reelId}/publish`, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reels'] });
      qc.invalidateQueries({ queryKey: ['reel', reelId] });
    },
  });
}

export function statusLabel(status: ReelStatus): string {
  return {
    draft: 'Draft',
    rendering: 'Rendering…',
    rendered: 'Ready to publish',
    publishing: 'Publishing…',
    published: 'Live on Facebook',
    failed: 'Failed',
  }[status];
}

export function statusColor(status: ReelStatus): string {
  return {
    draft: 'bg-gray-500/10 text-gray-300',
    rendering: 'bg-blue-500/10 text-blue-400',
    rendered: 'bg-amber-500/10 text-amber-400',
    publishing: 'bg-blue-500/10 text-blue-400',
    published: 'bg-green-500/10 text-green-400',
    failed: 'bg-red-500/10 text-red-400',
  }[status];
}
