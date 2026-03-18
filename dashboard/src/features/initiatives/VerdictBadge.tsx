import { Badge } from '../../components/ui/Badge';
import { VERDICT_COLORS } from '../../lib/constants';
import type { InitiativeVerdict } from '../../api/types';

export function VerdictBadge({ verdict }: { verdict: InitiativeVerdict }) {
  return (
    <Badge className={VERDICT_COLORS[verdict] ?? ''}>
      {verdict}
    </Badge>
  );
}
