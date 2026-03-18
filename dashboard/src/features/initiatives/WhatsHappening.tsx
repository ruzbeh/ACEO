import { Loader2 } from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { StatusPipeline } from '../../components/ui/StatusPipeline';
import { INITIATIVE_STATUS_COLORS } from '../../lib/constants';

const PROGRESS_STAGES = ['planning', 'executing', 'in_review', 'measuring', 'closed'] as const;
const PROGRESS_LABELS: Record<string, string> = {
  planning: 'Planning (PM spec → Architect → Task plan)',
  executing: 'Executing tasks',
  in_review: 'In review',
  rolling_out: 'Rolling out',
  measuring: 'Measuring',
  closed: 'Done',
};

interface WhatsHappeningProps {
  status: string;
}

/** Shown when an initiative is in progress so users see current phase and that decisions stream below. */
export function WhatsHappening({ status }: WhatsHappeningProps) {
  const inProgress = status !== 'draft' && status !== 'closed';
  if (!inProgress) return null;

  const currentStage = PROGRESS_STAGES.includes(status as (typeof PROGRESS_STAGES)[number])
    ? status
    : 'planning';
  const colorMap = Object.fromEntries(
    Object.entries(INITIATIVE_STATUS_COLORS).map(([k, v]) => {
      const match = v.match(/text-(\S+)/);
      return [k, match ? match[0] : 'text-gray-400'];
    }),
  );

  return (
    <Card className="border-accent/30 bg-accent/5">
      <div className="flex items-start gap-4">
        <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-gray-200">What&apos;s happening</h3>
          <p className="mt-1 text-xs text-gray-400">
            The workflow is running: product spec → architect → task plan → execution → evaluation.
            New decisions appear in <strong className="text-gray-300">Decision history</strong> below
            as each step completes (updates every few seconds).
          </p>
          <div className="mt-4">
            <StatusPipeline
              stages={[...PROGRESS_STAGES]}
              current={currentStage}
              colorMap={colorMap}
            />
          </div>
          {currentStage !== 'closed' && (
            <p className="mt-2 text-[10px] text-gray-500">
              Current phase: {PROGRESS_LABELS[currentStage] ?? currentStage}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
