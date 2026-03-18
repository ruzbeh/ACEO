import { cn } from '../../lib/utils';

interface UtilizationBarProps {
  percent: number;
  className?: string;
}

export function UtilizationBar({ percent, className }: UtilizationBarProps) {
  const color =
    percent >= 90 ? 'bg-red-500' : percent >= 70 ? 'bg-yellow-500' : 'bg-accent';

  return (
    <div className={cn('h-2.5 w-full rounded-full bg-surface-overlay', className)}>
      <div
        className={cn('h-full rounded-full transition-all', color)}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}
