export const INITIATIVE_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-500/20 text-gray-400',
  planning: 'bg-blue-500/20 text-blue-400',
  executing: 'bg-yellow-500/20 text-yellow-400',
  in_review: 'bg-purple-500/20 text-purple-400',
  rolling_out: 'bg-cyan-500/20 text-cyan-400',
  measuring: 'bg-orange-500/20 text-orange-400',
  closed: 'bg-gray-500/20 text-gray-500',
};

export const INITIATIVE_STATUSES = [
  'draft', 'planning', 'executing', 'in_review', 'rolling_out', 'measuring', 'closed',
] as const;

export const VERDICT_COLORS: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-400',
  scale: 'bg-emerald-500/20 text-emerald-400',
  iterate: 'bg-yellow-500/20 text-yellow-400',
  kill: 'bg-red-500/20 text-red-400',
};

export const TASK_STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-500/20 text-gray-400',
  in_progress: 'bg-blue-500/20 text-blue-400',
  architect_design: 'bg-purple-500/20 text-purple-400',
  engineering: 'bg-yellow-500/20 text-yellow-400',
  qa_review: 'bg-orange-500/20 text-orange-400',
  done: 'bg-emerald-500/20 text-emerald-400',
  blocked: 'bg-red-500/20 text-red-400',
};

export const WORKFLOW_STATUS_COLORS: Record<string, string> = {
  running: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-emerald-500/20 text-emerald-400',
  failed: 'bg-red-500/20 text-red-400',
};

export const APPROVAL_COLORS: Record<string, string> = {
  auto_approved: 'bg-emerald-500/20 text-emerald-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  denied: 'bg-red-500/20 text-red-400',
  pending: 'bg-yellow-500/20 text-yellow-400',
  escalated: 'bg-orange-500/20 text-orange-400',
};

export const CATEGORY_COLORS: Record<string, string> = {
  llm_tokens: '#6366f1',
  compute: '#a855f7',
  api_calls: '#06b6d4',
  storage: '#22c55e',
  tooling: '#f97316',
  other: '#6b7280',
};

/** Preset workspaces for initiative creation (name → path). */
export const WORKSPACE_PRESETS: { name: string; path: string }[] = [
  { name: 'Agentic Company', path: './workspace' },
  { name: 'Headshot AI', path: '/Users/ruzbeh.i/IdeaProjects/SIdeProjects/headshot-studio' },
];
