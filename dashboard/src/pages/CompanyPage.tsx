import { useAgents } from '../api/agents';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import {
  Building2,
  Crown,
  Search,
  Shield,
  Code2,
  TestTube,
  Palette,
  Server,
  BarChart3,
  Wallet,
  ClipboardList,
  FileText,
  Layers,
  ArrowDown,
  GitBranch,
  LayoutDashboard,
  Users,
  Briefcase,
} from 'lucide-react';
import type { AgentResponse } from '../api/types';
import { cn } from '../lib/utils';

// Org chart structure: departments → agents
const ORG_STRUCTURE = {
  executive: {
    label: 'Executive',
    color: 'border-amber-500/40 bg-amber-500/5',
    badgeColor: 'bg-amber-500/20 text-amber-400',
    icon: Crown,
    agents: ['ceo_director'],
    description: 'Portfolio decisions, resource allocation, company direction',
  },
  product: {
    label: 'Product',
    color: 'border-blue-500/40 bg-blue-500/5',
    badgeColor: 'bg-blue-500/20 text-blue-400',
    icon: Search,
    agents: ['product_strategist', 'pm_agent'],
    description: 'Opportunity discovery, product specs, metrics definition',
  },
  management: {
    label: 'Management',
    color: 'border-purple-500/40 bg-purple-500/5',
    badgeColor: 'bg-purple-500/20 text-purple-400',
    icon: ClipboardList,
    agents: ['coo_orchestrator', 'program_manager', 'task_planner'],
    description: 'Workflow orchestration, task planning, ClickUp coordination',
  },
  engineering: {
    label: 'Engineering',
    color: 'border-green-500/40 bg-green-500/5',
    badgeColor: 'bg-green-500/20 text-green-400',
    icon: Code2,
    agents: ['chief_architect', 'backend_engineer', 'frontend_engineer', 'devops_engineer'],
    description: 'System design, implementation, infrastructure',
  },
  quality: {
    label: 'Quality & Security',
    color: 'border-red-500/40 bg-red-500/5',
    badgeColor: 'bg-red-500/20 text-red-400',
    icon: Shield,
    agents: ['qa_engineer', 'security_reviewer'],
    description: 'Code review, testing, OWASP assessment, blast-radius analysis',
  },
  operations: {
    label: 'Operations & Analytics',
    color: 'border-cyan-500/40 bg-cyan-500/5',
    badgeColor: 'bg-cyan-500/20 text-cyan-400',
    icon: BarChart3,
    agents: ['analytics_agent', 'budget_controller', 'agent_evaluator', 'release_manager', 'postmortem_writer'],
    description: 'Metrics, budget governance, evaluation, release, retrospectives',
  },
} as const;

const WORKFLOW_LAYERS = [
  {
    name: 'Portfolio Loop',
    color: 'border-amber-500/30',
    accent: 'text-amber-400',
    nodes: ['opportunity_scan', 'portfolio_review', 'execute_portfolio', 'portfolio_evaluate', 'rebalance'],
    description: 'CEO + Strategist autonomously discover and fund initiatives',
    loop: true,
  },
  {
    name: 'Initiative Workflow',
    color: 'border-blue-500/30',
    accent: 'text-blue-400',
    nodes: ['intake', 'pm_spec', 'architect', 'security_review', 'task_planning', 'execute_tasks', 'evaluate', 'close'],
    description: 'Full product lifecycle: spec → design → security gate → build → ship → measure',
    loop: false,
  },
  {
    name: 'Task Workflow',
    color: 'border-green-500/30',
    accent: 'text-green-400',
    nodes: ['intake', 'route', 'budget_check', 'architect', 'engineer', 'qa', 'publish'],
    description: 'Individual task execution with COO routing and budget gates',
    loop: false,
  },
];

const AGENT_ICONS: Record<string, typeof Crown> = {
  ceo_director: Crown,
  product_strategist: Search,
  pm_agent: FileText,
  coo_orchestrator: LayoutDashboard,
  program_manager: Briefcase,
  task_planner: ClipboardList,
  chief_architect: Layers,
  backend_engineer: Code2,
  frontend_engineer: Palette,
  devops_engineer: Server,
  qa_engineer: TestTube,
  security_reviewer: Shield,
  analytics_agent: BarChart3,
  budget_controller: Wallet,
  agent_evaluator: Users,
  release_manager: GitBranch,
  postmortem_writer: FileText,
};

function AgentNode({ agent, badgeColor }: { agent: AgentResponse; badgeColor: string }) {
  const Icon = AGENT_ICONS[agent.agent_id] ?? Code2;
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-border bg-surface-raised px-3 py-2 transition-colors hover:border-border-subtle">
      <Icon size={14} className="shrink-0 text-gray-400" />
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-gray-200 truncate">{agent.name}</div>
        <div className="text-[10px] text-gray-500">{agent.llm_model.split('/').pop()}</div>
      </div>
      <Badge className={cn('text-[9px] shrink-0', badgeColor)}>{agent.role}</Badge>
    </div>
  );
}

function DepartmentCard({
  dept,
  agents,
}: {
  dept: (typeof ORG_STRUCTURE)[keyof typeof ORG_STRUCTURE];
  agents: AgentResponse[];
}) {
  const Icon = dept.icon;
  return (
    <div className={cn('rounded-xl border p-4', dept.color)}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={16} className="text-gray-300" />
        <h3 className="text-sm font-semibold text-gray-200">{dept.label}</h3>
        <Badge className={cn('text-[9px] ml-auto', dept.badgeColor)}>{agents.length}</Badge>
      </div>
      <p className="text-[10px] text-gray-500 mb-3">{dept.description}</p>
      <div className="space-y-1.5">
        {agents.map((a) => (
          <AgentNode key={a.agent_id} agent={a} badgeColor={dept.badgeColor} />
        ))}
      </div>
    </div>
  );
}

