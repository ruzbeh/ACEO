import { useState } from 'react';
import { Upload, X, Loader2, Sparkles, Wand2, Mic } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { useCreateReel, useUploadImage } from '../../api/reels';
import { cn } from '../../lib/utils';

interface Props {
  onClose: () => void;
  onCreated?: (reelId: string) => void;
}

interface UploadedImage {
  id: string;
  path: string;
  url: string;
  filename: string;
}

export function NewReelForm({ onClose, onCreated }: Props) {
  const uploadImage = useUploadImage();
  const createReel = useCreateReel();

  const [title, setTitle] = useState('');
  const [before, setBefore] = useState<UploadedImage | null>(null);
  const [afters, setAfters] = useState<UploadedImage[]>([]);
  const [headline, setHeadline] = useState('8 Pro Headshots in 2 Minutes');
  const [subheadline, setSubheadline] = useState('$19 · Money-back guarantee');
  const [ctaText, setCtaText] = useState('Try free at headshot-generators.com');
  const [brand, setBrand] = useState('headshot-generators.com');
  const [brief, setBrief] = useState('');
  const [autoScript, setAutoScript] = useState(false);
  const [useRunway, setUseRunway] = useState(false);
  const [useVoiceover, setUseVoiceover] = useState(false);
  const [voiceoverText, setVoiceoverText] = useState(
    "Your LinkedIn photo is the first thing recruiters see. Upload a selfie to Headshot AI and get 8 studio-quality headshots in two minutes. All for just nineteen dollars. Try it free — money-back guarantee.",
  );
  const [voiceoverVoice, setVoiceoverVoice] = useState('narrator');
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File): Promise<UploadedImage | null> => {
    try {
      const res = await uploadImage.mutateAsync(file);
      return { ...res, filename: file.name };
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  };

  const handleBefore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const img = await upload(file);
    if (img) setBefore(img);
  };

  const handleAfters = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const uploaded: UploadedImage[] = [];
    for (const f of files.slice(0, 6 - afters.length)) {
      const img = await upload(f);
      if (img) uploaded.push(img);
    }
    setAfters((prev) => [...prev, ...uploaded].slice(0, 6));
  };

  const submit = async () => {
    setError(null);
    if (!before) {
      setError('Upload a "before" selfie first.');
      return;
    }
    if (afters.length < 3) {
      setError('Add at least 3 after-headshots (3–6 supported).');
      return;
    }
    try {
      const reel = await createReel.mutateAsync({
        title: title || undefined,
        before_image_path: before.path,
        after_image_paths: afters.map((a) => a.path),
        headline,
        subheadline,
        cta_text: ctaText,
        brand,
        brief: brief || undefined,
        auto_script: autoScript && !!brief,
        use_runway: useRunway,
        use_voiceover: useVoiceover,
        voiceover_text: useVoiceover ? voiceoverText : undefined,
        voiceover_voice: useVoiceover ? voiceoverVoice : undefined,
      });
      onCreated?.(reel.id);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const busy = uploadImage.isPending || createReel.isPending;

  return (
    <div className="space-y-5">
      <Field label="Title (optional)">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Headshot AI V2 launch"
          className={inputCls}
        />
      </Field>

      <ImageSlot
        label='"Before" selfie'
        hint="One clear selfie — the source for your AI headshots."
        image={before}
        onChange={handleBefore}
        onRemove={() => setBefore(null)}
        busy={busy}
      />

      <div>
        <div className="mb-2 flex items-baseline justify-between">
          <div className="text-sm font-semibold text-gray-200">
            "After" headshots <span className="text-gray-500 font-normal">(3–6)</span>
          </div>
          <div className="text-xs text-gray-500">{afters.length} / 6</div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {afters.map((a, i) => (
            <div key={a.id} className="relative overflow-hidden rounded-lg border border-border bg-surface-overlay">
              <img src={a.url} alt={a.filename} className="aspect-[3/4] w-full object-cover" />
              <button
                onClick={() => setAfters((p) => p.filter((_, idx) => idx !== i))}
                className="absolute right-1 top-1 rounded bg-black/70 p-1 text-gray-300 hover:text-white"
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {afters.length < 6 && (
            <label
              className={cn(
                'flex aspect-[3/4] cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-surface-overlay text-gray-500 hover:border-accent hover:text-accent',
                busy && 'pointer-events-none opacity-50',
              )}
            >
              <Upload size={18} />
              <span className="text-xs">Add</span>
              <input type="file" accept="image/*" multiple className="hidden" onChange={handleAfters} />
            </label>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Headline">
          <input value={headline} onChange={(e) => setHeadline(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Subheadline">
          <input value={subheadline} onChange={(e) => setSubheadline(e.target.value)} className={inputCls} />
        </Field>
        <Field label="CTA">
          <input value={ctaText} onChange={(e) => setCtaText(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Brand">
          <input value={brand} onChange={(e) => setBrand(e.target.value)} className={inputCls} />
        </Field>
      </div>

      <Field label="Brief (optional — describe the angle you want)">
        <textarea
          rows={2}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="e.g. Target US professionals, 35-55, emphasize time savings vs studio visit."
          className={cn(inputCls, 'resize-none')}
        />
      </Field>

      <div className="space-y-2">
        <label
          className={cn(
            'flex cursor-pointer items-center gap-2 text-sm text-gray-300',
            !brief && 'opacity-50',
          )}
        >
          <input
            type="checkbox"
            checked={autoScript}
            disabled={!brief}
            onChange={(e) => setAutoScript(e.target.checked)}
          />
          <Sparkles size={14} className="text-accent" />
          Auto-generate script from brief (Claude)
        </label>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={useRunway}
            onChange={(e) => setUseRunway(e.target.checked)}
            className="mt-0.5"
          />
          <Wand2 size={14} className="mt-0.5 shrink-0 text-accent" />
          <span>
            Animate after-headshots with Runway Gen-4 Turbo
            <span className="ml-1 text-xs text-gray-500">
              (adds ~60s + ~$1.20 per reel; falls back to Ken&nbsp;Burns if the API fails)
            </span>
          </span>
        </label>

        <label className="flex cursor-pointer items-start gap-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={useVoiceover}
            onChange={(e) => setUseVoiceover(e.target.checked)}
            className="mt-0.5"
          />
          <Mic size={14} className="mt-0.5 shrink-0 text-accent" />
          <span>
            Add ElevenLabs voiceover narration
            <span className="ml-1 text-xs text-gray-500">
              (~$0.05 per reel; renders silent if TTS fails)
            </span>
          </span>
        </label>

        {useVoiceover && (
          <div className="ml-6 space-y-2 rounded-lg border border-border bg-surface-overlay p-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">Voice</label>
              <select
                value={voiceoverVoice}
                onChange={(e) => setVoiceoverVoice(e.target.value)}
                className={inputCls}
              >
                <option value="narrator">Sarah — warm, friendly female (recommended)</option>
                <option value="female_clear">Rachel — clear, natural female</option>
                <option value="male_pro">Antoni — professional male</option>
                <option value="male_deep">Drew — deep, confident male</option>
                <option value="male_calm">Arnold — calm, authoritative male</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">
                Script <span className="text-gray-500">({voiceoverText.length} chars · aim for &lt;300)</span>
              </label>
              <textarea
                rows={3}
                value={voiceoverText}
                onChange={(e) => setVoiceoverText(e.target.value)}
                className={cn(inputCls, 'resize-none font-mono text-xs')}
              />
            </div>
          </div>
        )}
      </div>

      {error && <div className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</div>}

      <div className="flex justify-end gap-2 border-t border-border pt-4">
        <Button variant="ghost" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={busy}>
          {busy ? (
            <>
              <Loader2 size={14} className="mr-2 animate-spin" /> Creating…
            </>
          ) : (
            'Render Reel'
          )}
        </Button>
      </div>
    </div>
  );
}

const inputCls =
  'w-full rounded-lg border border-border bg-surface-overlay px-3 py-2 text-sm text-gray-100 placeholder:text-gray-500 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-300">{label}</span>
      {children}
    </label>
  );
}

function ImageSlot({
  label,
  hint,
  image,
  onChange,
  onRemove,
  busy,
}: {
  label: string;
  hint: string;
  image: UploadedImage | null;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemove: () => void;
  busy: boolean;
}) {
  return (
    <div>
      <div className="mb-1 text-sm font-semibold text-gray-200">{label}</div>
      <div className="mb-2 text-xs text-gray-500">{hint}</div>
      {image ? (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-overlay p-2">
          <img src={image.url} alt={image.filename} className="h-16 w-16 rounded object-cover" />
          <div className="flex-1 truncate text-sm text-gray-300">{image.filename}</div>
          <button onClick={onRemove} className="rounded p-1 text-gray-400 hover:text-gray-200">
            <X size={14} />
          </button>
        </div>
      ) : (
        <label
          className={cn(
            'flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-border bg-surface-overlay p-4 text-sm text-gray-400 hover:border-accent hover:text-accent',
            busy && 'pointer-events-none opacity-50',
          )}
        >
          <Upload size={16} />
          <span>Click to upload</span>
          <input type="file" accept="image/*" className="hidden" onChange={onChange} />
        </label>
      )}
    </div>
  );
}
