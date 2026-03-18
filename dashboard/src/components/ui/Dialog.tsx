import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Dialog({ open, onClose, title, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="fixed inset-0 z-50 m-auto w-full max-w-lg rounded-xl border border-border bg-surface-raised p-0 text-gray-100 backdrop:bg-black/60"
    >
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
          <X size={18} />
        </button>
      </div>
      <div className="px-6 py-5">{children}</div>
    </dialog>
  );
}
