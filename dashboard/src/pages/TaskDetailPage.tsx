import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, AlertCircle, Loader2 } from 'lucide-react';
import { useTask } from '../api/tasks';
import { useWorkflow } from '../api/workflows';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { StatusPipeline } from '../components/ui/StatusPipeline';
import { WorkflowGraph, WORKFLOW_NODE_LABELS } from '../features/workflows/WorkflowGraph';
import { TASK_STATUS_COLORS, WORKFLOW_STATUS_COLORS } from '../lib/constants';
import { formatDateTime } from '../lib/utils';

const TASK_STAGES = ['todo', 'in_progress', 'architect_design', 'engineering', 'qa_review', 'done'] as const;

export function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: task, isLoading } = useTask(id!);
  const { data: workflow } = useWorkflow(task?.workflow_run_id ?? null);

  if (isLoading || !task) {
    return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/tasks" className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-200 mb-4">
          <ArrowLeft size={14} /> Back to tasks
        </Link>
        <h1 className="text-2xl font-bold">{task.title}</h1>
        {task.description && <p className="mt-1 text-sm text-gray-400">{task.description}</p>}
      </div>

      {/* Pipeline */}
      <Card>
        <h3 className="mb-4 text-sm font-medium text-gray-300">Task Lifecycle</h3>
        <StatusPipeline
          stages={[...TASK_STAGES]}
          current={task.status}
          colorMap={Object.fromEntries(
            Object.entries(TASK_STATUS_COLORS).map(([k, v]) => {
              const match = v.match(/text-(\S+)/);
              return [k, match ? match[0] : 'text-gray-400'];
            }),
          )}
        />
      </Card>

      {/* Meta */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Status</span>
          <div className="mt-2">
            <Badge className={TASK_STATUS_COLORS[task.status] ?? ''}>{task.status.replace('_', ' ')}</Badge>
          </div>
        </Card>
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Assigned Agent</span>
          <p className="mt-2 text-sm text-gray-200">{task.assigned_agent_id ?? 'Unassigned'}</p>
        </Card>
        <Card>
          <span className="text-xs font-medium uppercase text-gray-500">Updated</span>
          <p className="mt-2 text-sm text-gray-200">{formatDateTime(task.updated_at)}</p>
        </Card>
      </div>

      {/* Workflow Execution */}
      {workflow && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-300">Workflow Execution</h3>
            <Badge className={WORKFLOW_STATUS_COLORS[workflow.status] ?? ''}>
              {workflow.status}
            </Badge>
          </div>

          {/* Currently running: visible without looking at logs */}
          {workflow.status === 'running' && (
            <div className="mb-4 flex items-center gap-3 rounded-lg border border-accent/30 bg-accent/10 px-4 py-3">
              <Loader2 className="h-5 w-5 shrink-0 animate-spin text-accent" aria-hidden />
              <div>
                <span className="text-sm font-medium text-gray-200">Currently running: </span>
                <span className="text-sm text-accent">
                  {WORKFLOW_NODE_LABELS[workflow.current_node] ?? workflow.current_node}
                </span>
              </div>
            </div>
          )}

          {/* Error: prominent so you see it in the UI, not only in logs */}
          {workflow.status === 'failed' && workflow.error && (
            <div className="mb-4 flex gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-400" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-red-300">Workflow failed</p>
                <p className="mt-1 text-sm text-red-200/90">{workflow.error}</p>
              </div>
            </div>
          )}

          <WorkflowGraph currentNode={workflow.current_node} status={workflow.status} />
          <div className="mt-4 flex items-center gap-4 text-xs text-gray-500">
            <span>Started: {formatDateTime(workflow.started_at)}</span>
            {workflow.completed_at && <span>Completed: {formatDateTime(workflow.completed_at)}</span>}
          </div>
        </Card>
      )}
    </div>
  );
}
