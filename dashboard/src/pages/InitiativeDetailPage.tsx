import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Play, Target } from 'lucide-react';
import { useInitiative, useRunInitiative } from '../api/initiatives';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { StatusPipeline } from '../components/ui/StatusPipeline';
import { VerdictBadge } from '../features/initiatives/VerdictBadge';
import { DecisionTimeline } from '../features/initiatives/DecisionTimeline';
import { WhatsHappening } from '../features/initiatives/WhatsHappening';
import { INITIATIVE_STATUSES, INITIATIVE_STATUS_COLORS } from '../lib/constants';
import { formatDate } from '../lib/utils';

export function InitiativeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: initiative, isLoading } = useInitiative(id!);
  const run = useRunInitiative();

  if (isLoading || !initiative) {
    return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;
  }

  const canRun = initiative.status === 'draft';

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
          </div>
          <div className="flex items-center gap-3">
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

      {/* Meta */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Status</span>
          <div className="mt-2">
            <Badge className={INITIATIVE_STATUS_COLORS[initiative.status] ?? ''}>
              {initiative.status.replace('_', ' ')}
            </Badge>
          </div>
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
