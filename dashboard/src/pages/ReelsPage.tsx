import { useState } from 'react';
import { Film, Plus, Loader2, Rocket, ExternalLink, AlertCircle, Wand2 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Dialog } from '../components/ui/Dialog';
import { EmptyState } from '../components/ui/EmptyState';
import { Spinner } from '../components/ui/Spinner';
import {
  Reel,
  ReelStatus,
  statusColor,
  statusLabel,
  useReels,
  usePublishReel,
} from '../api/reels';
import { NewReelForm } from '../features/reels/NewReelForm';
import { cn } from '../lib/utils';

export function ReelsPage() {
  const { data: reels, isLoading, error } = useReels();
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-3 text-2xl font-bold text-gray-100">
            <Film className="h-7 w-7 text-accent" />
            Reels
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            Generate 9:16 video ads and publish them to Facebook as paused drafts.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)}>
          <Plus size={16} className="mr-1.5" />
          New Reel
        </Button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      )}

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle size={16} />
            <span className="text-sm">Failed to load reels: {error.message}</span>
          </div>
        </Card>
      )}

      {reels && reels.length === 0 && (
        <EmptyState
          icon={Film}
          title="No reels yet"
          description="Upload a selfie and 3–6 AI headshots — we'll compose a 25-second reel ready for Facebook."
          action={
            <Button onClick={() => setShowNew(true)}>
              <Plus size={16} className="mr-1.5" />
              Create your first reel
            </Button>
          }
        />
      )}

      {reels && reels.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reels.map((r) => (
            <ReelCard key={r.id} reel={r} />
          ))}
        </div>
      )}

      <Dialog open={showNew} onClose={() => setShowNew(false)} title="New Reel">
        <NewReelForm onClose={() => setShowNew(false)} />
      </Dialog>
    </div>
  );
}

function ReelCard({ reel }: { reel: Reel }) {
  const publish = usePublishReel(reel.id);
  const [publishing, setPublishing] = useState(false);

  const handlePublish = async () => {
    setPublishing(true);
    try {
      await publish.mutateAsync({});
    } finally {
      setPublishing(false);
    }
  };

  const latest = reel.progress_log?.[reel.progress_log.length - 1];
  const mid = reel.status === 'rendering' || reel.status === 'publishing';

  return (
    <Card className="overflow-hidden p-0">
      {/* Preview */}
      <div className="relative aspect-[9/16] bg-black">
        {reel.mp4_url ? (
          <video
            src={reel.mp4_url}
            className="h-full w-full"
            controls
            playsInline
            preload="metadata"
            poster={reel.before_image_url || undefined}
          />
        ) : reel.before_image_url ? (
          <img src={reel.before_image_url} alt="before" className="h-full w-full object-cover opacity-60" />
        ) : null}

        {mid && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70">
            <Loader2 size={28} className="animate-spin text-accent" />
            <div className="mt-2 text-xs text-gray-300">{latest?.message ?? statusLabel(reel.status as ReelStatus)}</div>
          </div>
        )}

        <div className="absolute left-2 top-2">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
              statusColor(reel.status as ReelStatus),
            )}
          >
            {statusLabel(reel.status as ReelStatus)}
          </span>
        </div>

        <div className="absolute right-2 top-2 flex items-center gap-1">
          {reel.use_runway && (
            <span className="flex items-center gap-0.5 rounded bg-purple-500/90 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              <Wand2 size={9} /> Runway
            </span>
          )}
          {reel.duration_sec != null && (
            <div className="rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-mono text-gray-200">
              {reel.duration_sec.toFixed(0)}s
            </div>
          )}
        </div>
      </div>

      {/* Meta */}
      <div className="space-y-3 p-4">
        <div>
          <h3 className="line-clamp-1 text-sm font-semibold text-gray-100">{reel.title}</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            {reel.headline} · {reel.subheadline}
          </p>
        </div>

        {reel.last_error && (
          <div className="rounded bg-red-500/10 px-2 py-1 text-[11px] text-red-400">{reel.last_error}</div>
        )}

        <div className="flex items-center gap-2">
          {reel.status === 'rendered' && (
            <Button size="sm" onClick={handlePublish} disabled={publishing}>
              {publishing ? (
                <Loader2 size={12} className="mr-1.5 animate-spin" />
              ) : (
                <Rocket size={12} className="mr-1.5" />
              )}
              Publish to FB
            </Button>
          )}
          {reel.status === 'published' && reel.fb_ads_manager_url && (
            <a
              href={reel.fb_ads_manager_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-400 hover:bg-green-500/20"
            >
              View on Facebook <ExternalLink size={10} />
            </a>
          )}
          {reel.mp4_url && (
            <a
              href={reel.mp4_url}
              download
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-gray-400 hover:text-gray-200"
            >
              Download MP4
            </a>
          )}
        </div>
      </div>
    </Card>
  );
}
