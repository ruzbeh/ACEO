import { Badge } from '../../components/ui/Badge';
import { formatDateTime } from '../../lib/utils';
import type { BudgetAlert } from '../../api/types';

const SEVERITY_COLORS: Record<string, string> = {
  info: 'bg-blue-500/20 text-blue-400',
  warning: 'bg-yellow-500/20 text-yellow-400',
  critical: 'bg-red-500/20 text-red-400',
};

export function AlertsList({ alerts }: { alerts: BudgetAlert[] }) {
  if (alerts.length === 0) {
    return <p className="text-sm text-gray-500">No alerts.</p>;
  }

  return (
    <div className="space-y-2">
      {alerts.map((a) => (
        <div key={a.id} className="flex items-start gap-3 rounded-lg border border-border bg-surface-overlay p-3">
          <Badge className={SEVERITY_COLORS[a.severity] ?? ''}>{a.severity}</Badge>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-gray-200">{a.message}</p>
            <span className="text-xs text-gray-500">{formatDateTime(a.created_at)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
