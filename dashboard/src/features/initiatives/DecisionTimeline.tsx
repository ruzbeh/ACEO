import { useDecisions } from '../../api/initiatives';
import { Badge } from '../../components/ui/Badge';
import { formatDateTime } from '../../lib/utils';
import { Spinner } from '../../components/ui/Spinner';

export function DecisionTimeline({ initiativeId }: { initiativeId: string }) {
  const { data, isLoading } = useDecisions(initiativeId);

  if (isLoading) return <Spinner />;

  const decisions = data?.decisions ?? [];
  if (decisions.length === 0) {
    return <p className="text-sm text-gray-500">No decisions recorded yet.</p>;
  }

  return (
    <div className="relative space-y-6 pl-6">
      {/* vertical line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-border" />

      {decisions.map((d, index) => (
        <div key={d.id} className="relative">
          {/* dot */}
          <div className="absolute -left-6 top-1 h-3.5 w-3.5 rounded-full border-2 border-accent bg-surface" />

          <div className="rounded-lg border border-border bg-surface-overlay p-4">
            <div className="flex flex-wrap items-center gap-2">
              {index === 0 && (
                <Badge className="bg-emerald-500/20 text-emerald-400 text-[10px]">Latest</Badge>
              )}
              <Badge className="bg-accent/20 text-accent">{d.category}</Badge>
              <span className="text-xs text-gray-500">{d.agent_id}</span>
              <span className="ml-auto text-xs text-gray-600">{formatDateTime(d.created_at)}</span>
            </div>
            <p className="mt-2 text-sm text-gray-200">{d.decision}</p>
            {d.reasoning && <p className="mt-1 text-xs text-gray-400">{d.reasoning}</p>}

            {d.assumptions.length > 0 && (
              <div className="mt-2">
                <span className="text-[10px] font-medium uppercase text-gray-500">Assumptions</span>
                <ul className="mt-0.5 list-disc pl-4 text-xs text-gray-400">
                  {d.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              </div>
            )}

            <div className="mt-2 flex items-center gap-3">
              <span className="text-xs text-gray-500">
                Confidence: <span className="text-gray-300">{(d.confidence * 100).toFixed(0)}%</span>
              </span>
              {d.risks.length > 0 && (
                <span className="text-xs text-red-400">{d.risks.length} risk{d.risks.length > 1 ? 's' : ''}</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
