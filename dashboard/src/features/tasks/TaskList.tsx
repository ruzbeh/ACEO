import { useTasks } from '../../api/tasks';
import { TaskCard } from './TaskCard';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ListChecks } from 'lucide-react';

export function TaskList() {
  const { data, isLoading } = useTasks();

  if (isLoading) return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;

  if (!data?.length) {
    return (
      <EmptyState
        icon={ListChecks}
        title="No tasks yet"
        description="Create a task to trigger the engineering workflow."
      />
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((t) => (
        <TaskCard key={t.id} task={t} />
      ))}
    </div>
  );
}
