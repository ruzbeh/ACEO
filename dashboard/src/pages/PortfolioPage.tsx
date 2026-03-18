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

const STATUS_ICONS: Record<string, typeof CheckCircle2> = {
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

function RunPortfolioForm() {
  const [goals, setGoals] = useState('');
  const [maxCycles, setMaxCycles] = useState('2');
  const [budget, setBudget] = useState('1000');
  const runMutation = useRunPortfolio();

  const handleSubmit = () => {
    const goalList = goals
      .split('\n')
      .map((g) => g.trim())
      .filter(Boolean);
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
      <h3 className="text-sm font-semibold text-gray-200 mb-3">Run Portfolio Cycle</h3>
      <div className="space-y-3">
        <div>
          <label className="text-[10px] font-medium uppercase text-gray-500">Company Goals (one per line)</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-accent focus:outline-none"
            rows={3}
            placeholder={"Increase user retention\nReduce checkout abandonment\nImprove API reliability"}
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
            <><Loader2 size={14} className="animate-spin mr-1" /> Starting...</>
          ) : (
            <><Play size={14} className="mr-1" /> Run Portfolio</>
          )}
        </Button>
        {runMutation.isSuccess && (
          <p className="text-xs text-green-400">
            Started portfolio: {runMutation.data.portfolio_id.slice(0, 8)}...
          </p>
        )}
      </div>
    </Card>
  );
}

function PortfolioDetail({ portfolioId }: { portfolioId: string }) {
  const { data: status, isLoading } = usePortfolioStatus(portfolioId);
  const stopMutation = useStopPortfolio();

  if (isLoading || !status) return <Spinner />;

  const StatusIcon = STATUS_ICONS[status.status] ?? Clock;
  const isRunning = status.status === 'running';

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <StatusIcon
            size={16}
            className={cn(
              isRunning && 'animate-spin',
              status.status === 'completed' ? 'text-green-400' : status.status === 'failed' ? 'text-red-400' : 'text-accent',
            )}
          />
          <span className="text-sm font-semibold text-gray-200">
            {portfolioId.slice(0, 8)}...
          </span>
          <Badge className={PHASE_COLORS[status.current_phase] ?? PHASE_COLORS.starting}>
            {status.current_phase.replace(/_/g, ' ')}
          </Badge>
        </div>
        {isRunning && (
          <Button variant="ghost" size="sm" onClick={() => stopMutation.mutate(portfolioId)}>
            <Square size={12} className="mr-1" /> Stop
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Cycle" value={`${status.cycle_count} / ${status.max_cycles}`} />
        <Stat label="Opportunities" value={status.opportunities_found} />
        <Stat label="Funded" value={status.initiatives_funded} color="text-green-400" />
        <Stat label="Killed" value={status.initiatives_killed} color="text-red-400" />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label="Budget Spent" value={`$${status.budget_spent.toFixed(2)}`} />
        <Stat label="Remaining" value={`$${status.budget_remaining.toFixed(2)}`} />
        <Stat label="Results" value={status.execution_results} />
      </div>

      {/* Phase pipeline */}
      <div className="mt-4 flex flex-wrap items-center gap-1">
        {['opportunity_scan', 'portfolio_review', 'executing', 'evaluating', 'rebalancing'].map((phase, i, arr) => {
          const isCurrent = status.current_phase === phase;
          const isPast = arr.indexOf(status.current_phase) > i;
          return (
            <span key={phase} className="flex items-center gap-1">
              <span
                className={cn(
                  'rounded px-2 py-0.5 text-[10px] font-mono transition-colors',
                  isCurrent ? 'bg-accent/20 text-accent ring-1 ring-accent/30' :
                  isPast ? 'bg-surface-overlay text-gray-300' : 'bg-surface text-gray-600',
                )}
              >
                {phase.replace(/_/g, ' ')}
              </span>
              {i < arr.length - 1 && <span className="text-gray-600 text-[10px]">&rarr;</span>}
            </span>
          );
        })}
      </div>
    </Card>
  );
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase text-gray-500">{label}</div>
      <div className={cn('text-lg font-bold', color ?? 'text-gray-200')}>{value}</div>
    </div>
  );
}

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
              </div>
              <p className="mt-1 text-xs text-gray-400">{approval.reasoning}</p>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-500">
                <span>Budget: ${approval.allocated_budget.toFixed(2)}</span>
                <span>Blast radius: {approval.blast_radius}</span>
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

export function PortfolioPage() {
  const { data: runs, isLoading } = usePortfolioRuns();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Briefcase className="h-7 w-7 text-accent" />
        <div>
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <p className="text-sm text-gray-400">
            Autonomous opportunity discovery, initiative funding, and portfolio management
          </p>
        </div>
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
        <div>
          <RunPortfolioForm />
        </div>
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-base font-semibold text-gray-200">Portfolio Runs</h2>
          {isLoading ? (
            <Spinner />
          ) : !runs?.length ? (
            <EmptyState
              icon={TrendingUp}
              title="No portfolio runs yet"
              description="Run your first portfolio cycle to discover opportunities and fund initiatives"
            />
          ) : (
            runs.map((run) => (
              <PortfolioDetail key={run.portfolio_id} portfolioId={run.portfolio_id} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