function WorkflowLayer({ layer }: { layer: (typeof WORKFLOW_LAYERS)[number] }) {
  return (
    <div className={cn('rounded-xl border p-4 bg-surface-raised', layer.color)}>
      <div className="flex items-center gap-2 mb-1">
        <h3 className={cn('text-sm font-semibold', layer.accent)}>{layer.name}</h3>
        {layer.loop && (
          <Badge className="bg-amber-500/20 text-amber-400 text-[9px]">loops</Badge>
        )}
      </div>
      <p className="text-[10px] text-gray-500 mb-3">{layer.description}</p>
      <div className="flex flex-wrap items-center gap-1">
        {layer.nodes.map((node, i) => (
          <span key={node} className="flex items-center gap-1">
            <span className="rounded bg-surface-overlay px-2 py-0.5 text-[10px] font-mono text-gray-300">
              {node}
            </span>
            {i < layer.nodes.length - 1 && (
              <span className="text-gray-600 text-[10px]">&rarr;</span>
            )}
          </span>
        ))}
        {layer.loop && (
          <span className="text-gray-600 text-[10px] ml-1">&circlearrowleft;</span>
        )}
      </div>
    </div>
  );
}

function CompanyStats({ agents }: { agents: AgentResponse[] }) {
  const providers = new Set(agents.map((a) => a.llm_provider));
  const roles = new Set(agents.map((a) => a.role));
  const totalTools = new Set(agents.flatMap((a) => a.tools));

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[
        { label: 'Agents', value: agents.length, sub: `${roles.size} roles` },
        { label: 'Departments', value: Object.keys(ORG_STRUCTURE).length, sub: 'org units' },
        { label: 'Workflows', value: 3, sub: 'task + initiative + portfolio' },
        { label: 'Tools', value: totalTools.size, sub: `${providers.size} LLM provider${providers.size > 1 ? 's' : ''}` },
      ].map((s) => (
        <Card key={s.label} className="text-center">
          <div className="text-2xl font-bold text-accent">{s.value}</div>
          <div className="text-xs font-medium text-gray-300">{s.label}</div>
          <div className="text-[10px] text-gray-500">{s.sub}</div>
        </Card>
      ))}
    </div>
  );
}

export function CompanyPage() {
  const { data: agents, isLoading } = useAgents();

  if (isLoading) return <Spinner />;

  const agentMap = new Map((agents ?? []).map((a) => [a.agent_id, a]));

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <Building2 className="h-7 w-7 text-accent" />
          <div>
            <h1 className="text-2xl font-bold">AECO Company Structure</h1>
            <p className="text-sm text-gray-400">
              Autonomous Engineering Company — {agents?.length ?? 0} agents across {Object.keys(ORG_STRUCTURE).length} departments
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <CompanyStats agents={agents ?? []} />

      {/* Workflow Layers */}
      <section>
        <h2 className="mb-3 text-base font-semibold text-gray-200">Workflow Architecture</h2>
        <p className="mb-4 text-xs text-gray-500">
          Three nested orchestration layers. The portfolio loop discovers and funds initiatives.
          Each initiative runs the full product lifecycle. Individual tasks execute with budget gates.
        </p>
        <div className="space-y-3">
          {WORKFLOW_LAYERS.map((layer) => (
            <WorkflowLayer key={layer.name} layer={layer} />
          ))}
        </div>
        <div className="mt-3 flex items-center justify-center gap-2 text-gray-600">
          <ArrowDown size={14} />
          <span className="text-[10px]">Each layer invokes the one below it</span>
          <ArrowDown size={14} />
        </div>
      </section>

      {/* Org Chart */}
      <section>
        <h2 className="mb-3 text-base font-semibold text-gray-200">Organization Chart</h2>
        <p className="mb-4 text-xs text-gray-500">
          17 specialized AI agents organized into departments. Each agent has dedicated tools, permissions, and an LLM configuration tuned for its role.
        </p>

        {/* Executive row */}
        <div className="mb-4 mx-auto max-w-md">
          {(() => {
            const dept = ORG_STRUCTURE.executive;
            const deptAgents = dept.agents
              .map((id) => agentMap.get(id))
              .filter(Boolean) as AgentResponse[];
            return <DepartmentCard dept={dept} agents={deptAgents} />;
          })()}
        </div>

        {/* Reporting line */}
        <div className="flex justify-center mb-4">
          <div className="h-8 w-px bg-border" />
        </div>

        {/* Product + Management row */}
        <div className="grid grid-cols-1 gap-4 mb-4 md:grid-cols-2">
          {(['product', 'management'] as const).map((key) => {
            const dept = ORG_STRUCTURE[key];
            const deptAgents = dept.agents
              .map((id) => agentMap.get(id))
              .filter(Boolean) as AgentResponse[];
            return <DepartmentCard key={key} dept={dept} agents={deptAgents} />;
          })}
        </div>

        {/* Reporting line */}
        <div className="flex justify-center mb-4">
          <div className="h-8 w-px bg-border" />
        </div>

        {/* Engineering + Quality + Operations row */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {(['engineering', 'quality', 'operations'] as const).map((key) => {
            const dept = ORG_STRUCTURE[key];
            const deptAgents = dept.agents
              .map((id) => agentMap.get(id))
              .filter(Boolean) as AgentResponse[];
            return <DepartmentCard key={key} dept={dept} agents={deptAgents} />;
          })}
        </div>
      </section>
    </div>
  );
}
