import { Card } from '../../components/ui/Card';
import { Lightbulb } from 'lucide-react';
import { formatCurrency } from '../../lib/utils';
import type { OptimizationReport } from '../../api/types';

export function OptimizationPanel({ report }: { report: OptimizationReport }) {
  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb size={16} className="text-yellow-400" />
        <h3 className="text-sm font-medium text-gray-300">Optimization Insights</h3>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <span className="text-xs text-gray-500">Daily Burn Rate</span>
          <p className="text-sm font-medium text-gray-200">{formatCurrency(report.daily_burn_rate)}/day</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Projected Spend</span>
          <p className={`text-sm font-medium ${report.projected_over_budget ? 'text-red-400' : 'text-gray-200'}`}>
            {formatCurrency(report.projected_total_spend)}
          </p>
        </div>
      </div>

      {report.top_spenders.length > 0 && (
        <div className="mb-4">
          <span className="text-xs font-medium text-gray-500">Top Spenders</span>
          <div className="mt-1 space-y-1">
            {report.top_spenders.slice(0, 5).map((s) => (
              <div key={s.agent_id} className="flex items-center justify-between text-xs">
                <span className="text-gray-400">{s.agent_id}</span>
                <span className="text-gray-300">{formatCurrency(s.total)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {report.optimization_hints.length > 0 && (
        <div className="mb-3">
          <span className="text-xs font-medium text-gray-500">Hints</span>
          <ul className="mt-1 list-disc pl-4 space-y-0.5 text-xs text-gray-400">
            {report.optimization_hints.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      )}

      <div className="rounded-lg bg-accent/10 px-3 py-2">
        <p className="text-xs text-accent">{report.recommendation}</p>
      </div>
    </Card>
  );
}
