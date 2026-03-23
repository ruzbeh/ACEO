import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Wallet } from 'lucide-react';
import { useActiveBudget, useBudgetSummary, useOptimization, useSpendOverTime, useSpendByInitiative, useRecentSpend } from '../api/budget';
import { useInitiatives } from '../api/initiatives';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { SpendDonut } from '../components/charts/SpendDonut';
import { AgentBarChart } from '../components/charts/AgentBarChart';
import { BudgetOverview } from '../features/budget/BudgetOverview';
import { AlertsList } from '../features/budget/AlertsList';
import { OptimizationPanel } from '../features/budget/OptimizationPanel';
import { CreateBudgetDialog } from '../features/budget/CreateBudgetDialog';
import { formatCurrency, formatDateTime } from '../lib/utils';

export function BudgetPage() {
  const [open, setOpen] = useState(false);
  const { data: budget, isLoading } = useActiveBudget();
  const budgetId = (budget as { budget_id?: string })?.budget_id ?? (budget as { id?: string })?.id;
  const { data: summary } = useBudgetSummary(budgetId);
  const { data: optimization } = useOptimization(budgetId);
  const { data: spendOverTime } = useSpendOverTime(budgetId, { groupBy: 'day' });
  const { data: byInitiative } = useSpendByInitiative(budgetId);
  const { data: recentSpend } = useRecentSpend(budgetId);
  const { data: initiatives } = useInitiatives();

  if (isLoading) return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Budget & Spend</h1>
          <p className="mt-1 text-sm text-gray-400">Resource governance and cost tracking</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} className="mr-1.5" />
          New Budget
        </Button>
      </div>

      {!budget ? (
        <EmptyState
          icon={Wallet}
          title="No active budget"
          description="Without an active budget period, spend is not monitored or logged. Create a budget to track agent usage (tokens/cost) and get alerts."
          action={<Button onClick={() => setOpen(true)} size="sm">Create Budget</Button>}
        />
      ) : (
        <div className="space-y-6">
          {/* Overview */}
          <BudgetOverview budget={budget} />

          {/* Charts */}
          {summary && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <h3 className="mb-4 text-sm font-medium text-gray-300">Spend by Category</h3>
                <SpendDonut byCategory={typeof summary.by_category === 'object' && summary.by_category !== null && !Array.isArray(summary.by_category) ? Object.fromEntries(Object.entries(summary.by_category).map(([k, v]) => [k, typeof v === 'object' && v !== null && 'total' in v ? (v as { total: number }).total : Number(v)])) : (summary.by_category as Record<string, number>) || {}} />
                <div className="mt-3 flex flex-wrap gap-3">
                  {Object.entries(summary.by_category || {}).filter(([, v]) => (typeof v === 'object' && v !== null && 'total' in v ? (v as { total: number }).total : Number(v)) > 0).map(([cat, val]) => {
                    const total = typeof val === 'object' && val !== null && 'total' in val ? (val as { total: number }).total : Number(val);
                    return (
                      <span key={cat} className="text-xs text-gray-400">
                        {cat.replace('_', ' ')}: <span className="text-gray-200">{formatCurrency(total)}</span>
                      </span>
                    );
                  })}
                </div>
              </Card>
              <Card>
                <h3 className="mb-4 text-sm font-medium text-gray-300">Spend by Agent</h3>
                <AgentBarChart byAgent={typeof summary.by_agent === 'object' && summary.by_agent !== null ? Object.fromEntries(Object.entries(summary.by_agent).map(([k, v]) => [k, typeof v === 'object' && v !== null && 'total' in v ? (v as { total: number }).total : Number(v)])) : (summary.by_agent as Record<string, number>) || {}} />
              </Card>
            </div>
          )}

          {/* Spend over time */}
          {spendOverTime && spendOverTime.series.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300">Spend over time</h3>
              <div className="flex flex-wrap gap-4">
                {spendOverTime.series.slice(-14).map(({ date, amount }) => (
                  <div key={date} className="flex flex-col items-center rounded bg-surface-overlay px-3 py-2">
                    <span className="text-xs text-gray-500">{date}</span>
                    <span className="text-sm font-medium text-gray-200">{formatCurrency(amount)}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-gray-500">Total in range: {formatCurrency(spendOverTime.total)}</p>
            </Card>
          )}

          {/* Spend by initiative */}
          {byInitiative && byInitiative.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300">Spend by initiative</h3>
              <ul className="space-y-2">
                {byInitiative.map((row) => {
                  const initiative = initiatives?.find((i) => i.id === row.initiative_id);
                  return (
                    <li key={row.initiative_id} className="flex items-center justify-between rounded border border-border bg-surface-overlay px-3 py-2">
                      <Link to={`/initiatives/${row.initiative_id}`} className="text-sm font-medium text-accent hover:underline">
                        {initiative?.title ?? row.initiative_id}
                      </Link>
                      <span className="text-sm text-gray-200">{formatCurrency(row.total)} · {row.tokens.toLocaleString()} tokens</span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}

          {/* Recent spend: initiative, initiator, time */}
          {recentSpend && recentSpend.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300">Recent spend</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-gray-500">
                      <th className="pb-2 pr-4">Initiative</th>
                      <th className="pb-2 pr-4">Initiator</th>
                      <th className="pb-2 pr-4">Portfolio</th>
                      <th className="pb-2 pr-4 text-right">Amount</th>
                      <th className="pb-2">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentSpend.map((r) => {
                      const initiative = r.initiative_id
                        ? initiatives?.find((i) => i.id === r.initiative_id)
                        : null;
                      return (
                        <tr key={r.id} className="border-b border-border/50">
                          <td className="py-2 pr-4">
                            {r.initiative_id ? (
                              <Link
                                to={`/initiatives/${r.initiative_id}`}
                                className="text-accent hover:underline"
                              >
                                {initiative?.title ?? r.initiative_id.slice(0, 8)}
                              </Link>
                            ) : (
                              <span className="text-gray-500">—</span>
                            )}
                          </td>
                          <td className="py-2 pr-4 text-gray-300">{r.agent_id}</td>
                          <td className="py-2 pr-4 text-gray-500">—</td>
                          <td className="py-2 pr-4 text-right text-gray-200">
                            {formatCurrency(r.amount)}
                            {r.tokens_used != null ? ` · ${r.tokens_used.toLocaleString()} tok` : ''}
                          </td>
                          <td className="py-2 text-gray-500">{formatDateTime(r.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Alerts */}
          {summary && summary.recent_alerts.length > 0 && (
            <Card>
              <h3 className="mb-4 text-sm font-medium text-gray-300">Alerts</h3>
              <AlertsList alerts={summary.recent_alerts} />
            </Card>
          )}

          {/* Optimization */}
          {optimization && <OptimizationPanel report={optimization} />}
        </div>
      )}

      <CreateBudgetDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
