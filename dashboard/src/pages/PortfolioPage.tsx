import { useState } from 'react';
import {
  Briefcase,
  Play,
  Square,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  History,
  Target,
  Lightbulb,
  Gavel,
  Rocket,
  MessageSquare,
  DollarSign,
  ChevronDown,
  ChevronRight,
  Zap,
  Skull,
  Scale,
  AlertCircle,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { cn } from '../lib/utils';
import {
  usePortfolioRuns,
  usePortfolioStatus,
  useRunPortfolio,
  useStopPortfolio,
  useApprovalQueue,
  useApproveAction,
} from '../api/portfolio';
import type { PortfolioListItem, PortfolioMessage, PortfolioStatusResponse } from '../api/types';

const PHASE_COLORS: Record<string, string> = {
  opportunity_scan: 'bg-amber-500/20 text-amber-400',
  portfolio_review: 'bg-blue-500/20 text-blue-400',
  executing: 'bg-green-500/20 text-green-400',
  evaluating: 'bg-purple-500/20 text-purple-400',
  rebalancing: 'bg-cyan-500/20 text-cyan-400',
  closed: 'bg-gray-500/20 text-gray-400',
  starting: 'bg-gray-500/20 text-gray-400',
  failed: 'bg-red-500/20 text-red-400',
};

const PHASE_LABELS: Record<string, string> = {
  opportunity_scan: 'Scanning Opportunities',
  portfolio_review: 'CEO Reviewing',
  executing: 'Executing Initiatives',
  evaluating: 'Evaluating Results',
  rebalancing: 'Rebalancing Portfolio',
  closed: 'Complete',
  starting: 'Starting…',
  failed: 'Failed',
};

const STATUS_ICONS: Record<string, typeof CheckCircle2> = {
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

/* ─── Run Portfolio Form ─── */

function RunPortfolioForm() {
  const [goals, setGoals] = useState('');
  const [maxCycles, setMaxCycles] = useState('2');
  const [budget, setBudget] = useState('1000');
  const runMutation = useRunPortfolio();

  const handleSubmit = () => {
    const goalList = goals.split('\n').map((g) => g.trim()).filter(Boolean);
    if (goalList.length === 0) return;
    runMutation.mutate({
      company_goals: goalList,
      max_cycles: parseInt(maxCycles) || 2,
      total_budget: parseFloat(budget) || 0,
    });
    setGoals('');
  };

  return (
    <Card>
      <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
        <Rocket size={14} className="text-accent" /> Run Portfolio Cycle
      </h3>
      <div className="space-y-3">
        <div>
          <label className="text-[10px] font-medium uppercase text-gray-500">
            Company Goals (one per line)
          </label>
          <textarea
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-accent focus:outline-none"
            rows={3}
            placeholder={"Reduce CAC below $15\nIncrease MRR to $5K\nImprove conversion rate"}
            value={goals}
            onChange={(e) => setGoals(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-medium uppercase text-gray-500">Max Cycles</label>
            <Input value={maxCycles} onChange={(e) => setMaxCycles(e.target.value)} type="number" />
          </div>
          <div>
            <label className="text-[10px] font-medium uppercase text-gray-500">Total Budget ($)</label>
            <Input value={budget} onChange={(e) => setBudget(e.target.value)} type="number" />
          </div>
        </div>
        <Button onClick={handleSubmit} disabled={runMutation.isPending || !goals.trim()}>
          {runMutation.isPending ? (
            <><Loader2 size={14} className="animate-spin mr-1" /> Starting…</>
          ) : (
            <><Play size={14} className="mr-1" /> Run Portfolio</>
          )}
        </Button>
        {runMutation.isSuccess && (
          <p className="text-xs text-green-400">
            ✓ Started portfolio: {runMutation.data.portfolio_id.slice(0, 8)}…
          </p>
        )}
      </div>
    </Card>
  );
}

/* ─── Helpers ─── */

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

function Stat({ label, value, color, icon: Icon }: {
  label: string;
  value: string | number;
  color?: string;
  icon?: typeof CheckCircle2;
}) {
  return (
    <div className="rounded-lg bg-surface-overlay/40 px-3 py-2">
      <div className="flex items-center gap-1">
        {Icon && <Icon size={10} className="text-gray-500" />}
        <span className="text-[10px] font-medium uppercase text-gray-500">{label}</span>
      </div>
      <div className={cn('text-lg font-bold', color ?? 'text-gray-200')}>{value}</div>
    </div>
  );
}

function BudgetBar({ spent, total }: { spent: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (spent / total) * 100) : 0;
  const color = pct > 80 ? 'bg-red-500' : pct > 50 ? 'bg-amber-500' : 'bg-green-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-gray-500">
        <span>Budget</span>
        <span>${spent.toFixed(0)} / ${total.toFixed(0)} ({pct.toFixed(0)}%)</span>
      </div>
      <div className="h-2 w-full rounded-full bg-surface-overlay overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Collapsible({ title, icon: Icon, count, defaultOpen, children }: {
  title: string;
  icon: typeof CheckCircle2;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-surface-overlay/30 transition-colors"
      >
        {open ? <ChevronDown size={14} className="text-gray-500" /> : <ChevronRight size={14} className="text-gray-500" />}
        <Icon size={14} className="text-accent" />
        <span className="text-sm font-semibold text-gray-200">{title}</span>
        {count !== undefined && (
          <Badge className="bg-surface-overlay text-gray-400 text-[9px] ml-auto">{count}</Badge>
        )}
      </button>
      {open && <div className="border-t border-border px-4 py-3">{children}</div>}
    </div>
  );
}

/* ─── Progress Pipeline ─── */

const PIPELINE = ['opportunity_scan', 'portfolio_review', 'executing', 'evaluating', 'rebalancing'] as const;

function ProgressPipeline({ currentPhase }: { currentPhase: string }) {
  const currentIdx = PIPELINE.indexOf(currentPhase as typeof PIPELINE[number]);
  const isClosed = currentPhase === 'closed';

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {PIPELINE.map((phase, i) => {
        const isCurrent = currentPhase === phase;
        const isPast = isClosed || (currentIdx >= 0 && i < currentIdx);
        return (
          <span key={phase} className="flex items-center gap-1">
            <span
              className={cn(
                'rounded px-2 py-0.5 text-[10px] font-mono transition-colors',
                isCurrent ? 'bg-accent/20 text-accent ring-1 ring-accent/30 animate-pulse' :
                isPast ? 'bg-green-500/10 text-green-400' : 'bg-surface text-gray-600',
              )}
            >
              {isPast && '✓ '}{phase.replace(/_/g, ' ')}
            </span>
            {i < PIPELINE.length - 1 && <span className="text-gray-600 text-[10px]">→</span>}
          </span>
        );
      })}
      {isClosed && (
        <span className="flex items-center gap-1">
          <span className="text-gray-600 text-[10px]">→</span>
          <span className="rounded px-2 py-0.5 text-[10px] font-mono bg-green-500/20 text-green-400 ring-1 ring-green-500/30">
            ✓ complete
          </span>
        </span>
      )}
    </div>
  );
}

/* ─── Portfolio Detail (the big expanded view) ─── */

function PortfolioDetail({ portfolioId, run }: { portfolioId: string; run?: PortfolioListItem }) {
  const { data: status, isLoading } = usePortfolioStatus(portfolioId);
  const stopMutation = useStopPortfolio();

  if (isLoading || !status) return <Spinner />;

  const StatusIcon = STATUS_ICONS[status.status] ?? Clock;
  const isRunning = status.status === 'running';

  return (
    <Card className="space-y-5">
      {/* Header row */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <StatusIcon
            size={18}
            className={cn(
              isRunning && 'animate-spin',
              status.status === 'completed' ? 'text-green-400' :
              status.status === 'failed' ? 'text-red-400' : 'text-accent',
            )}
          />
          <span className="text-base font-bold text-gray-200 font-mono">
            {portfolioId.slice(0, 8)}…
          </span>
          <Badge className={PHASE_COLORS[status.current_phase] ?? PHASE_COLORS.starting}>
            {PHASE_LABELS[status.current_phase] ?? status.current_phase.replace(/_/g, ' ')}
          </Badge>
          {run?.started_at && (
            <span className="text-xs text-gray-500">
              {formatDate(run.started_at)}
              {run.completed_at && ` → ${formatDate(run.completed_at)}`}
            </span>
          )}
        </div>
        {isRunning && (
          <Button variant="ghost" size="sm" onClick={() => stopMutation.mutate(portfolioId)}>
            <Square size={12} className="mr-1" /> Stop
          </Button>
        )}
      </div>

      {/* Goals */}
      {status.company_goals.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {status.company_goals.map((goal, i) => (
            <Badge key={i} className="bg-accent/10 text-accent text-xs">
              <Target size={10} className="mr-1" /> {goal}
            </Badge>
          ))}
        </div>
      )}

      {/* Progress pipeline */}
      <div className="rounded-lg border border-border bg-surface-overlay/30 px-3 py-2.5">
        <ProgressPipeline currentPhase={status.current_phase} />
      </div>

      {/* Budget bar */}
      <BudgetBar spent={status.budget_spent} total={status.total_budget} />

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Stat label="Cycle" value={`${status.cycle_count} / ${status.max_cycles}`} icon={TrendingUp} />
        <Stat label="Opportunities" value={status.opportunities_found} icon={Lightbulb} />
        <Stat label="Funded" value={status.initiatives_funded} color="text-green-400" icon={Zap} />
        <Stat label="Killed" value={status.initiatives_killed} color="text-red-400" icon={Skull} />
        <Stat label="Spent" value={`$${status.budget_spent.toFixed(0)}`} icon={DollarSign} />
        <Stat label="Remaining" value={`$${status.budget_remaining.toFixed(0)}`} icon={DollarSign} />
        <Stat label="Results" value={status.execution_results} icon={Rocket} />
      </div>

      {/* Collapsible sections */}
      <div className="space-y-2">
        {/* Opportunities */}
        <OpportunitiesSection status={status} />

        {/* CEO Decisions */}
        <DecisionsSection status={status} />

        {/* Execution Results */}
        <ResultsSection status={status} />

        {/* Activity Log */}
        <ActivityLogSection status={status} />

        {/* Errors */}
        {status.errors.length > 0 && (
          <Collapsible title="Errors" icon={AlertCircle} count={status.errors.length} defaultOpen>
            <div className="space-y-1">
              {status.errors.map((err, i) => (
                <div key={i} className="rounded bg-red-500/10 px-3 py-1.5 text-xs text-red-400 font-mono">
                  {err}
                </div>
              ))}
            </div>
          </Collapsible>
        )}
      </div>
    </Card>
  );
}

/* ─── Opportunities Section ─── */

function OpportunitiesSection({ status }: { status: PortfolioStatusResponse }) {
  if (status.opportunities.length === 0 && status.opportunities_found === 0) return null;
  return (
    <Collapsible
      title="Opportunities Discovered"
      icon={Lightbulb}
      count={status.opportunities_found}
      defaultOpen={status.current_phase === 'portfolio_review'}
    >
      {status.opportunities.length === 0 ? (
        <p className="text-xs text-gray-500 italic">Opportunities data summarized as count only</p>
      ) : (
        <div className="space-y-2">
          {status.opportunities.map((opp, i) => (
            <div key={i} className="rounded-lg bg-surface px-3 py-2 border border-border/50">
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-medium text-gray-200">{opp.title || `Opportunity ${i + 1}`}</span>
                {opp.estimated_impact && (
                  <Badge className="bg-amber-500/10 text-amber-400 text-[9px] shrink-0">
                    {opp.estimated_impact}
                  </Badge>
                )}
              </div>
              {opp.description && (
                <p className="mt-1 text-xs text-gray-400 line-clamp-2">{opp.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Collapsible>
  );
}

/* ─── CEO Decisions Section ─── */

function DecisionsSection({ status }: { status: PortfolioStatusResponse }) {
  if (status.portfolio_decisions.length === 0) return null;
  return (
    <Collapsible
      title="CEO Decisions"
      icon={Gavel}
      count={status.portfolio_decisions.length}
      defaultOpen={status.current_phase === 'executing' || status.current_phase === 'closed'}
    >
      <div className="space-y-3">
        {status.portfolio_decisions.map((d, i) => (
          <div key={i} className="rounded-lg bg-surface px-3 py-2 border border-border/50 space-y-2">
            <div className="flex items-center gap-2">
              <Badge className="bg-blue-500/10 text-blue-400 text-[9px]">{d.agent}</Badge>
              <span className="text-[10px] text-gray-500">{d.phase}</span>
            </div>
            {d.reasoning && (
              <p className="text-xs text-gray-300 leading-relaxed">{d.reasoning}</p>
            )}
            <div className="flex flex-wrap gap-2">
              {d.funded.map((f, j) => (
                <Badge key={`f-${j}`} className="bg-green-500/10 text-green-400 text-[9px]">
                  <Zap size={9} className="mr-0.5" /> Fund: {f}
                </Badge>
              ))}
              {d.killed.map((k, j) => (
                <Badge key={`k-${j}`} className="bg-red-500/10 text-red-400 text-[9px]">
                  <Skull size={9} className="mr-0.5" /> Kill: {k}
                </Badge>
              ))}
              {d.scaled.map((s, j) => (
                <Badge key={`s-${j}`} className="bg-purple-500/10 text-purple-400 text-[9px]">
                  <Scale size={9} className="mr-0.5" /> Scale: {s}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Collapsible>
  );
}

/* ─── Execution Results Section ─── */

function ResultsSection({ status }: { status: PortfolioStatusResponse }) {
  if (status.results.length === 0 && status.execution_results === 0) return null;

  const verdictColors: Record<string, string> = {
    scale: 'bg-green-500/10 text-green-400',
    continue: 'bg-blue-500/10 text-blue-400',
    pivot: 'bg-amber-500/10 text-amber-400',
    kill: 'bg-red-500/10 text-red-400',
  };
  const actionIcons: Record<string, string> = {
    completed: '✓',
    failed: '✗',
    timeout: '⏱',
    killed: '☠',
  };

  return (
    <Collapsible
      title="Execution Results"
      icon={Rocket}
      count={status.execution_results}
      defaultOpen={status.current_phase === 'closed'}
    >
      {status.results.length === 0 ? (
        <p className="text-xs text-gray-500 italic">{status.execution_results} initiative(s) executed</p>
      ) : (
        <div className="space-y-2">
          {status.results.map((r, i) => (
            <div key={i} className="rounded-lg bg-surface px-3 py-2 border border-border/50">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{actionIcons[r.action] ?? '?'}</span>
                  <span className="text-sm font-medium text-gray-200">{r.title || `Initiative ${i + 1}`}</span>
                  <Badge className={cn('text-[9px]', verdictColors[r.verdict] ?? 'bg-gray-500/10 text-gray-400')}>
                    {r.verdict || r.action}
                  </Badge>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  {r.budget_spent > 0 && <span>${r.budget_spent.toFixed(2)}</span>}
                  {r.tasks_executed > 0 && <span>{r.tasks_executed} tasks</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Collapsible>
  );
}

/* ─── Activity Log ─── */

const MSG_TYPE_STYLES: Record<string, string> = {
  phase_start: 'text-blue-400 font-semibold',
  agent_call: 'text-cyan-400',
  response: 'text-green-400',
  opportunity: 'text-amber-400',
  decisions: 'text-blue-300',
  fund_decision: 'text-green-300',
  parse_error: 'text-red-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-gray-300',
  initiative_start: 'text-purple-400',
  initiative_complete: 'text-green-400',
  initiative_killed: 'text-red-300',
  timeout: 'text-amber-400',
  portfolio_closed: 'text-blue-400 font-semibold',
  rebalance: 'text-cyan-300',
  evaluation_summary: 'text-purple-300',
};

function formatMsgContent(msg: PortfolioMessage): string {
  const type = (msg.type as string) || '';
  const content = msg.content;

  if (typeof content === 'string') return content;
  if (!content || typeof content !== 'object') return JSON.stringify(content);

  const c = content as Record<string, unknown>;

  // Specific formatting for known message types
  if (type === 'phase_start') return `── Phase: ${(c.phase as string || '').replace(/_/g, ' ')} ──`;
  if (type === 'agent_call') return c.action as string || `Calling ${c.agent}...`;
  if (type === 'response') return `Found ${c.opportunities_found ?? 0} opportunities (confidence: ${c.confidence ?? 0})`;
  if (type === 'opportunity') return `${c.index}. ${c.title} — ${c.goal || c.hypothesis || ''}`;
  if (type === 'decisions') return `Fund: ${c.funded_count}, Kill: ${c.killed_count}, Scale: ${c.scaled_count} — ${(c.reasoning as string || '').slice(0, 150)}`;
  if (type === 'fund_decision') return `Fund "${c.title}" — $${c.allocated_budget} (${c.priority}) ${(c.reasoning as string || '').slice(0, 100)}`;
  if (type === 'parse_error') return `PARSE ERROR: ${(c.error as string || '').slice(0, 200)}`;
  if (type === 'initiative_start') return `[${c.index}/${c.total}] Starting "${c.title}" — $${c.allocated_budget}`;
  if (type === 'initiative_complete') return `"${c.title}" → ${c.verdict} (${c.tasks_executed} tasks, $${c.budget_spent})`;
  if (type === 'portfolio_closed') return `Complete: ${c.cycles} cycles, $${(c.budget_spent as number || 0).toFixed(0)} spent, ${c.total_results} results`;
  if (type === 'evaluation_summary') return `Executed: ${c.total_executed}, Scaled: ${c.scaled}, Killed: ${c.killed}, Failed: ${c.failed}`;
  if (type === 'rebalance') return `Cycle ${c.cycle}/${c.max_cycles} — $${(c.budget_remaining as number || 0).toFixed(0)} remaining → ${c.next_phase}`;

  // Fallback: show key/value pairs
  const pairs = Object.entries(c).slice(0, 4).map(([k, v]) => `${k}: ${typeof v === 'string' ? v.slice(0, 80) : JSON.stringify(v)}`);
  return pairs.join(' | ');
}

function ActivityLogSection({ status }: { status: PortfolioStatusResponse }) {
  if (status.messages.length === 0) return null;
  return (
    <Collapsible title="Activity Log" icon={MessageSquare} count={status.messages.length} defaultOpen={status.status === 'running'}>
      <div className="max-h-80 overflow-y-auto space-y-0.5 pr-1 font-mono">
        {status.messages.map((msg, i) => {
          const type = msg.type || '';
          const sender = msg.sender || msg.role || '?';
          const styleClass = MSG_TYPE_STYLES[type] || 'text-gray-400';
          const isError = type === 'error' || type === 'parse_error';

          return (
            <div
              key={i}
              className={cn(
                'flex gap-2 text-[11px] leading-relaxed py-0.5',
                isError && 'bg-red-500/5 rounded px-1',
              )}
            >
              <span className="shrink-0 text-gray-600 w-28 text-right truncate">
                {sender}
              </span>
              <span className={cn('min-w-0', styleClass)}>
                {formatMsgContent(msg)}
              </span>
            </div>
          );
        })}
      </div>
    </Collapsible>
  );
}

/* ─── Approval Queue ─── */

function ApprovalQueue() {
  const { data: approvals, isLoading } = useApprovalQueue();
  const approveMutation = useApproveAction();

  if (isLoading) return <Spinner />;

  const pending = (approvals ?? []).filter((a) => a.status === 'pending');

  if (pending.length === 0) {
    return (
      <EmptyState
        icon={ThumbsUp}
        title="No pending approvals"
        description="High-impact decisions will appear here for your review"
      />
    );
  }

  return (
    <div className="space-y-3">
      {pending.map((approval) => (
        <Card key={approval.id}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-400" />
                <span className="text-sm font-semibold text-gray-200">{approval.initiative_title}</span>
                <Badge className="bg-amber-500/20 text-amber-400 text-[9px]">{approval.action}</Badge>
                <Badge className="bg-surface-overlay text-gray-400 text-[9px]">{approval.blast_radius}</Badge>
              </div>
              <p className="mt-1 text-xs text-gray-400">{approval.reasoning}</p>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-500">
                <span>Budget: ${approval.allocated_budget.toFixed(2)}</span>
                <span>By: {approval.requested_by}</span>
              </div>
            </div>
            <div className="flex gap-2 shrink-0 ml-4">
              <Button
                size="sm"
                onClick={() => approveMutation.mutate({ id: approval.id, action: 'approve' })}
                disabled={approveMutation.isPending}
              >
                <ThumbsUp size={12} className="mr-1" /> Approve
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => approveMutation.mutate({ id: approval.id, action: 'reject' })}
                disabled={approveMutation.isPending}
              >
                <ThumbsDown size={12} className="mr-1" /> Reject
              </Button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ─── Main Page ─── */

export function PortfolioPage() {
  const { data: runs, isLoading } = usePortfolioRuns();

  const runningCount = (runs ?? []).filter((r) => r.status === 'running').length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Briefcase className="h-7 w-7 text-accent" />
        <div>
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <p className="text-sm text-gray-400">
            Autonomous opportunity discovery, CEO-led initiative funding, and execution tracking
          </p>
        </div>
        {runningCount > 0 && (
          <Badge className="bg-green-500/20 text-green-400 ml-auto">
            <Loader2 size={10} className="animate-spin mr-1" /> {runningCount} running
          </Badge>
        )}
      </div>

      {/* Approval Queue */}
      <section>
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-gray-200">
          <AlertTriangle size={16} className="text-amber-400" />
          Approval Queue
        </h2>
        <ApprovalQueue />
      </section>

      {/* Run form + Active runs */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-4">
          <RunPortfolioForm />

          {/* Quick info card */}
          <Card className="text-xs text-gray-500 space-y-2">
            <h4 className="text-[10px] font-medium uppercase text-gray-400">How it works</h4>
            <ol className="list-decimal list-inside space-y-1">
              <li>Product Strategist scans for opportunities</li>
              <li>CEO reviews and funds the best initiatives</li>
              <li>PM, Architect, Security review each initiative</li>
              <li>Engineers execute the tasks autonomously</li>
              <li>Evaluator judges results: scale, continue, pivot, or kill</li>
              <li>Repeat until budget depleted or max cycles reached</li>
            </ol>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-200">
            <History size={18} />
            Portfolio Runs
          </h2>
          {isLoading ? (
            <Spinner />
          ) : !runs?.length ? (
            <EmptyState
              icon={TrendingUp}
              title="No portfolio runs yet"
              description="Enter your company goals and run your first portfolio cycle. The AI agents will discover opportunities, fund initiatives, and execute them autonomously."
            />
          ) : (
            runs.map((run) => (
              <PortfolioDetail key={run.portfolio_id} portfolioId={run.portfolio_id} run={run} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
