import { useState, useRef, useCallback } from 'react';
import { Camera, X, Upload } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface ScreenshotUploadData {
  file: File;
  feedback: string;
}

interface ScreenshotUploadProps {
  onUpload: (data: ScreenshotUploadData) => void;
  label?: string;
  placeholder?: string;
  compact?: boolean;
  className?: string;
}

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

export function ScreenshotUpload({
  onUpload,
  label = 'Screenshot',
  placeholder = 'Describe what you see or what should change…',
  compact = false,
  className,
}: ScreenshotUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [feedback, setFeedback] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    if (!ACCEPTED_TYPES.includes(f.type)) return;
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreview(url);
  }, []);

  /** Clipboard paste (e.g. macOS screenshot → Cmd+V, Windows Snipping Tool). */
  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items?.length) return;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (!item || item.kind !== 'file' || !ACCEPTED_TYPES.includes(item.type)) continue;
        const blob = item.getAsFile();
        if (!blob) continue;
        e.preventDefault();
        const ext =
          blob.type === 'image/png' ? 'png' : blob.type === 'image/jpeg' ? 'jpg' : 'webp';
        const pasted = new File([blob], `paste-${Date.now()}.${ext}`, { type: blob.type });
        handleFile(pasted);
        return;
      }
    },
    [handleFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleRemove = () => {
    setFile(null);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setFeedback('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleSubmit = () => {
    if (!file) return;
    onUpload({ file, feedback });
    handleRemove();
  };

  return (
    <div className={cn('space-y-2', className)}>
      {label && (
        <label className="block text-sm font-medium text-gray-300">{label}</label>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        className="hidden"
        onChange={handleInputChange}
      />

      {!preview ? (
        <div
          role="button"
          tabIndex={0}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onPaste={handlePaste}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click();
          }}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors',
            dragOver
              ? 'border-accent bg-accent/10'
              : 'border-border hover:border-border-subtle hover:bg-surface-overlay',
            compact ? 'gap-1 px-3 py-4' : 'gap-2 px-4 py-8',
          )}
        >
          <Upload size={compact ? 16 : 24} className="text-gray-500" />
          <span className={cn('text-gray-500', compact ? 'text-xs' : 'text-sm')}>
            Drop, click to upload, or paste image
          </span>
          <span className="text-[10px] text-gray-600">PNG, JPG, WebP · focus here and ⌘V / Ctrl+V</span>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="relative inline-block">
            <img
              src={preview}
              alt="Screenshot preview"
              className={cn(
                'rounded-lg border border-border object-cover',
                compact ? 'max-h-28' : 'max-h-48',
              )}
            />
            <button
              type="button"
              onClick={handleRemove}
              className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white hover:bg-red-400 transition-colors"
              title="Remove screenshot"
            >
              <X size={12} />
            </button>
          </div>

          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            onPaste={handlePaste}
            placeholder={placeholder}
            rows={compact ? 2 : 3}
            className={cn(
              'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-accent focus:ring-1 focus:ring-accent',
              compact ? 'min-h-[48px]' : 'min-h-[64px]',
            )}
          />

          <button
            type="button"
            onClick={handleSubmit}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:pointer-events-none"
            disabled={!file}
          >
            <Camera size={14} />
            Attach
          </button>
        </div>
      )}
    </div>
  );
}
