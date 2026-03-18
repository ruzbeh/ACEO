import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { formatCurrency } from '../../lib/utils';

interface AgentBarChartProps {
  byAgent: Record<string, number>;
}

export function AgentBarChart({ byAgent }: AgentBarChartProps) {
  const data = Object.entries(byAgent)
    .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);

  if (data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-gray-500">No agent spend data</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
        <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} />
        <YAxis type="category" dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} width={80} />
        <Tooltip
          contentStyle={{ background: '#1e2030', border: '1px solid #2e3148', borderRadius: 8, fontSize: 12 }}
          formatter={(value: number) => formatCurrency(value)}
        />
        <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
