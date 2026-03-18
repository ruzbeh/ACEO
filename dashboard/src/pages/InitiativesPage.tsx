import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { InitiativeList } from '../features/initiatives/InitiativeList';
import { CreateInitiativeDialog } from '../features/initiatives/CreateInitiativeDialog';
import type { InitiativeResponse } from '../api/types';

export function InitiativesPage() {
  const [open, setOpen] = useState(false);
  const [copyFrom, setCopyFrom] = useState<InitiativeResponse | null>(null);

  const handleClose = () => {
    setOpen(false);
    setCopyFrom(null);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Initiatives</h1>
          <p className="mt-1 text-sm text-gray-400">Product hypotheses with measurable outcomes</p>
        </div>
        <Button onClick={() => { setCopyFrom(null); setOpen(true); }}>
          <Plus size={16} className="mr-1.5" />
          New Initiative
        </Button>
      </div>

      <InitiativeList
        onCopy={(initiative) => {
          setCopyFrom(initiative);
          setOpen(true);
        }}
      />
      <CreateInitiativeDialog
        open={open}
        onClose={handleClose}
        copyFrom={copyFrom}
      />
    </div>
  );
}
