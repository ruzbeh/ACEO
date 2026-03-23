import { useState } from 'react';
import {
  Megaphone, Play, Square, Zap, Sparkles, Clock, DollarSign,
  MousePointerClick, Eye, ShoppingCart, Target, AlertTriangle,
  Lightbulb, BarChart3, Users, Repeat, Send, CheckCircle,
  Pause, TrendingUp, Loader2, ArrowDownRight, ChevronDown,
  ChevronUp, Star,
} from 'lucide-react';
import {
  useCampaignReport,
  useProducts,
  useMonitorStatus,
  useStartMonitor,
  useStopMonitor,
  useOptimizeCampaigns,
  useGenerateCreatives,
  usePushAdToFacebook,
  useExecuteAction,
  useCreateInitiativeFromRec,
  useProductMetrics,
  type CreativePerformance,
  type TargetingBreakdown,
  type Recommendation,
  type ProductMetrics,
  type CampaignBreakdownMetrics,
} from '../api/campaigns';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { formatCurrency, formatDateTime } from '../lib/utils';

const STYLES = [
  { value: 'direct_response', label: 'Direct Response' },
  { value: 'social_proof', label: 'Social Proof' },
  { value: 'urgency', label: 'Urgency' },
  { value: 'benefit_led', label: 'Benefit-Led' },
  { value: 'problem_agitation', label: 'Problem Agitation' },
];

