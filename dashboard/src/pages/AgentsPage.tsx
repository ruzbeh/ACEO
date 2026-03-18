import { AgentRoster } from '../features/agents/AgentRoster';
import { ActivityFeed } from '../features/agents/ActivityFeed';

export function AgentsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Agents</h1>
        <p className="mt-1 text-sm text-gray-400">The 14-agent engineering organization</p>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-200">Roster</h2>
        <AgentRoster />
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-200">Recent Activity</h2>
        <ActivityFeed />
      </section>
    </div>
  );
}
