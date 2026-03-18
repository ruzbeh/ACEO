import { useState } from 'react';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import { Button } from '../../components/ui/Button';
import { useCreateTask } from '../../api/tasks';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateTaskDialog({ open, onClose }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const create = useCreateTask();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      { title, description: description || undefined },
      {
        onSuccess: () => {
          setTitle('');
          setDescription('');
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title="New Task">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Title" id="task-title" value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="e.g. Add user authentication" />
        <Textarea label="Description" id="task-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the engineering task" />
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Creating...' : 'Create Task'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
