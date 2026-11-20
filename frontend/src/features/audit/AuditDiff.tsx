import { Caption1, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import type { AuditEventOut } from '../workspace/api';

const useStyles = makeStyles({
  table: { borderCollapse: 'collapse', width: '100%', fontSize: tokens.fontSizeBase200 },
  cell: {
    textAlign: 'left',
    verticalAlign: 'top',
    padding: `${tokens.spacingVerticalXXS} ${tokens.spacingHorizontalS}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    wordBreak: 'break-word',
    fontFamily: tokens.fontFamilyMonospace,
  },
  head: { fontFamily: tokens.fontFamilyBase, fontWeight: tokens.fontWeightSemibold },
  changed: { backgroundColor: tokens.colorBrandBackground2 },
});

function show(v: unknown): string {
  if (v === undefined) return '';
  if (typeof v === 'string') return v;
  return JSON.stringify(v);
}

/** Before/after snapshot diff: changed keys are highlighted (spec 8.17). */
export function AuditDiff({ event }: { event: AuditEventOut }) {
  const s = useStyles();
  const before = event.before ?? {};
  const after = event.after ?? {};
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();
  if (keys.length === 0) return <Caption1>No before/after snapshot was recorded.</Caption1>;
  return (
    <table className={s.table} aria-label="Before and after">
      <thead>
        <tr>
          <th className={mergeClasses(s.cell, s.head)}>Field</th>
          <th className={mergeClasses(s.cell, s.head)}>Before</th>
          <th className={mergeClasses(s.cell, s.head)}>After</th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const changed = show(before[k]) !== show(after[k]);
          return (
            <tr key={k} className={changed ? s.changed : undefined}>
              <td className={s.cell}>
                {k}
                {changed ? ' (changed)' : ''}
              </td>
              <td className={s.cell}>{show(before[k])}</td>
              <td className={s.cell}>{show(after[k])}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
