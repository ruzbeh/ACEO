import { useState } from 'react';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';
import { useCreateBudget } from '../../api/budget';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateBudgetDialog({ open, onClose }: Props) {
  const [name, setName] = useState('');
  const [total, setTotal] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const create = useCreateBudget();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        name,
        total_budget: parseFloat(total),
        period_start: new Date(start).toISOString(),
        period_end: new Date(end).toISOString(),
      },
      {
        onSuccess: () => {
          setName('');
          setTotal('');
          setStart('');
          setEnd('');
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title="New Budget Period">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Name" id="budget-name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Q1 2026" />
        <Input label="Total Budget ($)" id="budget-total" type="number" step="0.01" value={total} onChange={(e) => setTotal(e.target.value)} required placeholder="1000.00" />
        <Input label="Period Start" id="budget-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} required />
        <Input label="Period End" id="budget-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} required />
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Creating...' : 'Create Budget'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
