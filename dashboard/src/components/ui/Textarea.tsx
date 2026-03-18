import { cn } from '../../lib/utils';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, className, id, ...props }: TextareaProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-gray-300">
          {label}
        </label>
      )}
      <textarea
        id={id}
        className={cn(
          'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-accent focus:ring-1 focus:ring-accent min-h-[80px]',
          className,
        )}
        {...props}
      />
    </div>
  );
}
