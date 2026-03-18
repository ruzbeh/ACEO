import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { CATEGORY_COLORS } from '../../lib/constants';
import { formatCurrency } from '../../lib/utils';

interface SpendDonutProps {
  byCategory: Record<string, number>;
}

export function SpendDonut({ byCategory }: SpendDonutProps) {
  const data = Object.entries(byCategory)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  if (data.length === 0) {
    return <div className="flex h-48 items-center justify-center text-sm text-gray-500">No spend data</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          stroke="none"
        >
          {data.map((d) => (
            <Cell key={d.name} fill={CATEGORY_COLORS[d.name] ?? '#6b7280'} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: '#1e2030', border: '1px solid #2e3148', borderRadius: 8, fontSize: 12 }}
          formatter={(value: number) => formatCurrency(value)}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
