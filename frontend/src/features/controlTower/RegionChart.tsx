// Readiness by region: average overall readiness per region (spec 8.2). Regions with no
// transitions are drawn as 0 and listed in a note.
import { Caption1, tokens } from '@fluentui/react-components';
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { RegionReadiness } from '../../api/types';

export function RegionChart({ data }: { data: RegionReadiness[] }) {
  const rows = data.map((r) => ({
    region: r.region,
    readiness: r.average_readiness ?? 0,
    transitions: r.transitions,
  }));
  const empty = data.filter((r) => r.transitions === 0).map((r) => r.region);
  const summary = data
    .map(
      (r) =>
        `${r.region}: ${r.average_readiness === null ? 'no transitions' : `${r.average_readiness}%`}`,
    )
    .join('; ');

  return (
    <>
      <div
        role="img"
        aria-label={`Average readiness by region. ${summary}`}
        style={{ height: 260 }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 20, right: 8, bottom: 4, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="region" tick={{ fontSize: 12 }} interval={0} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              formatter={(value, _name, item) => [
                item.payload.transitions === 0 ? 'No transitions' : `${value}%`,
                'Average readiness',
              ]}
            />
            <Bar
              dataKey="readiness"
              fill={tokens.colorBrandBackground}
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="readiness"
                position="top"
                formatter={(v) => `${v}%`}
                fontSize={12}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {empty.length > 0 && (
        <Caption1>No transitions in: {empty.join(', ')} (shown as 0%).</Caption1>
      )}
    </>
  );
}
