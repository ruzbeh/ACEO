import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Camera, CheckCircle2, DollarSign, Loader2, Play, RefreshCw, Square, Target, XCircle } from 'lucide-react';
import { useInitiative, useRunInitiative, useKillInitiative, useInitiativeSpend } from '../api/initiatives';
import { useSubmitVisualFeedback, useVisualFeedbackList } from '../api/visual-feedback';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { StatusPipeline } from '../components/ui/StatusPipeline';
import { ScreenshotUpload } from '../components/ui/ScreenshotUpload';
import type { ScreenshotUploadData } from '../components/ui/ScreenshotUpload';
import { VerdictBadge } from '../features/initiatives/VerdictBadge';
import { DecisionTimeline } from '../features/initiatives/DecisionTimeline';
import { WhatsHappening } from '../features/initiatives/WhatsHappening';
import { InitiativeLiveTrace } from '../features/initiatives/InitiativeLiveTrace';
import { INITIATIVE_STATUSES, INITIATIVE_STATUS_COLORS } from '../lib/constants';
import { formatDate, formatExactDateTime } from '../lib/utils';

export function InitiativeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: initiative, isLoading } = useInitiative(id!);
  const run = useRunInitiative();
  const kill = useKillInitiative();
  const { data: spend } = useInitiativeSpend(id!);
  const [pendingFeedback, setPendingFeedback] = useState<ScreenshotUploadData | null>(null);
  const submitFeedback = useSubmitVisualFeedback();
  const { data: feedbackList } = useVisualFeedbackList(id);

  if (isLoading || !initiative) {
    return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;
  }

  const canRun = initiative.status === 'draft';
  const canRerun = initiative.status === 'closed';
  const canKill = initiative.status !== 'closed';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/initiatives" className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-200 mb-4">
          <ArrowLeft size={14} /> Back to initiatives
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{initiative.title}</h1>
            <p className="mt-1 text-sm text-gray-400">{initiative.goal}</p>
            {initiative.run_started_at && (
              <p className="mt-2 text-xs text-gray-500">
                <span className="text-gray-400">Workflow run started:</span>{' '}
                <time dateTime={initiative.run_started_at} className="font-mono text-gray-300">
                  {formatExactDateTime(initiative.run_started_at)}
                </time>
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <VerdictBadge verdict={initiative.verdict} />
            {canRun && (
              <>
                <Button
                  onClick={() => run.mutate({ initiative_id: initiative.id })}
                  disabled={run.isPending}
                  size="sm"
                >
                  <Play size={14} className="mr-1" />
                  {run.isPending ? 'Starting...' : 'Run'}
                </Button>
                {run.isError && (
                  <p className="text-sm text-red-400" role="alert">
                    {(() => {
                      const err = run.error;
                      if (err && typeof err === 'object' && 'message' in err && typeof (err as { message: string }).message === 'string') {
                        const msg = (err as { message: string }).message;
                        try {
                          const d = JSON.parse(msg) as { detail?: string };
                          if (d.detail) return d.detail;
                        } catch {
                          /* not JSON */
                        }
                        return msg;
                      }
                      return String(err);
                    })()}
                  </p>
                )}
              </>
            )}
            {canRerun && (
              <Button
                size="sm"
                onClick={() => run.mutate({ initiative_id: initiative.id })}
                disabled={run.isPending}
              >
                <RefreshCw size={14} className="mr-1" />
                {run.isPending ? 'Restarting...' : 'Rerun'}
              </Button>
            )}
            {canKill && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => kill.mutate(initiative.id)}
                disabled={kill.isPending}
              >
                <Square size={14} className="mr-1" />
                {kill.isPending ? 'Killing...' : 'Kill'}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline */}
      <Card>
        <h3 className="mb-4 text-sm font-medium text-gray-300">Lifecycle</h3>
        <StatusPipeline
          stages={[...INITIATIVE_STATUSES]}
          current={initiative.status}
          colorMap={Object.fromEntries(
            Object.entries(INITIATIVE_STATUS_COLORS).map(([k, v]) => {
              const match = v.match(/text-(\S+)/);
              return [k, match ? match[0] : 'text-gray-400'];
            }),
          )}
        />
      </Card>

      {/* What's happening (when in progress) */}
      <WhatsHappening status={initiative.status} />

      <InitiativeLiveTrace
        initiativeId={initiative.id}
        status={initiative.status}
        workflowRunStartedAt={initiative.run_started_at}
      />

      {/* Meta */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Status</span>
          <div className="mt-2">
            <Badge className={INITIATIVE_STATUS_COLORS[initiative.status] ?? ''}>
              {initiative.status.replace('_', ' ')}
            </Badge>
          </div>
        </Card>
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Workflow run started</span>
          <p className="mt-2 font-mono text-sm text-gray-200">
            {initiative.run_started_at ? formatExactDateTime(initiative.run_started_at) : '—'}
          </p>
          <p className="mt-1 text-[10px] text-gray-500">Exact local time when Run was last clicked</p>
        </Card>
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">North Star Metric</span>
          <div className="mt-2 flex items-center gap-2">
            <Target size={14} className="text-accent" />
            <span className="text-sm text-gray-200">{initiative.north_star_metric ?? 'Not defined'}</span>
          </div>
        </Card>
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Created</span>
          <p className="mt-2 text-sm text-gray-200">{formatDate(initiative.created_at)}</p>
        </Card>
      </div>

      {/* Hypothesis */}
      {initiative.hypothesis && (
        <Card>
          <h3 className="mb-2 text-sm font-medium text-gray-300">Hypothesis</h3>
          <p className="text-sm text-gray-400">{initiative.hypothesis}</p>
        </Card>
      )}

      {/* Visual Feedback */}
      <Card>
        <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-gray-300">
          <Camera size={16} className="text-accent" />
          Visual Feedback
        </h3>
        <ScreenshotUpload
          compact
          label=""
          placeholder="Describe the issue or desired change…"
          onUpload={(data) => setPendingFeedback(data)}
        />
        {pendingFeedback && (
          <div className="mt-3 flex items-center gap-3">
            <img
              src={URL.createObjectURL(pendingFeedback.file)}
              alt="Pending feedback"
              className="h-10 w-10 rounded border border-border object-cover"
            />
            <span className="flex-1 truncate text-xs text-gray-400">{pendingFeedback.feedback || pendingFeedback.file.name}</span>
            <Button
              size="sm"
              onClick={() => {
                submitFeedback.mutate(
                  { file: pendingFeedback.file, feedback: pendingFeedback.feedback, initiative_id: id },
                  { onSuccess: () => setPendingFeedback(null) },
                );
              }}
              disabled={submitFeedback.isPending}
            >
              {submitFeedback.isPending ? (
                <><Loader2 size={14} className="animate-spin mr-1" /> Sending…</>
              ) : (
                'Send Feedback'
              )}
            </Button>
          </div>
        )}
        {feedbackList && feedbackList.length > 0 && (
          <div className="mt-4 space-y-2">
            <span className="text-xs font-medium uppercase text-gray-500">Previous feedback</span>
            <ul className="space-y-1.5">
              {feedbackList.map((item) => (
                <li key={item.id} className="flex items-center gap-2 text-sm">
                  {item.status === 'running' || item.status === 'pending' ? (
                    <Loader2 size={14} className="animate-spin text-amber-400" />
                  ) : item.status === 'done' ? (
                    <CheckCircle2 size={14} className="text-green-400" />
                  ) : (
                    <XCircle size={14} className="text-red-400" />
                  )}
                  <span className="flex-1 truncate text-gray-300">{item.feedback || 'Screenshot'}</span>
                  <Badge className={
                    item.status === 'done'
                      ? 'bg-green-500/20 text-green-400'
                      : item.status === 'error'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-amber-500/20 text-amber-400'
                  }>
                    {item.status}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* Budget spend for this initiative */}
      {spend && (spend.total_cost > 0 || spend.records.length > 0) && (
        <Card>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-gray-300">
            <DollarSign size={16} className="text-accent" />
            Initiative spend
          </h3>
          <div className="mb-4 flex gap-6">
            <div>
              <span className="text-xs text-gray-500">Total cost</span>
              <p className="text-lg font-semibold text-gray-100">${spend.total_cost.toFixed(4)}</p>
            </div>
            <div>
              <span className="text-xs text-gray-500">Tokens</span>
              <p className="text-lg font-semibold text-gray-100">{spend.total_tokens.toLocaleString()}</p>
            </div>
          </div>
          {Object.keys(spend.by_agent).length > 0 && (
            <div className="mb-4">
              <span className="text-xs font-medium uppercase text-gray-500">By agent</span>
              <ul className="mt-2 space-y-1">
                {Object.entries(spend.by_agent).map(([agent, v]) => (
                  <li key={agent} className="flex justify-between text-sm">
                    <span className="text-gray-300">{agent}</span>
                    <span className="text-gray-200">${v.total.toFixed(4)} ({v.tokens.toLocaleString()} tokens)</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {spend.records.length > 0 && (
            <div>
              <span className="text-xs font-medium uppercase text-gray-500">Recent activity</span>
              <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs">
                {spend.records.slice(0, 10).map((r) => (
                  <li key={r.id} className="flex justify-between text-gray-400">
                    <span>{r.agent_id}</span>
                    <span>${r.amount.toFixed(4)} · {formatDate(r.created_at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {/* Decision Ledger / Live activity */}
      <div>
        <h2 className="text-lg font-semibold">Decision history</h2>
        <p className="mt-1 mb-4 text-sm text-gray-500">
          {initiative.status !== 'draft' && initiative.status !== 'closed'
            ? 'New decisions appear here as agents work (auto-refreshes every few seconds).'
            : 'Decisions recorded during the initiative run.'}
        </p>
        <DecisionTimeline initiativeId={id!} />
      </div>
    </div>
  );
}
