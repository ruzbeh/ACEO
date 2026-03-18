import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { TASK_STATUS_COLORS } from '../../lib/constants';
import { formatDate } from '../../lib/utils';
import type { TaskResponse } from '../../api/types';

export function TaskCard({ task }: { task: TaskResponse }) {
  const nav = useNavigate();

  return (
    <Card onClick={() => nav(`/tasks/${task.id}`)}>
      <h3 className="truncate text-sm font-semibold text-gray-100">{task.title}</h3>
      {task.description && (
        <p className="mt-1 line-clamp-2 text-xs text-gray-400">{task.description}</p>
      )}
      <div className="mt-3 flex items-center gap-2">
        <Badge className={TASK_STATUS_COLORS[task.status] ?? ''}>
          {task.status.replace('_', ' ')}
        </Badge>
        {task.assigned_agent_id && (
          <span className="text-xs text-gray-500">{task.assigned_agent_id}</span>
        )}
        <span className="ml-auto text-xs text-gray-600">{formatDate(task.created_at)}</span>
      </div>
    </Card>
  );
}
