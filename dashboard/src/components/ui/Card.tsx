import { cn } from '../../lib/utils';

interface CardProps {
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
}

export function Card({ className, children, onClick }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface-raised p-5',
        onClick && 'cursor-pointer hover:border-border-subtle hover:bg-surface-overlay transition-colors',
        className,
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
