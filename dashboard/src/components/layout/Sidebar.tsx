import { NavLink } from 'react-router-dom';
import { Rocket, ListChecks, Wallet, Bot, Activity, Building2, Briefcase } from 'lucide-react';
import { cn } from '../../lib/utils';

const links = [
  { to: '/company', label: 'Company', icon: Building2 },
  { to: '/portfolio', label: 'Portfolio', icon: Briefcase },
  { to: '/initiatives', label: 'Initiatives', icon: Rocket },
  { to: '/tasks', label: 'Tasks', icon: ListChecks },
  { to: '/budget', label: 'Budget', icon: Wallet },
  { to: '/agents', label: 'Agents', icon: Bot },
] as const;

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-surface">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <Activity className="h-6 w-6 text-accent" />
        <span className="text-lg font-bold tracking-tight">AECO</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3 py-2">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent/10 text-accent'
                  : 'text-gray-400 hover:bg-surface-overlay hover:text-gray-200',
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Version */}
      <div className="border-t border-border px-5 py-3">
        <span className="text-xs text-gray-600">v0.1.0</span>
      </div>
    </aside>
  );
}
