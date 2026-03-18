import { useState } from 'react';
import { Plus, Wallet } from 'lucide-react';
import { useActiveBudget, useBudgetSummary, useOptimization } from '../api/budget';
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

export function BudgetPage() {
  const [open, setOpen] = useState(false);
  const { data: budget, isLoading } = useActiveBudget();
  const { data: summary } = useBudgetSummary(budget?.id);
  const { data: optimization } = useOptimization(budget?.id);

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
          description="Create a budget period to start tracking spend."
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
                <SpendDonut byCategory={summary.by_category} />
                <div className="mt-3 flex flex-wrap gap-3">
                  {Object.entries(summary.by_category).filter(([,v]) => v > 0).map(([cat, val]) => (
                    <span key={cat} className="text-xs text-gray-400">
                      {cat.replace('_', ' ')}: <span className="text-gray-200">${val.toFixed(2)}</span>
                    </span>
                  ))}
                </div>
              </Card>
              <Card>
                <h3 className="mb-4 text-sm font-medium text-gray-300">Spend by Agent</h3>
                <AgentBarChart byAgent={summary.by_agent} />
              </Card>
            </div>
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
