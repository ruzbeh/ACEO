import { useInitiatives } from '../../api/initiatives';
import { InitiativeCard } from './InitiativeCard';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { Rocket } from 'lucide-react';
import type { InitiativeResponse } from '../../api/types';

interface Props {
  onCopy?: (initiative: InitiativeResponse) => void;
}

export function InitiativeList({ onCopy }: Props) {
  const { data, isLoading } = useInitiatives();

  if (isLoading) return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;

  if (!data?.length) {
    return (
      <EmptyState
        icon={Rocket}
        title="No initiatives yet"
        description="Create your first product initiative to get started."
      />
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((i) => (
        <InitiativeCard key={i.id} initiative={i} onCopy={onCopy} />
      ))}
    </div>
  );
}
