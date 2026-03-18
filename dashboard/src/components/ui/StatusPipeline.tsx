import { cn } from '../../lib/utils';

interface StatusPipelineProps {
  stages: string[];
  current: string;
  colorMap: Record<string, string>;
}

export function StatusPipeline({ stages, current, colorMap }: StatusPipelineProps) {
  const currentIdx = stages.indexOf(current);

  return (
    <div className="flex items-center gap-1">
      {stages.map((stage, i) => {
        const isPast = i < currentIdx;
        const isCurrent = i === currentIdx;
        return (
          <div key={stage} className="flex items-center gap-1">
            {i > 0 && (
              <div
                className={cn(
                  'h-0.5 w-6',
                  isPast ? 'bg-emerald-500' : isCurrent ? 'bg-accent' : 'bg-border',
                )}
              />
            )}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'h-3 w-3 rounded-full border-2',
                  isPast
                    ? 'border-emerald-500 bg-emerald-500'
                    : isCurrent
                      ? 'border-accent bg-accent animate-pulse-node'
                      : 'border-border bg-transparent',
                )}
              />
              <span
                className={cn(
                  'mt-1.5 text-[10px] leading-none',
                  isCurrent ? (colorMap[stage] ?? 'text-gray-200') : 'text-gray-500',
                )}
              >
                {stage.replace('_', ' ')}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
