import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { TaskList } from '../features/tasks/TaskList';
import { CreateTaskDialog } from '../features/tasks/CreateTaskDialog';

export function TasksPage() {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tasks</h1>
          <p className="mt-1 text-sm text-gray-400">Engineering tasks executed through the workflow graph</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} className="mr-1.5" />
          New Task
        </Button>
      </div>

      <TaskList />
      <CreateTaskDialog open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