const gradeColors: Record<string, string> = {
  A: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  B: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  C: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  F: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const statusColors: Record<string, string> = {
  ACTIVE: 'bg-emerald-500/20 text-emerald-400',
  PENDING_REVIEW: 'bg-yellow-500/20 text-yellow-400',
  PAUSED: 'bg-gray-500/20 text-gray-400',
  DISAPPROVED: 'bg-red-500/20 text-red-400',
  ARCHIVED: 'bg-gray-500/20 text-gray-500',
};

function metricColor(metric: string, value: number): string {
  if (metric === 'ctr') return value >= 2 ? 'text-emerald-400' : value >= 1 ? 'text-yellow-400' : 'text-red-400';
  if (metric === 'cpm') return value <= 10 ? 'text-emerald-400' : value <= 20 ? 'text-yellow-400' : 'text-red-400';
  if (metric === 'conversions') return value >= 10 ? 'text-emerald-400' : value >= 3 ? 'text-yellow-400' : 'text-red-400';
  if (metric === 'frequency') return value <= 2 ? 'text-emerald-400' : value <= 3 ? 'text-yellow-400' : 'text-red-400';
  if (metric === 'cost_per_conversion') return value > 0 && value <= 15 ? 'text-emerald-400' : value <= 30 ? 'text-yellow-400' : 'text-red-400';
  return 'text-gray-200';
}

function BudgetBar({ spend, budget7d }: { spend: number; budget7d: number }) {
  const pct = budget7d > 0 ? Math.min((spend / budget7d) * 100, 100) : 0;
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>Budget utilization</span>
        <span>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-gray-700">
        <div className={`h-1.5 rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function FunnelView({
  funnel, rates, economics, dropoffs, compact,
}: {
  funnel: ProductMetrics['funnel'];
  rates: ProductMetrics['rates'];
  economics: ProductMetrics['economics'];
  dropoffs: ProductMetrics['dropoffs'];
  compact?: boolean;
}) {
  const steps = [
    { label: 'Impressions', value: funnel.impressions },
    { label: 'Link Clicks', value: funnel.link_clicks },
    { label: 'Landing Views', value: funnel.landing_page_views },
    { label: 'Checkout', value: funnel.initiate_checkout },
    { label: 'Purchase', value: funnel.purchases },
  ];
  const maxVal = steps[0].value || 1;
  const barHeight = compact ? 'h-7' : 'h-10';

  return (
    <div className="space-y-4">
      {/* Funnel bars */}
      <Card>
        <div className="flex items-end gap-2">
          {steps.map((step, i) => {
            const widthPct = Math.max((step.value / maxVal) * 100, 4);
            const dropoffMatch = dropoffs[i - 1];
            const severity = dropoffMatch?.severity;
            const barColor = severity === 'critical'
              ? 'bg-red-500/70'
              : severity === 'warning'
              ? 'bg-yellow-500/70'
              : 'bg-emerald-500/70';
            return (
              <div key={step.label} className="flex-1 text-center">
                <p className="text-xs text-gray-500 mb-1">{step.label}</p>
                <div className="mx-auto" style={{ width: `${widthPct}%`, minWidth: '24px' }}>
                  <div className={`${barHeight} rounded ${i === 0 ? 'bg-accent/60' : barColor} transition-all`} />
                </div>
                <p className="text-sm font-semibold text-gray-200 mt-1 tabular-nums">{step.value.toLocaleString()}</p>
                {dropoffMatch && (
                  <p className={`text-xs mt-0.5 ${
                    dropoffMatch.severity === 'critical' ? 'text-red-400' :
                    dropoffMatch.severity === 'warning' ? 'text-yellow-400' : 'text-gray-500'
                  }`}>
                    <ArrowDownRight size={10} className="inline mr-0.5" />
                    {dropoffMatch.drop_percent}% drop
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Unit Economics */}
      <div className={`grid gap-4 ${compact ? 'sm:grid-cols-2 lg:grid-cols-4' : 'sm:grid-cols-2 lg:grid-cols-4'}`}>
        <Card>
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <MousePointerClick size={16} />
            <span className="text-xs font-medium uppercase tracking-wide">Cost per Click</span>
          </div>
          <p className={`${compact ? 'text-xl' : 'text-2xl'} font-bold text-gray-200`}>{formatCurrency(economics.cost_per_link_click)}</p>
          <p className="text-xs text-gray-500 mt-1">CPC: {formatCurrency(economics.cpc)}</p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <Eye size={16} />
            <span className="text-xs font-medium uppercase tracking-wide">Cost per Landing View</span>
          </div>
          <p className={`${compact ? 'text-xl' : 'text-2xl'} font-bold text-gray-200`}>{formatCurrency(economics.cost_per_landing_view)}</p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <ShoppingCart size={16} />
            <span className="text-xs font-medium uppercase tracking-wide">Cost per Purchase</span>
          </div>
          <p className={`${compact ? 'text-xl' : 'text-2xl'} font-bold text-gray-200`}>
            {economics.cost_per_purchase > 0 ? formatCurrency(economics.cost_per_purchase) : 'No purchases'}
          </p>
        </Card>
        <Card>
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <TrendingUp size={16} />
            <span className="text-xs font-medium uppercase tracking-wide">ROAS</span>
          </div>
          <p className={`${compact ? 'text-xl' : 'text-2xl'} font-bold ${economics.roas > 1 ? 'text-emerald-400' : economics.roas > 0 ? 'text-yellow-400' : 'text-gray-500'}`}>
            {economics.roas > 0 ? `${economics.roas}x` : 'N/A'}
          </p>
          <p className={`text-xs mt-1 ${economics.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {economics.profit >= 0 ? '+' : ''}{formatCurrency(economics.profit)} profit
          </p>
        </Card>
      </div>

      {/* Drop-off Analysis */}
      {dropoffs.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-gray-300 flex items-center gap-2">
            <AlertTriangle size={16} className="text-yellow-400" />
            Drop-off Analysis
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {dropoffs.map((d) => (
              <div
                key={`${d.from}-${d.to}`}
                className={`rounded-lg border p-3 ${
                  d.severity === 'critical'
                    ? 'border-red-500/30 bg-red-500/10'
                    : d.severity === 'warning'
                    ? 'border-yellow-500/30 bg-yellow-500/10'
                    : 'border-border bg-surface-overlay'
                }`}
              >
                <p className={`text-sm font-medium ${
                  d.severity === 'critical' ? 'text-red-400' :
                  d.severity === 'warning' ? 'text-yellow-400' : 'text-gray-300'
                }`}>
                  {d.from} &rarr; {d.to}
                </p>
                <p className={`${compact ? 'text-xl' : 'text-2xl'} font-bold mt-1 ${
                  d.severity === 'critical' ? 'text-red-300' :
                  d.severity === 'warning' ? 'text-yellow-300' : 'text-gray-200'
                }`}>
                  {d.drop_percent}%
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {d.lost.toLocaleString()} lost
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function CampaignsPage() {
  const [selectedProduct, setSelectedProduct] = useState<string>('Headshot AI');
  const productFilter = selectedProduct === '__all__' ? undefined : selectedProduct;
  const { data: report, isLoading: reportLoading } = useCampaignReport(productFilter);
  const { data: productsData } = useProducts();
  const { data: monitor } = useMonitorStatus();
  const startMonitor = useStartMonitor();
  const stopMonitor = useStopMonitor();
  const optimize = useOptimizeCampaigns();
  const generateCreatives = useGenerateCreatives();
  const pushAd = usePushAdToFacebook();
  const executeAction = useExecuteAction();
  const createInitiative = useCreateInitiativeFromRec();

  const [metricsPeriod, setMetricsPeriod] = useState<string>('7d');
  const [metricsBreakdown, setMetricsBreakdown] = useState<'total' | 'campaign'>('total');
  const { data: metricsRaw, isLoading: metricsLoading } = useProductMetrics(
    productFilter,
    metricsPeriod,
    metricsBreakdown === 'campaign' ? 'campaign' : undefined,
  );
  const metrics = metricsBreakdown === 'total' ? (metricsRaw as ProductMetrics | undefined) : undefined;
  const breakdownData = metricsBreakdown === 'campaign' ? (metricsRaw as CampaignBreakdownMetrics | undefined) : undefined;
  const [expandedCampaigns, setExpandedCampaigns] = useState<Record<string, boolean>>({});

  const [style, setStyle] = useState('direct_response');
  const [generatedCards, setGeneratedCards] = useState<any[]>([]);
  const [pushedCards, setPushedCards] = useState<Record<number, 'loading' | 'success' | string>>({});
  const [recStates, setRecStates] = useState<Record<string, 'loading' | 'success' | string>>({});

  const health = report?.account_health;

  function handlePush(index: number, creative: any) {
    setPushedCards((prev) => ({ ...prev, [index]: 'loading' }));
    pushAd.mutate(
      { headline: creative.headline, primary_text: creative.primary_text, description: creative.description ?? '', product_name: productFilter ?? 'Headshot AI' },
      {
        onSuccess: () => setPushedCards((prev) => ({ ...prev, [index]: 'success' })),
        onError: (err: any) => setPushedCards((prev) => ({ ...prev, [index]: err?.message ?? 'Push failed' })),
      },
    );
  }

  function handleGenerate() {
    generateCreatives.mutate(
      { product: 'Headshot AI', style, count: 3 },
      { onSuccess: (data) => { setGeneratedCards(data.creatives ?? []); setPushedCards({}); } },
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold">Campaign Manager</h1>
            <p className="mt-1 text-sm text-gray-400">
              AI-powered Facebook ad optimization
              {productFilter ? ` for ${productFilter}` : ''}
            </p>
          </div>
          <select
            value={selectedProduct}
            onChange={(e) => setSelectedProduct(e.target.value)}
            className="rounded-lg border border-border bg-surface-overlay px-3 py-1.5 text-sm text-gray-200 focus:border-accent focus:outline-none"
          >
            <option value="__all__">All Products</option>
            {(productsData?.products ?? []).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-3">
          {/* Monitor toggle */}
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${monitor?.active ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
            <span className="text-xs text-gray-400">{monitor?.active ? 'Monitoring' : 'Stopped'}</span>
            {monitor?.active ? (
              <Button variant="secondary" size="sm" onClick={() => stopMonitor.mutate()} disabled={stopMonitor.isPending}>
                <Square size={14} className="mr-1.5" />
                Stop
              </Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => startMonitor.mutate()} disabled={startMonitor.isPending}>
                <Play size={14} className="mr-1.5" />
                Start
              </Button>
            )}
          </div>

          {/* Optimize */}
          <Button onClick={() => optimize.mutate()} disabled={optimize.isPending}>
            {optimize.isPending ? <Spinner className="mr-1.5 h-4 w-4" /> : <Zap size={16} className="mr-1.5" />}
            Run Optimization
          </Button>
        </div>
      </div>

      {/* Mock data indicator */}
      {report?.is_mock && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-2 text-sm text-yellow-400">
          <AlertTriangle size={16} />
          <span>Showing sample data — connect your Facebook account for live metrics.</span>
        </div>
      )}

      {reportLoading && (
        <div className="flex justify-center py-16">
          <Spinner className="h-8 w-8" />
        </div>
      )}

      {!reportLoading && !report && (
        <Card className="text-center py-12">
          <Megaphone className="mx-auto h-10 w-10 text-gray-600 mb-3" />
          <p className="text-gray-400">No campaign data yet. Run an optimization or start the monitor to begin.</p>
        </Card>
      )}

      {/* Product Funnel Metrics */}
      {(metrics || breakdownData) && (
        <div className="mb-6 space-y-4">
          {/* Period + breakdown selector */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
              <BarChart3 size={18} className="text-accent" />
              Funnel Metrics
              <span className="text-sm font-normal text-gray-500">— {metrics?.product || breakdownData?.product}</span>
            </h2>
            <div className="flex items-center gap-3">
              {/* Breakdown toggle */}
              <div className="flex rounded-lg border border-border overflow-hidden">
                {([['total', 'Total'], ['campaign', 'By Campaign']] as const).map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => {
                      setMetricsBreakdown(val);
                      setExpandedCampaigns({});
                    }}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      metricsBreakdown === val
                        ? 'bg-purple-500/20 text-purple-400'
                        : 'bg-surface-overlay text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {/* Period selector */}
              <div className="flex rounded-lg border border-border overflow-hidden">
                {([['7d', '7 Days'], ['30d', '30 Days'], ['lifetime', 'Lifetime']] as const).map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => setMetricsPeriod(val)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      metricsPeriod === val
                        ? 'bg-accent/20 text-accent'
                        : 'bg-surface-overlay text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Account-level (Total) view */}
          {metrics && <FunnelView funnel={metrics.funnel} rates={metrics.rates} economics={metrics.economics} dropoffs={metrics.dropoffs} />}

          {/* Campaign breakdown view */}
          {breakdownData && (
            <div className="space-y-3">
              {breakdownData.campaigns.map((camp, campIdx) => {
                const isExpanded = expandedCampaigns[camp.campaign_id] ?? (campIdx === 0 && camp.status === 'ACTIVE');
                // Find best performer per drop-off step (lowest drop at each step)
                const isBest = breakdownData.campaigns.length > 1 && camp.dropoffs.length > 0 &&
                  camp.dropoffs.every((d, di) => {
                    const others = breakdownData.campaigns
                      .filter((c) => c.campaign_id !== camp.campaign_id && c.dropoffs[di])
                      .map((c) => c.dropoffs[di].drop_percent);
                    return others.length === 0 || d.drop_percent <= Math.min(...others);
                  });
                return (
                  <div key={camp.campaign_id} className="rounded-lg border border-border bg-surface-overlay overflow-hidden">
                    <button
                      onClick={() => setExpandedCampaigns((prev) => ({ ...prev, [camp.campaign_id]: !isExpanded }))}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {isBest && <Star size={14} className="text-yellow-400 fill-yellow-400 flex-shrink-0" />}
                        <span className="text-sm font-medium text-gray-200">{camp.campaign_name}</span>
                        <Badge className={statusColors[camp.status] ?? 'bg-gray-500/20 text-gray-400'}>
                          {camp.status.replace(/_/g, ' ')}
                        </Badge>
                        <span className="text-xs text-gray-500 tabular-nums">
                          {formatCurrency(camp.economics.spend)} spend
                        </span>
                      </div>
                      {isExpanded ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />}
                    </button>
                    {isExpanded && (
                      <div className="px-4 pb-4 space-y-4 border-t border-border/50">
                        <FunnelView funnel={camp.funnel} rates={camp.rates} economics={camp.economics} dropoffs={camp.dropoffs} compact />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Totals row */}
              <div className="rounded-lg border border-accent/30 bg-accent/5 overflow-hidden">
                <div className="px-4 py-3">
                  <h3 className="text-sm font-medium text-accent">Totals (Account-Level)</h3>
                </div>
                <div className="px-4 pb-4 space-y-4 border-t border-accent/20">
                  <FunnelView
                    funnel={breakdownData.totals.funnel}
                    rates={breakdownData.totals.rates}
                    economics={breakdownData.totals.economics}
                    dropoffs={breakdownData.totals.dropoffs}
                    compact
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {metricsLoading && !metrics && !breakdownData && (
        <div className="mb-6 flex justify-center py-8">
          <Spinner className="h-6 w-6" />
        </div>
      )}

      {health && (
        <div className="space-y-6">
          {/* Account Health Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <DollarSign size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">Spend (7d)</span>
              </div>
              <p className="text-2xl font-bold text-gray-200">{formatCurrency(health.spend_7d)}</p>
            </Card>
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <Eye size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">CPM</span>
              </div>
              <p className={`text-2xl font-bold ${metricColor('cpm', health.cpm)}`}>{formatCurrency(health.cpm)}</p>
            </Card>
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <MousePointerClick size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">CTR</span>
              </div>
              <p className={`text-2xl font-bold ${metricColor('ctr', health.ctr)}`}>{health.ctr.toFixed(2)}%</p>
            </Card>
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <ShoppingCart size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">Conversions</span>
              </div>
              <p className={`text-2xl font-bold ${metricColor('conversions', health.conversions)}`}>{health.conversions}</p>
            </Card>
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <Target size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">Cost / Conv</span>
              </div>
              <p className={`text-2xl font-bold ${metricColor('cost_per_conversion', health.cost_per_conversion)}`}>
                {health.cost_per_conversion > 0 ? formatCurrency(health.cost_per_conversion) : '\u2014'}
              </p>
            </Card>
            <Card>
              <div className="flex items-center gap-2 text-gray-400 mb-2">
                <Repeat size={16} />
                <span className="text-xs font-medium uppercase tracking-wide">Frequency</span>
              </div>
              <p className={`text-2xl font-bold ${metricColor('frequency', health.frequency)}`}>
                {health.frequency.toFixed(1)}
              </p>
              {health.frequency > 3 && (
                <p className="mt-1 text-xs text-red-400 flex items-center gap-1">
                  <AlertTriangle size={12} /> Ad fatigue risk
                </p>
              )}
            </Card>
          </div>

          {/* Creative + Targeting Combo Table */}
          {report.creative_performance && report.creative_performance.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300 flex items-center gap-2">
                <BarChart3 size={16} className="text-accent" />
                Creative + Targeting Performance
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-gray-500">
                      <th className="pb-2 pr-4">Creative</th>
                      <th className="pb-2 pr-4">Targeting</th>
                      <th className="pb-2 pr-4 text-right">Spend</th>
                      <th className="pb-2 pr-4 text-right">Impr.</th>
                      <th className="pb-2 pr-4 text-right">Clicks</th>
                      <th className="pb-2 pr-4 text-right">CTR</th>
                      <th className="pb-2 pr-4 text-right">CPM</th>
                      <th className="pb-2 pr-4 text-right">Conv.</th>
                      <th className="pb-2 pr-4 text-right">Cost/Conv</th>
                      <th className="pb-2 pr-4 text-center">Grade</th>
                      <th className="pb-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.creative_performance.map((ad: CreativePerformance) => (
                      <tr key={ad.ad_id} className="border-b border-border/50 hover:bg-white/[0.02] transition-colors">
                        {/* Creative column */}
                        <td className="py-3 pr-4 max-w-[260px]">
                          <div className="flex items-start gap-3">
                            {ad.image_url && (
                              <img
                                src={ad.image_url}
                                alt=""
                                className="h-10 w-10 rounded object-cover flex-shrink-0 bg-gray-800"
                              />
                            )}
                            <div className="min-w-0">
                              <p className="font-medium text-gray-200 truncate">{ad.creative_title || ad.ad_name}</p>
                              <p className="text-xs text-gray-500 truncate mt-0.5">
                                {ad.creative_body ? ad.creative_body.slice(0, 80) + (ad.creative_body.length > 80 ? '...' : '') : '\u2014'}
                              </p>
                            </div>
                          </div>
                        </td>
                        {/* Targeting column */}
                        <td className="py-3 pr-4 max-w-[180px]">
                          <p className="text-xs text-gray-400">{ad.targeting_summary || '\u2014'}</p>
                          <p className="text-xs text-gray-600 mt-0.5">{ad.ad_set_name}</p>
                        </td>
                        {/* Metrics */}
                        <td className="py-3 pr-4 text-right text-gray-200 tabular-nums">{formatCurrency(ad.spend)}</td>
                        <td className="py-3 pr-4 text-right text-gray-300 tabular-nums">{ad.impressions.toLocaleString()}</td>
                        <td className="py-3 pr-4 text-right text-gray-300 tabular-nums">{ad.clicks.toLocaleString()}</td>
                        <td className={`py-3 pr-4 text-right tabular-nums ${metricColor('ctr', ad.ctr)}`}>{ad.ctr.toFixed(2)}%</td>
                        <td className={`py-3 pr-4 text-right tabular-nums ${metricColor('cpm', ad.cpm)}`}>{formatCurrency(ad.cpm)}</td>
                        <td className={`py-3 pr-4 text-right tabular-nums ${metricColor('conversions', ad.conversions)}`}>{ad.conversions}</td>
                        <td className="py-3 pr-4 text-right text-gray-300 tabular-nums">
                          {ad.cost_per_conversion > 0 ? formatCurrency(ad.cost_per_conversion) : '\u2014'}
                        </td>
                        {/* Grade */}
                        <td className="py-3 pr-4 text-center">
                          <Badge className={`${gradeColors[ad.performance_grade] ?? 'bg-gray-500/20 text-gray-400'} border`}>
                            {ad.performance_grade}
                          </Badge>
                        </td>
                        {/* Status */}
                        <td className="py-3 text-center">
                          <Badge className={statusColors[ad.status] ?? 'bg-gray-500/20 text-gray-400'}>
                            {ad.status.replace(/_/g, ' ')}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Targeting Breakdown */}
          {report.targeting_breakdown && report.targeting_breakdown.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-medium text-gray-300 flex items-center gap-2">
                <Users size={16} className="text-accent" />
                Targeting Breakdown
              </h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {report.targeting_breakdown.map((ts: TargetingBreakdown) => {
                  const budget7d = ts.daily_budget * 7;
                  return (
                    <Card key={ts.ad_set_id}>
                      <div className="flex items-center justify-between mb-3">
                        <p className="font-medium text-gray-200 text-sm truncate">{ts.ad_set_name}</p>
                        <Badge className="bg-gray-500/20 text-gray-400">
                          {ts.ads_count} ad{ts.ads_count !== 1 ? 's' : ''}
                        </Badge>
                      </div>
                      <div className="space-y-1.5 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Countries</span>
                          <span className="text-gray-300">{ts.targeting.countries.join(', ') || 'Broad'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Age</span>
                          <span className="text-gray-300">{ts.targeting.age_min}\u2013{ts.targeting.age_max}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Optimization</span>
                          <span className="text-gray-300">{ts.optimization_goal.replace(/_/g, ' ')}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Daily Budget</span>
                          <span className="text-gray-300">{formatCurrency(ts.daily_budget)}</span>
                        </div>
                        <div className="border-t border-border/50 pt-1.5 mt-1.5" />
                        <div className="flex justify-between">
                          <span className="text-gray-500">Spend (7d)</span>
                          <span className="text-gray-200 font-medium">{formatCurrency(ts.spend)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">CPM</span>
                          <span className={metricColor('cpm', ts.cpm)}>{formatCurrency(ts.cpm)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Conversions</span>
                          <span className={metricColor('conversions', ts.conversions)}>{ts.conversions}</span>
                        </div>
                      </div>
                      <BudgetBar spend={ts.spend} budget7d={budget7d} />
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {report.recommendations && report.recommendations.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300 flex items-center gap-2">
                <Lightbulb size={16} className="text-yellow-400" />
                Recommendations
              </h3>
              <div className="space-y-3">
                {report.recommendations.map((rec: Recommendation) => {
                  const state = recStates[rec.id];
                  const isLoading = state === 'loading';
                  const isSuccess = state === 'success';
                  const isError = typeof state === 'string' && state !== 'loading' && state !== 'success';

                  function handleAction() {
                    setRecStates((p) => ({ ...p, [rec.id]: 'loading' }));
                    if (rec.action_type === 'instant') {
                      executeAction.mutate(rec.action_payload, {
                        onSuccess: () => setRecStates((p) => ({ ...p, [rec.id]: 'success' })),
                        onError: (err: any) => setRecStates((p) => ({ ...p, [rec.id]: err?.message ?? 'Action failed' })),
                      });
                    } else if (rec.action_type === 'initiative') {
                      createInitiative.mutate(
                        { title: rec.action_payload.title, goal: rec.action_payload.goal },
                        {
                          onSuccess: () => setRecStates((p) => ({ ...p, [rec.id]: 'success' })),
                          onError: (err: any) => setRecStates((p) => ({ ...p, [rec.id]: err?.message ?? 'Failed to create initiative' })),
                        },
                      );
                    }
                  }

                  const actionIcon = rec.action_payload?.action === 'pause_ad'
                    ? <Pause size={14} className="mr-1.5" />
                    : rec.action_payload?.action === 'scale_budget' || rec.action_payload?.action === 'update_budget'
                    ? <TrendingUp size={14} className="mr-1.5" />
                    : rec.action_type === 'initiative'
                    ? <Sparkles size={14} className="mr-1.5" />
                    : null;

                  const buttonColor = rec.action_payload?.action === 'pause_ad'
                    ? 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30 border-orange-500/30'
                    : rec.action_payload?.action === 'scale_budget' || rec.action_payload?.action === 'update_budget'
                    ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border-emerald-500/30'
                    : rec.action_type === 'initiative'
                    ? 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border-purple-500/30'
                    : '';

                  return (
                    <div
                      key={rec.id}
                      className="flex items-center justify-between gap-4 rounded-lg border border-border/50 bg-surface-overlay px-4 py-3"
                    >
                      <div className="flex items-start gap-2.5 min-w-0">
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-accent flex-shrink-0" />
                        <span className="text-sm text-gray-300">{rec.text}</span>
                      </div>

                      {rec.action_type !== 'none' && (
                        <div className="flex-shrink-0">
                          {isSuccess ? (
                            <span className="flex items-center gap-1 text-xs text-emerald-400 whitespace-nowrap">
                              <CheckCircle size={14} />
                              {rec.action_type === 'initiative' ? 'Initiative created!' : 'Done!'}
                            </span>
                          ) : isLoading ? (
                            <button
                              disabled
                              className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-xs font-medium opacity-60 ${buttonColor}`}
                            >
                              <Loader2 size={14} className="mr-1.5 animate-spin" />
                              {rec.action_type === 'initiative' ? 'Creating...' : 'Executing...'}
                            </button>
                          ) : (
                            <button
                              onClick={handleAction}
                              className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${buttonColor}`}
                            >
                              {actionIcon}
                              {rec.action_label}
                            </button>
                          )}
                          {isError && (
                            <p className="mt-1 text-xs text-red-400">{state}</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Generate Ad Copy Section */}
      <div className="mt-6">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-300">Generate New Ad Copy</h3>
            <div className="flex items-center gap-3">
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="rounded-lg border border-border bg-surface-overlay px-3 py-1.5 text-sm text-gray-200 focus:border-accent focus:outline-none"
              >
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
              <Button size="sm" onClick={handleGenerate} disabled={generateCreatives.isPending}>
                {generateCreatives.isPending ? <Spinner className="mr-1.5 h-4 w-4" /> : <Sparkles size={14} className="mr-1.5" />}
                Generate
              </Button>
            </div>
          </div>

          {generatedCards.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {generatedCards.map((creative, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface-overlay p-4 space-y-2">
                  <p className="text-sm font-semibold text-gray-200">{creative.headline}</p>
                  <p className="text-sm text-gray-400">{creative.primary_text}</p>
                  {creative.description && (
                    <p className="text-xs text-gray-500">{creative.description}</p>
                  )}
                  <div className="flex items-center justify-between pt-2 border-t border-border">
                    <Badge className="bg-accent/20 text-accent">{creative.cta}</Badge>
                    {pushedCards[i] === 'success' ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle size={14} /> Live on Facebook!
                      </span>
                    ) : pushedCards[i] === 'loading' ? (
                      <Button variant="secondary" size="sm" disabled>
                        <Spinner className="mr-1.5 h-3.5 w-3.5" />
                        Pushing...
                      </Button>
                    ) : (
                      <Button variant="secondary" size="sm" onClick={() => handlePush(i, creative)}>
                        <Send size={14} className="mr-1.5" />
                        Push to Facebook
                      </Button>
                    )}
                  </div>
                  {typeof pushedCards[i] === 'string' && pushedCards[i] !== 'loading' && pushedCards[i] !== 'success' && (
                    <p className="text-xs text-red-400">{pushedCards[i]}</p>
                  )}
                  {creative.rationale && (
                    <p className="text-xs text-gray-500 italic">{creative.rationale}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Show report generated creatives if present */}
          {report?.generated_creatives && report.generated_creatives.length > 0 && generatedCards.length === 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {report.generated_creatives.map((creative, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface-overlay p-4 space-y-2">
                  <p className="text-sm font-semibold text-gray-200">{creative.headline}</p>
                  <p className="text-sm text-gray-400">{creative.primary_text}</p>
                  {creative.description && (
                    <p className="text-xs text-gray-500">{creative.description}</p>
                  )}
                  <div className="flex items-center justify-between pt-2 border-t border-border">
                    <Badge className="bg-accent/20 text-accent">{creative.cta}</Badge>
                  </div>
                  {creative.rationale && (
                    <p className="text-xs text-gray-500 italic">{creative.rationale}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Monitor Log */}
      {monitor && (
        <div className="mt-6">
          <Card>
            <h3 className="mb-4 text-sm font-medium text-gray-300">Monitor Log</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <Clock size={14} className="text-gray-500" />
                <span className="text-gray-400">Last check:</span>
                <span className="text-gray-200">{monitor.last_check ? formatDateTime(monitor.last_check) : 'Never'}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <Clock size={14} className="text-gray-500" />
                <span className="text-gray-400">Next check:</span>
                <span className="text-gray-200">{monitor.next_check ? formatDateTime(monitor.next_check) : 'N/A'}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="text-gray-400">Reports generated:</span>
                <span className="text-gray-200">{monitor.reports_count}</span>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
