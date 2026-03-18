import { useNavigate } from 'react-router-dom';
import { Copy, Loader2 } from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { VerdictBadge } from './VerdictBadge';
import { INITIATIVE_STATUS_COLORS } from '../../lib/constants';
import { formatDate } from '../../lib/utils';
import type { InitiativeResponse } from '../../api/types';

interface Props {
  initiative: InitiativeResponse;
  onCopy?: (initiative: InitiativeResponse) => void;
}

export function InitiativeCard({ initiative, onCopy }: Props) {
  const nav = useNavigate();

  return (
    <Card onClick={() => nav(`/initiatives/${initiative.id}`)}>
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-gray-100">{initiative.title}</h3>
          <p className="mt-1 line-clamp-2 text-xs text-gray-400">{initiative.goal}</p>
        </div>
        <div className="flex items-center gap-1.5">
          {onCopy && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCopy(initiative);
              }}
              className="rounded p-1.5 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
              title="Copy initiative"
            >
              <Copy size={14} />
            </button>
          )}
          <VerdictBadge verdict={initiative.verdict} />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        {(initiative.status === 'planning' || initiative.status === 'executing') && (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" title="Workflow running" />
        )}
        <Badge className={INITIATIVE_STATUS_COLORS[initiative.status] ?? ''}>
          {initiative.status.replace('_', ' ')}
        </Badge>
        <span className="text-xs text-gray-500">{formatDate(initiative.created_at)}</span>
      </div>
    </Card>
  );
}
