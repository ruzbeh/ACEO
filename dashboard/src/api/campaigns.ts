// Hooks for campaign management API
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export interface AccountHealth {
  spend_7d: number;
  impressions: number;
  clicks: number;
  cpm: number;
  ctr: number;
  conversions: number;
  cost_per_conversion: number;
  frequency: number;
  roas: number;
}

export interface CreativePerformance {
  ad_id: string;
  ad_name: string;
  status: string;
  creative_body: string;
  creative_title: string;
  image_url: string;
  targeting_summary: string;
  ad_set_name: string;
  spend: number;
  impressions: number;
  clicks: number;
  ctr: number;
  cpm: number;
  conversions: number;
  cost_per_conversion: number;
  performance_grade: string;
}

export interface TargetingBreakdown {
  ad_set_id: string;
  ad_set_name: string;
  targeting: {
    countries: string[];
    age_min: number;
    age_max: number;
  };
  optimization_goal: string;
  daily_budget: number;
  spend: number;
  cpm: number;
  conversions: number;
  ads_count: number;
}

export interface GeneratedCreative {
  headline: string;
  primary_text: string;
  description: string;
  cta: string;
  rationale: string;
}

export interface Recommendation {
  id: string;
  text: string;
  action_type: 'instant' | 'initiative' | 'none';
  action_label: string;
  action_payload: Record<string, any>;
}

export interface CampaignReport {
  timestamp?: string;
  is_mock?: boolean;
  account_health: AccountHealth;
  creative_performance: CreativePerformance[];
  targeting_breakdown: TargetingBreakdown[];
  recommendations: Recommendation[];
  generated_creatives: GeneratedCreative[];
}

interface MonitorStatus {
  active: boolean;
  last_check: string | null;
  next_check: string | null;
  reports_count: number;
}

interface OptimizeResult {
  task_id: string;
  status: string;
  result?: any;
}

// GET /api/campaigns/report
export function useCampaignReport(product?: string) {
  const params = product ? `?product=${encodeURIComponent(product)}` : '';
  return useQuery({
    queryKey: ['campaign-report', product ?? '__all__'],
    queryFn: () => api.get<CampaignReport>(`/campaigns/report${params}`),
  });
}

// GET /api/campaigns/products
export function useProducts() {
  return useQuery({
    queryKey: ['campaign-products'],
    queryFn: () => api.get<{ products: string[] }>('/campaigns/products'),
  });
}

// GET /api/campaigns/monitor/status
export function useMonitorStatus() {
  return useQuery({ queryKey: ['campaign-monitor'], queryFn: () => api.get<MonitorStatus>('/campaigns/monitor/status'), refetchInterval: 10000 });
}

// POST /api/campaigns/monitor/start
export function useStartMonitor() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post('/campaigns/monitor/start'), onSuccess: () => qc.invalidateQueries({ queryKey: ['campaign-monitor'] }) });
}

// POST /api/campaigns/monitor/stop
export function useStopMonitor() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post('/campaigns/monitor/stop'), onSuccess: () => qc.invalidateQueries({ queryKey: ['campaign-monitor'] }) });
}

// POST /api/campaigns/optimize
export function useOptimizeCampaigns() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post<OptimizeResult>('/campaigns/optimize'), onSuccess: () => { qc.invalidateQueries({ queryKey: ['campaign-report'] }); } });
}

// POST /api/campaigns/generate-creatives
export function useGenerateCreatives() {
  return useMutation({ mutationFn: (body: { product?: string; audience?: string; style?: string; count?: number }) => api.post<{ creatives: any[] }>('/campaigns/generate-creatives', body) });
}

// POST /api/campaigns/create-ad — push generated copy to live Facebook campaign
export function usePushAdToFacebook() {
  return useMutation({
    mutationFn: (body: { headline: string; primary_text: string; description?: string; cta_type?: string; link?: string; product_name?: string }) =>
      api.post<{ ad_id: string; creative_id: string }>('/campaigns/create-ad', body),
  });
}

// POST /api/campaigns/execute-action — execute an instant campaign action
export function useExecuteAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, any>) => api.post('/campaigns/execute-action', payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['campaign-report'] }),
  });
}

// POST /api/initiatives — create initiative from recommendation
export function useCreateInitiativeFromRec() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; goal: string }) => api.post('/initiatives', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['initiatives'] }),
  });
}

// --- Product Metrics ---

export interface ProductMetrics {
  product: string;
  period: string;
  funnel: {
    impressions: number;
    reach: number;
    clicks: number;
    link_clicks: number;
    landing_page_views: number;
    leads: number;
    add_to_cart: number;
    initiate_checkout: number;
    purchases: number;
    revenue: number;
  };
  rates: {
    click_through_rate: number;
    landing_rate: number;
    lead_rate: number;
    checkout_rate: number;
    purchase_rate: number;
    overall_conversion_rate: number;
  };
  economics: {
    spend: number;
    cpm: number;
    cpc: number;
    cost_per_link_click: number;
    cost_per_landing_view: number;
    cost_per_lead: number;
    cost_per_purchase: number;
    roas: number;
    revenue: number;
    profit: number;
  };
  dropoffs: Array<{
    from: string;
    to: string;
    drop_percent: number;
    lost: number;
    severity: 'critical' | 'warning' | 'ok';
  }>;
}

export interface CampaignBreakdownEntry {
  campaign_id: string;
  campaign_name: string;
  status: string;
  funnel: ProductMetrics['funnel'];
  rates: ProductMetrics['rates'];
  economics: ProductMetrics['economics'];
  dropoffs: ProductMetrics['dropoffs'];
}

export interface CampaignBreakdownMetrics {
  product: string;
  period: string;
  breakdown: 'campaign';
  campaigns: CampaignBreakdownEntry[];
  totals: {
    funnel: ProductMetrics['funnel'];
    rates: ProductMetrics['rates'];
    economics: ProductMetrics['economics'];
    dropoffs: ProductMetrics['dropoffs'];
  };
}

// GET /api/campaigns/metrics?product=...&period=...&breakdown=...
export function useProductMetrics(product?: string, period: string = '7d', breakdown?: string) {
  return useQuery({
    queryKey: ['product-metrics', product, period, breakdown],
    queryFn: () => {
      const params = new URLSearchParams();
      if (product) params.set('product', product);
      params.set('period', period);
      if (breakdown) params.set('breakdown', breakdown);
      return api.get<ProductMetrics | CampaignBreakdownMetrics>(`/campaigns/metrics?${params.toString()}`);
    },
  });
}
