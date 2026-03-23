import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useHealth } from '../../api/health';
import { WifiOff } from 'lucide-react';

export function AppShell() {
  const { isError } = useHealth();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {isError && (
          <div className="flex items-center gap-2 border-b border-red-500/30 bg-red-500/10 px-6 py-2.5">
            <WifiOff size={14} className="text-red-400" />
            <span className="text-sm text-red-300">
              Backend offline — start the API (uvicorn on 8000, or Docker on 8100). If you use{' '}
              <code className="rounded bg-black/30 px-1">npm run dev</code>, set{' '}
              <code className="rounded bg-black/30 px-1">VITE_DEV_PROXY_TARGET</code> in{' '}
              <code className="rounded bg-black/30 px-1">dashboard/.env.local</code> to match.
            </span>
          </div>
        )}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
