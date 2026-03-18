import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import type { AgentResponse } from '../../api/types';

export function AgentCard({ agent }: { agent: AgentResponse }) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-100">{agent.name}</h3>
          <p className="mt-0.5 text-xs text-gray-400">{agent.role}</p>
        </div>
        <Badge className="bg-surface-overlay text-gray-400">{agent.llm_provider}</Badge>
      </div>

      <div className="mt-3">
        <span className="text-[10px] font-medium uppercase text-gray-500">Model</span>
        <p className="text-xs text-gray-300">{agent.llm_model}</p>
      </div>

      {agent.tools.length > 0 && (
        <div className="mt-3">
          <span className="text-[10px] font-medium uppercase text-gray-500">Tools</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {agent.tools.map((t) => (
              <span key={t} className="rounded bg-surface-overlay px-1.5 py-0.5 text-[10px] text-gray-400">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
