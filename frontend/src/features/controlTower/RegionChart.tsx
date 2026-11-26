// Readiness by region: average overall readiness per region (spec 8.2). Every configured region is
// listed; one without transitions is labelled "No transitions".
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
    label: r.transitions === 0 ? 'No transitions' : `${r.average_readiness ?? 0}%`,
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
      <div style={{ overflowX: 'auto' }}>
        <div
          role="img"
          aria-label={`Average readiness by region. ${summary}`}
          style={{ height: 260, minWidth: 400 }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={rows}
              margin={{ top: 4, right: 96, bottom: 4, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 100]}
                tickFormatter={(v: number) => `${v}%`}
                tick={{ fontSize: 12 }}
              />
              <YAxis
                type="category"
                dataKey="region"
                width={130}
                tick={{ fontSize: 12 }}
                interval={0}
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
                radius={[0, 3, 3, 0]}
                isAnimationActive={false}
              >
                <LabelList dataKey="label" position="right" fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      {empty.length > 0 && <Caption1>No transitions in: {empty.join(', ')}.</Caption1>}
    </>
  );
}
