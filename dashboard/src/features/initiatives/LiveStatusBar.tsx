import { useInitiativeLiveStatus } from '../../api/initiatives';
import type { InitiativeLiveStatus } from '../../api/types';
import { cn } from '../../lib/utils';

/** Human-friendly labels for each graph node. */
const PHASE_LABELS: Record<string, string> = {
  intake: 'Intake',
  pm_spec: 'PM Spec',
  architect: 'Architect',
  security_review: 'Security',
  task_planning: 'Tasks',
  execute_tasks: 'Execute',
  evaluate: 'Evaluate',
  acceptance_test: 'Accept',
  close: 'Close',
};

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

interface LiveStatusBarProps {
  initiativeId: string;
  status: string;
  /** Compact mode for embedding inside WhatsHappening. */
  compact?: boolean;
}

export function LiveStatusBar({ initiativeId, status, compact = false }: LiveStatusBarProps) {
  const { data: live } = useInitiativeLiveStatus(initiativeId, status);

  const inProgress = status !== 'draft' && status !== 'closed';

  // If no data yet but initiative is in-flight, show a skeleton
  if (!live && inProgress) {
    return (
      <div className="animate-pulse rounded-lg border border-border bg-surface p-4">
        <div className="h-4 w-48 rounded bg-gray-700" />
        <div className="mt-3 flex items-center gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              {i > 0 && <div className="h-0.5 w-6 bg-gray-700" />}
              <div className="h-3 w-3 rounded-full bg-gray-700" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!live) return null;

  // Don't render for draft initiatives
  if (status === 'draft') return null;

  return (
    <div
      className={cn(
        'rounded-lg border bg-surface',
        inProgress ? 'border-accent/30' : 'border-border',
        compact ? 'p-3' : 'p-4',
      )}
    >
      <PhaseProgressBar live={live} inProgress={inProgress} compact={compact} />

      {/* Bottom info row */}
      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-gray-400">
          {live.tasks.length > 0 && (
            <TaskSummary tasks={live.tasks} />
          )}
          <span className="font-mono tabular-nums">
            {formatElapsed(live.elapsed_seconds)}
          </span>
          {live.verdict && (
            <span
              className={cn(
                'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase',
                live.verdict === 'scale'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : live.verdict === 'iterate'
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-red-500/20 text-red-400',
              )}
            >
              {live.verdict}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/** The horizontal phase dots with connecting lines. */
function PhaseProgressBar({
  live,
  inProgress,
  compact,
}: {
  live: InitiativeLiveStatus;
  inProgress: boolean;
  compact: boolean;
}) {
  const { phases_completed, current_node, phases_remaining } = live.progress;
  const allPhases = [...phases_completed, current_node, ...phases_remaining];

  return (
    <div className={cn('flex items-center', compact ? 'gap-0.5' : 'gap-1')}>
      {allPhases.map((phase, i) => {
        const isCompleted = phases_completed.includes(phase);
        const isCurrent = phase === current_node;
        const isRemaining = phases_remaining.includes(phase);

        return (
          <div key={phase} className="flex items-center gap-1">
            {/* Connector line */}
            {i > 0 && (
              <div
                className={cn(
                  'h-0.5',
                  compact ? 'w-4' : 'w-6',
                  isCompleted
                    ? 'bg-emerald-500'
                    : isCurrent
                      ? 'bg-accent'
                      : 'bg-border',
                )}
              />
            )}
            {/* Dot + label */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'rounded-full border-2',
                  compact ? 'h-2.5 w-2.5' : 'h-3 w-3',
                  isCompleted
                    ? 'border-emerald-500 bg-emerald-500'
                    : isCurrent && inProgress
                      ? 'border-accent bg-accent animate-pulse'
                      : isCurrent && !inProgress
                        ? 'border-accent bg-accent'
                        : 'border-border bg-transparent',
                )}
              />
              {!compact && (
                <span
                  className={cn(
                    'mt-1.5 text-[10px] leading-none whitespace-nowrap',
                    isCurrent
                      ? 'text-gray-200 font-medium'
                      : isCompleted
                        ? 'text-emerald-500'
                        : 'text-gray-600',
                  )}
                >
                  {PHASE_LABELS[phase] ?? phase}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Shows current agent working and task counts. */
function TaskSummary({ tasks }: { tasks: InitiativeLiveStatus['tasks'] }) {
  const inProgress = tasks.filter((t) => t.status === 'in_progress');
  const completed = tasks.filter((t) => t.status === 'completed');
  const failed = tasks.filter((t) => t.status === 'failed');

  const activeAgent = inProgress.length > 0 ? inProgress[inProgress.length - 1] : null;

  return (
    <div className="flex items-center gap-3">
      {activeAgent && (
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <span className="text-gray-300">{activeAgent.agent_id}</span>
        </span>
      )}
      {tasks.length > 0 && (
        <span>
          {completed.length}/{tasks.length} tasks
          {failed.length > 0 && (
            <span className="text-red-400"> ({failed.length} failed)</span>
          )}
        </span>
      )}
    </div>
  );
}
