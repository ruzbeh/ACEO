import { Card } from '../../components/ui/Card';
import { UtilizationBar } from '../../components/charts/UtilizationBar';
import { formatCurrency } from '../../lib/utils';
import type { BudgetResponse } from '../../api/types';

export function BudgetOverview({ budget }: { budget: BudgetResponse }) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-300">{budget.name}</h3>
        <span className="text-xs text-gray-500">{budget.scope}</span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <span className="text-xs text-gray-500">Total Budget</span>
          <p className="text-lg font-semibold text-gray-100">{formatCurrency(budget.total_budget)}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Spent</span>
          <p className="text-lg font-semibold text-yellow-400">{formatCurrency(budget.spent)}</p>
        </div>
        <div>
          <span className="text-xs text-gray-500">Remaining</span>
          <p className="text-lg font-semibold text-emerald-400">{formatCurrency(budget.remaining)}</p>
        </div>
      </div>

      <UtilizationBar percent={budget.utilization_percent} />
      <p className="mt-2 text-right text-xs text-gray-500">
        {budget.utilization_percent.toFixed(1)}% utilized
      </p>
    </Card>
  );
}
