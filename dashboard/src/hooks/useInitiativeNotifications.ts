import { useEffect } from 'react';
import { aecoWs } from '../api/ws';
import { useToast } from '../components/ui/Toast';

/**
 * Listens to WebSocket initiative events and shows toast notifications
 * for key lifecycle transitions.
 */
export function useInitiativeNotifications() {
  const { toast } = useToast();

  useEffect(() => {
    const unsubs: (() => void)[] = [];

    unsubs.push(
      aecoWs.on('initiative.closed', (event) => {
        const title = (event.data.title as string) || 'Initiative';
        const verdict = event.data.verdict as string | undefined;

        if (verdict === 'scale') {
          toast(`${title} completed — merged to main!`, 'success');
        } else if (verdict === 'kill') {
          toast(`${title} killed`, 'error');
        } else {
          toast(`${title} closed`, 'info');
        }
      }),
    );

    unsubs.push(
      aecoWs.on('initiative.task_completed', (event) => {
        const taskName = (event.data.task_name as string) || 'Task';
        const agent = (event.data.agent_id as string) || 'agent';
        toast(`${taskName} completed by ${agent}`, 'info');
      }),
    );

    return () => unsubs.forEach((fn) => fn());
  }, [toast]);
}
