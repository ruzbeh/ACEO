import { ScrollText } from 'lucide-react';
import { useInitiativeLiveLog } from '../../api/initiatives';
import { cn, formatExactDateTime } from '../../lib/utils';

const LIVE_CAT_STYLES: Record<string, string> = {
  agent: 'text-cyan-400',
  tool: 'text-amber-400',
  state: 'text-blue-400',
  workflow: 'text-purple-400',
  error: 'text-red-400',
};

function formatLiveLogLine(entry: Record<string, unknown>): string {
  const ts = typeof entry.ts === 'string' ? entry.ts.slice(11, 23) : '';
  const cat = String(entry.cat ?? '');
  const ev = String(entry.event ?? '');
  const rest = { ...entry };
  delete rest.ts;
  delete rest.cat;
  delete rest.event;
  const tail = Object.keys(rest).length ? ` ${JSON.stringify(rest)}` : '';
  return `${ts} [${cat}/${ev}]${tail}`;
}

interface InitiativeLiveTraceProps {
  initiativeId: string;
  status: string;
  /** From GET /initiatives/:id — shown when live-log payload has not refreshed yet */
  workflowRunStartedAt?: string | null;
}

/** Real-time company log (agents, tools, graph nodes) for this initiative run. */
export function InitiativeLiveTrace({
  initiativeId,
  status,
  workflowRunStartedAt,
}: InitiativeLiveTraceProps) {
  const { data, isLoading } = useInitiativeLiveLog(initiativeId, status);
  const lines = data?.lines ?? [];
  const runStarted = data?.run_started_at ?? workflowRunStartedAt ?? null;
  const inFlight = status !== 'draft' && status !== 'closed';

  if (status === 'draft' && lines.length === 0 && !workflowRunStartedAt) {
    return null;
  }

  return (
    <div className="rounded-xl border border-border bg-surface-overlay p-4">
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
        <div className="flex items-center gap-2">
          <ScrollText size={16} className="text-accent" />
          <h3 className="text-sm font-medium text-gray-200">Live trace</h3>
        </div>
        {runStarted && (
          <p className="text-[10px] text-gray-500 sm:ml-auto">
            Run started{' '}
            <time dateTime={runStarted} className="font-mono text-gray-400">
              {formatExactDateTime(runStarted)}
            </time>
          </p>
        )}
      </div>
      <p className="mb-3 text-[10px] text-gray-500">
        Agent, tool, and orchestration JSON logs (updates in real time). Replay this list after the run to inspect the same sequence.
      </p>
      {isLoading && lines.length === 0 ? (
        <p className="text-xs text-gray-500">Loading log…</p>
      ) : lines.length === 0 ? (
        <p className="text-xs text-gray-500 italic">
          {inFlight
            ? 'Waiting for activity — lines appear as agents and tools log.'
            : 'No buffered log for this initiative (only available after a run on this server).'}
        </p>
      ) : (
        <div className="max-h-96 overflow-y-auto space-y-0.5 pr-1 font-mono text-[10px] leading-relaxed">
          {lines.map((entry, i) => {
            const cat = String((entry as Record<string, unknown>).cat ?? '');
            const styleClass = LIVE_CAT_STYLES[cat] || 'text-gray-400';
            return (
              <div key={i} className={cn('break-all rounded px-0.5 py-0.5', styleClass)}>
                {formatLiveLogLine(entry as Record<string, unknown>)}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
