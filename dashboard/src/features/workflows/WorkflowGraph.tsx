import { cn } from '../../lib/utils';

interface WorkflowGraphProps {
  currentNode: string;
  status: string;
}

const NODES = [
  { id: 'intake', label: 'Intake', x: 50, y: 80 },
  { id: 'route', label: 'Route', x: 180, y: 80 },
  { id: 'budget_check', label: 'Budget Check', x: 320, y: 80 },
  { id: 'architect', label: 'Architect', x: 460, y: 30 },
  { id: 'engineer', label: 'Engineer', x: 460, y: 80 },
  { id: 'frontend', label: 'Frontend', x: 460, y: 130 },
  { id: 'qa_review', label: 'QA Review', x: 600, y: 80 },
  { id: 'publish', label: 'Publish', x: 730, y: 80 },
] as const;

/** Human-readable label for workflow node id (for "Currently running: …" etc.). */
export const WORKFLOW_NODE_LABELS: Record<string, string> = {
  intake: 'Intake',
  route: 'Route',
  budget_check: 'Budget Check',
  architect: 'Architect',
  engineer: 'Engineer',
  frontend: 'Frontend',
  qa_review: 'QA Review',
  publish: 'Publish',
  starting: 'Starting…',
  done: 'Done',
  failed: 'Failed',
};

const EDGES: [string, string][] = [
  ['intake', 'route'],
  ['route', 'budget_check'],
  ['budget_check', 'architect'],
  ['budget_check', 'engineer'],
  ['budget_check', 'frontend'],
  ['architect', 'qa_review'],
  ['engineer', 'qa_review'],
  ['frontend', 'qa_review'],
  ['qa_review', 'publish'],
];

function nodePos(id: string) {
  return NODES.find((n) => n.id === id) ?? { x: 0, y: 0 };
}

export function WorkflowGraph({ currentNode, status }: WorkflowGraphProps) {
  const currentIdx = NODES.findIndex((n) => n.id === currentNode);

  return (
    <svg viewBox="0 0 800 160" className="w-full max-w-3xl" role="img" aria-label="Workflow graph">
      {/* Edges */}
      {EDGES.map(([from, to]) => {
        const a = nodePos(from);
        const b = nodePos(to);
        const fromIdx = NODES.findIndex((n) => n.id === from);
        const isPast = fromIdx < currentIdx;
        return (
          <line
            key={`${from}-${to}`}
            x1={a.x + 45}
            y1={a.y + 15}
            x2={b.x}
            y2={b.y + 15}
            stroke={isPast ? '#22c55e' : '#2e3148'}
            strokeWidth={2}
          />
        );
      })}

      {/* Nodes */}
      {NODES.map((node, i) => {
        const isCurrent = node.id === currentNode;
        const isPast = i < currentIdx;
        const isDone = status === 'completed';

        return (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={90}
              height={30}
              rx={8}
              className={cn(
                'transition-all',
                isCurrent && !isDone
                  ? 'fill-accent/30 stroke-accent animate-pulse-node'
                  : isPast || isDone
                    ? 'fill-emerald-500/20 stroke-emerald-500'
                    : 'fill-surface-overlay stroke-border',
              )}
              strokeWidth={1.5}
            />
            <text
              x={node.x + 45}
              y={node.y + 19}
              textAnchor="middle"
              className={cn(
                'text-[10px] font-medium',
                isCurrent && !isDone
                  ? 'fill-accent'
                  : isPast || isDone
                    ? 'fill-emerald-400'
                    : 'fill-gray-400',
              )}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
