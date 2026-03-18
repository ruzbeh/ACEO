// ── Tasks ──
export interface TaskResponse {
  id: string;
  clickup_task_id: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  assigned_agent_id: string | null;
  workflow_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export type TaskStatus =
  | 'todo'
  | 'in_progress'
  | 'architect_design'
  | 'engineering'
  | 'qa_review'
  | 'done'
  | 'blocked';

export interface CreateTaskRequest {
  title: string;
  description?: string;
}

// ── Workflows ──
export interface WorkflowResponse {
  id: string;
  task_id: string;
  status: WorkflowStatus;
  current_node: string;
  started_at: string;
  completed_at: string | null;
  error?: string | null;
}

export type WorkflowStatus = 'running' | 'completed' | 'failed';

export interface RunWorkflowRequest {
  task_id: string;
  workspace_path?: string;
  project_name?: string;
}

// ── Initiatives ──
export interface InitiativeResponse {
  id: string;
  title: string;
  goal: string;
  hypothesis: string | null;
  status: InitiativeStatus;
  verdict: InitiativeVerdict;
  north_star_metric: string | null;
  created_at: string;
}

export type InitiativeStatus =
  | 'draft'
  | 'planning'
  | 'executing'
  | 'in_review'
  | 'rolling_out'
  | 'measuring'
  | 'closed';

export type InitiativeVerdict = 'pending' | 'scale' | 'iterate' | 'kill';

export interface CreateInitiativeRequest {
  title: string;
  goal: string;
  hypothesis?: string;
  workspace_path?: string;
}

export interface RunInitiativeRequest {
  initiative_id: string;
  workspace_path?: string;
}

// ── Decisions ──
export interface DecisionRecord {
  id: string;
  initiative_id: string | null;
  task_id: string | null;
  workflow_run_id: string | null;
  category: string;
  agent_id: string;
  decision: string;
  reasoning: string;
  assumptions: string[];
  evidence_refs: string[];
  risks: string[];
  confidence: number;
  alternatives_considered: string[];
  outcome: string | null;
  assumptions_validated: boolean | null;
  lessons_learned: string | null;
  created_at: string;
}

export interface DecisionsResponse {
  initiative_id: string;
  decisions: DecisionRecord[];
}

// ── Budget ──
export interface BudgetResponse {
  id: string;
  name: string;
  scope: string;
  scope_id: string | null;
  total_budget: number;
  spent: number;
  reserved: number;
  remaining: number;
  utilization_percent: number;
  period_start: string;
  period_end: string;
  is_active: boolean;
}

export interface CreateBudgetRequest {
  name: string;
  total_budget: number;
  period_start: string;
  period_end: string;
  scope?: string;
  scope_id?: string;
}

export interface BudgetSummary {
  budget_id: string;
  budget_name: string;
  scope: string;
  total_budget: number;
  spent: number;
  reserved: number;
  remaining: number;
  utilization_percent: number;
  period_start: string;
  period_end: string;
  by_category: Record<string, number>;
  by_agent: Record<string, number>;
  recent_alerts: BudgetAlert[];
}

export interface BudgetAlert {
  id: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  agent_id: string | null;
  acknowledged: boolean;
  created_at: string;
}

export interface SpendRequest {
  agent_id: string;
  amount: number;
  category?: string;
  description?: string;
  workflow_run_id?: string;
  task_id?: string;
  tokens_used?: number;
  llm_model?: string;
}

export interface SpendDecision {
  status: string;
  reasoning: string;
  amount: number;
  remaining_budget: number;
  utilization_percent: number;
  warnings: string[];
  optimization_hints: string[];
}

export interface InitiativeSpend {
  initiative_id: string;
  total_cost: number;
  total_tokens: number;
  by_agent: Record<string, { total: number; tokens: number; count: number }>;
  records: Array<{
    id: string;
    agent_id: string;
    amount: number;
    tokens_used: number | null;
    created_at: string;
  }>;
}

export interface SpendOverTimeResponse {
  budget_id: string;
  group_by: string;
  series: Array<{ date: string; amount: number }>;
  total: number;
}

export interface SpendByInitiativeItem {
  initiative_id: string;
  total: number;
  tokens: number;
  count: number;
}

export interface OptimizationReport {
  budget_id: string;
  budget_name: string;
  spent: number;
  remaining: number;
  utilization_percent: number;
  daily_burn_rate: number;
  projected_total_spend: number;
  projected_over_budget: boolean;
  top_spenders: Array<{ agent_id: string; total: number }>;
  optimization_hints: string[];
  recommendation: string;
}

export interface WorkflowCost {
  workflow_run_id: string;
  total_cost: number;
  total_tokens: number;
  by_agent: Record<string, number>;
}

// ── Portfolio ──
export interface PortfolioRunResponse {
  portfolio_id: string;
  status: string;
  message: string;
}

export interface OpportunityItem {
  title: string;
  description: string;
  estimated_impact: string;
}

export interface DecisionItem {
  agent: string;
  phase: string;
  reasoning: string;
  funded: string[];
  killed: string[];
  scaled: string[];
}

export interface ExecutionResultItem {
  title: string;
  initiative_id: string;
  action: string;
  verdict: string;
  budget_spent: number;
  tasks_executed: number;
  // Rich initiative internals
  prd?: Record<string, unknown> | null;
  design_document?: string | null;
  security_review?: Record<string, unknown> | null;
  task_graph?: Record<string, unknown>[];
  execution_details?: Record<string, unknown>[];
  evaluation?: Record<string, unknown> | null;
  decisions?: Record<string, unknown>[];
  north_star_metric?: string | null;
  success_threshold?: string | null;
}

export interface PortfolioMessage {
  sender?: string;
  type?: string;
  content?: unknown;
  timestamp?: string;
  // Legacy compat
  role?: string;
  agent?: string;
  [key: string]: unknown;
}

export interface PortfolioStatusResponse {
  portfolio_id: string;
  current_phase: string;
  cycle_count: number;
  max_cycles: number;
  budget_spent: number;
  budget_remaining: number;
  total_budget: number;
  opportunities_found: number;
  initiatives_funded: number;
  initiatives_killed: number;
  execution_results: number;
  status: 'running' | 'completed' | 'failed';
  company_goals: string[];
  opportunities: OpportunityItem[];
  portfolio_decisions: DecisionItem[];
  results: ExecutionResultItem[];
  errors: string[];
  messages: PortfolioMessage[];
}

export interface PortfolioListItem {
  portfolio_id: string;
  status: string;
  current_phase: string;
  started_at?: string | null;
  completed_at?: string | null;
  cycle_count?: number;
  max_cycles?: number;
}

export interface RunPortfolioRequest {
  company_goals: string[];
  max_cycles?: number;
  total_budget?: number;
  workspace_path?: string;
}

// ── Approval Queue ──
export interface ApprovalRequest {
  id: string;
  portfolio_id: string | null;
  initiative_title: string;
  action: 'fund' | 'kill' | 'scale';
  reasoning: string;
  allocated_budget: number;
  blast_radius: string;
  requested_by: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

// ── Agents ──
export interface AgentResponse {
  agent_id: string;
  name: string;
  role: string;
  tools: string[];
  llm_provider: string;
  llm_model: string;
}

// ── Projects ──
export interface ProjectResponse {
  id: string | null;
  name: string;
  workspace_path: string;
  language: string | null;
  framework: string | null;
  structure: Record<string, unknown>;
  key_files: string[];
  existing_patterns: string;
}

// ── Health ──
export interface HealthResponse {
  status: string;
  version: string;
}
