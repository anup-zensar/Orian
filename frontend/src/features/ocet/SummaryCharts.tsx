import { Caption1, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { OcetOut } from './api';
import { fmtFull, fmtK } from './format';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
    gap: tokens.spacingHorizontalL,
  },
  wrap: { overflowX: 'auto', minWidth: 0 },
  table: { borderCollapse: 'collapse', width: '100%' },
  cell: {
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
  },
  head: {
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    textAlign: 'right',
    backgroundColor: tokens.colorNeutralBackground2,
    fontWeight: tokens.fontWeightSemibold,
  },
  first: { textAlign: 'left' },
  foot: { fontWeight: tokens.fontWeightSemibold, backgroundColor: tokens.colorNeutralBackground2 },
});

const PALETTE = [
  tokens.colorPaletteBlueForeground2,
  tokens.colorPaletteTealForeground2,
  tokens.colorPaletteMarigoldForeground2,
  tokens.colorPalettePurpleForeground2,
  tokens.colorPaletteRedForeground2,
  tokens.colorPaletteGreenForeground2,
  tokens.colorPaletteDarkOrangeForeground2,
  tokens.colorPaletteBerryForeground2,
];

const yTick = (v: number) => fmtK(v);

/** Category x year table plus stacked bar (by category) and line (total) charts (spec 8.10). */
export function SummaryCharts({ data }: { data: OcetOut }) {
  const s = useStyles();
  const { years, category_totals: cats, grand_total_by_year: grand } = data;
  const byYear = years.map((y, i) => {
    const row: Record<string, number> = { year: y };
    for (const c of cats) row[c.category] = c.amounts[i]?.amount ?? 0;
    return row;
  });
  const totals = grand.map((g) => ({ year: g.year, total: g.amount }));
  const summary = totals.map((t) => `${t.year}: ${fmtK(t.total)}`).join('; ');

  if (cats.length === 0) return <Caption1>Add lines to see the summary.</Caption1>;

  return (
    <>
      <div className={s.wrap}>
        <table className={s.table}>
          <caption style={{ textAlign: 'left' }}>
            <Caption1>Cost by category and year ({data.estimate.currency})</Caption1>
          </caption>
          <thead>
            <tr>
              <th className={mergeClasses(s.head, s.first)}>Category</th>
              {years.map((y) => (
                <th key={y} className={s.head}>
                  {y}
                </th>
              ))}
              <th className={s.head}>Total</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => (
              <tr key={c.category}>
                <td className={mergeClasses(s.cell, s.first)}>{c.category}</td>
                {c.amounts.map((a) => (
                  <td key={a.year} className={s.cell}>
                    {fmtFull(a.amount)}
                  </td>
                ))}
                <td className={s.cell}>
                  <strong>{fmtFull(c.total)}</strong>
                </td>
              </tr>
            ))}
            <tr className={s.foot}>
              <td className={mergeClasses(s.cell, s.first)}>Total</td>
              {grand.map((g) => (
                <td key={g.year} className={s.cell}>
                  {fmtFull(g.amount)}
                </td>
              ))}
              <td className={s.cell}>{fmtFull(data.total)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className={s.grid}>
        <div
          role="img"
          aria-label={`Stacked bar chart of cost by category per year. Totals: ${summary}`}
          style={{ height: 280 }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byYear} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} padding={{ left: 24, right: 24 }} />
              <YAxis tickFormatter={yTick} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => fmtK(Number(v))} />
              <Legend
                formatter={(v) => (
                  <span style={{ color: tokens.colorNeutralForeground1 }}>{v}</span>
                )}
              />
              {cats.map((c, i) => (
                <Bar
                  key={c.category}
                  dataKey={c.category}
                  stackId="cost"
                  fill={PALETTE[i % PALETTE.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div
          role="img"
          aria-label={`Line chart of total cost per year. ${summary}`}
          style={{ height: 280 }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={totals} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} padding={{ left: 24, right: 24 }} />
              <YAxis tickFormatter={yTick} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => fmtK(Number(v))} />
              <Line
                type="monotone"
                dataKey="total"
                name="Total"
                stroke={tokens.colorBrandForeground1}
                strokeWidth={2}
                dot
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}
