import { useState, useEffect } from 'react';
import { Dialog } from '../../components/ui/Dialog';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import { Button } from '../../components/ui/Button';
import { useCreateInitiative } from '../../api/initiatives';
import { WORKSPACE_PRESETS } from '../../lib/constants';
import type { InitiativeResponse } from '../../api/types';

interface Props {
  open: boolean;
  onClose: () => void;
  /** When set, pre-fill form from this initiative (copy flow). Cleared by dialog on close. */
  copyFrom?: InitiativeResponse | null;
}

export function CreateInitiativeDialog({ open, onClose, copyFrom }: Props) {
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [workspacePath, setWorkspacePath] = useState('');
  const [workspacePreset, setWorkspacePreset] = useState<string>('');
  const create = useCreateInitiative();

  useEffect(() => {
    if (!open) return;
    if (copyFrom) {
      setTitle(`${copyFrom.title} (copy)`);
      setGoal(copyFrom.goal);
      setHypothesis(copyFrom.hypothesis ?? '');
    } else {
      setTitle('');
      setGoal('');
      setHypothesis('');
    }
    setWorkspacePath('');
    setWorkspacePreset('');
  }, [open, copyFrom]);

  const effectiveWorkspacePath =
    workspacePreset === 'custom' ? workspacePath : (WORKSPACE_PRESETS.find((w) => w.name === workspacePreset)?.path ?? workspacePath);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        title,
        goal,
        hypothesis: hypothesis || undefined,
        workspace_path: effectiveWorkspacePath || undefined,
      },
      {
        onSuccess: () => {
          setTitle('');
          setGoal('');
          setHypothesis('');
          setWorkspacePath('');
          setWorkspacePreset('');
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} title="New Initiative">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Title" id="title" value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="e.g. Improve onboarding conversion" />
        <Textarea label="Goal" id="goal" value={goal} onChange={(e) => setGoal(e.target.value)} required placeholder="What outcome should this achieve?" />
        <Textarea label="Hypothesis" id="hypothesis" value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} placeholder="Optional product hypothesis" />
        <div className="space-y-1">
          <label htmlFor="workspace-preset" className="block text-sm font-medium text-gray-300">Workspace</label>
          <p className="text-xs text-gray-500">Path must exist on the server. Use an absolute path (e.g. /path/to/project) for reliability.</p>
          <select
            id="workspace-preset"
            value={workspacePreset}
            onChange={(e) => setWorkspacePreset(e.target.value)}
            className="w-full rounded-md border border-gray-600 bg-gray-800 px-3 py-2 text-gray-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Select workspace...</option>
            {WORKSPACE_PRESETS.map((w) => (
              <option key={w.name} value={w.name}>{w.name}</option>
            ))}
            <option value="custom">Custom path</option>
          </select>
        </div>
        {workspacePreset === 'custom' && (
          <Input label="Workspace Path" id="workspace" value={workspacePath} onChange={(e) => setWorkspacePath(e.target.value)} placeholder="./workspace/my-project" />
        )}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? 'Creating...' : 'Create Initiative'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
