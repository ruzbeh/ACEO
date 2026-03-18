import { useWorkflows } from '../../api/workflows';
import { Badge } from '../../components/ui/Badge';
import { WORKFLOW_STATUS_COLORS } from '../../lib/constants';
import { formatDateTime } from '../../lib/utils';
import { Spinner } from '../../components/ui/Spinner';

export function ActivityFeed() {
  const { data, isLoading } = useWorkflows();

  if (isLoading) return <Spinner />;

  const recent = (data ?? []).slice(0, 20);

  if (recent.length === 0) {
    return <p className="text-sm text-gray-500">No workflow activity yet.</p>;
  }

  return (
    <div className="space-y-2">
      {recent.map((w) => (
        <div key={w.id} className="flex items-center gap-3 rounded-lg border border-border bg-surface-overlay px-4 py-3">
          <Badge className={WORKFLOW_STATUS_COLORS[w.status] ?? ''}>{w.status}</Badge>
          <div className="min-w-0 flex-1">
            <span className="text-sm text-gray-200">Task {w.task_id.slice(0, 8)}...</span>
            <span className="ml-2 text-xs text-gray-500">node: {w.current_node}</span>
          </div>
          <span className="text-xs text-gray-600">{formatDateTime(w.started_at)}</span>
        </div>
      ))}
    </div>
  );
}
