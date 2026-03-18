import { cn } from '../../lib/utils';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'sm' | 'md';
}

const variants: Record<Variant, string> = {
  primary: 'bg-accent hover:bg-accent-hover text-white',
  secondary: 'bg-surface-overlay hover:bg-border-subtle text-gray-200 border border-border',
  ghost: 'hover:bg-surface-overlay text-gray-300',
  danger: 'bg-red-500/20 hover:bg-red-500/30 text-red-400',
};

export function Button({ variant = 'primary', size = 'md', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2 text-sm',
        className,
      )}
      {...props}
    />
  );
}
