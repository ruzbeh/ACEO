import { Loader2 } from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { LiveStatusBar } from './LiveStatusBar';
import { useInitiativeLiveStatus } from '../../api/initiatives';

const PROGRESS_LABELS: Record<string, string> = {
  intake: 'Classifying initiative',
  pm_spec: 'PM writing PRD and metrics',
  architect: 'Chief Architect — technical design',
  security_review: 'Security review',
  task_planning: 'Task Planner building task graph',
  execute_tasks: 'Executing tasks',
  evaluate: 'Evaluating results',
  acceptance_test: 'Acceptance testing',
  close: 'Closing initiative',
};

interface WhatsHappeningProps {
  status: string;
  initiativeId?: string;
}

/** Shown when an initiative is in progress so users see current phase and that decisions stream below. */
export function WhatsHappening({ status, initiativeId }: WhatsHappeningProps) {
  const inProgress = status !== 'draft' && status !== 'closed';
  const { data: live } = useInitiativeLiveStatus(
    inProgress ? initiativeId : undefined,
    inProgress ? status : undefined,
  );

  if (!inProgress) return null;

  const currentNode = live?.progress.current_node;
  const phaseLabel = currentNode ? (PROGRESS_LABELS[currentNode] ?? currentNode) : null;

  return (
    <Card className="border-accent/30 bg-accent/5">
      <div className="flex items-start gap-4">
        <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-gray-200">What&apos;s happening</h3>
          <p className="mt-1 text-xs text-gray-400">
            The workflow is running. Watch{' '}
            <strong className="text-gray-300">Live trace</strong> below for agent/tool logs in real
            time. <strong className="text-gray-300">Decision history</strong> records ledger entries
            as each step completes.
          </p>

          {/* Compact live status bar with phase dots */}
          {initiativeId && (
            <div className="mt-3">
              <LiveStatusBar initiativeId={initiativeId} status={status} compact />
            </div>
          )}

          {phaseLabel && (
            <p className="mt-2 text-[10px] text-gray-500">
              Current phase: {phaseLabel}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
