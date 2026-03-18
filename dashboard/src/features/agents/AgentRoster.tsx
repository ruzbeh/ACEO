import { useAgents } from '../../api/agents';
import { AgentCard } from './AgentCard';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { Bot } from 'lucide-react';

export function AgentRoster() {
  const { data, isLoading } = useAgents();

  if (isLoading) return <div className="flex justify-center py-16"><Spinner className="h-8 w-8" /></div>;

  if (!data?.length) {
    return <EmptyState icon={Bot} title="No agents loaded" description="Agent definitions were not found." />;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((a) => (
        <AgentCard key={a.agent_id} agent={a} />
      ))}
    </div>
  );
}
