// Heatmap: portfolio (rows) x gate (columns); cell = count, coloured by worst RAG (spec 8.2).
import { Caption1, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { Diamond12Filled } from '@fluentui/react-icons';
import type { Heatmap as HeatmapData } from '../../api/types';
import { plural, toRag } from '../../lib/format';
import { ragColors } from '../../theme/tokens';

const useStyles = makeStyles({
  scroll: { overflowX: 'auto' },
  table: { borderCollapse: 'separate', borderSpacing: '3px', width: '100%', minWidth: '500px' },
  colHead: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    textAlign: 'center',
  },
  decision: { borderTop: `3px solid ${tokens.colorBrandForeground1}` },
  decisionTag: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '2px',
    color: tokens.colorBrandForeground1,
    fontWeight: tokens.fontWeightRegular,
  },
  rowHead: {
    textAlign: 'left',
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    paddingRight: tokens.spacingHorizontalS,
    whiteSpace: 'nowrap',
  },
  cell: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    minHeight: '48px',
    borderRadius: tokens.borderRadiusMedium,
    border: '1px solid transparent',
    font: 'inherit',
  },
  clickable: {
    cursor: 'pointer',
    ':hover': { boxShadow: tokens.shadow8 },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: '1px' },
  },
  selected: { outline: `3px solid ${tokens.colorBrandStroke1}`, outlineOffset: '1px' },
  count: { fontSize: tokens.fontSizeBase400, fontWeight: tokens.fontWeightSemibold, lineHeight: 1 },
  empty: { color: tokens.colorNeutralForeground4, backgroundColor: tokens.colorNeutralBackground2 },
});

interface Props {
  data: HeatmapData;
  selectedPortfolio?: string;
  selectedGate?: string;
  /** Called for non-empty cells only. */
  onSelect: (portfolio: string, gate: string) => void;
}

export function Heatmap({ data, selectedPortfolio, selectedGate, onSelect }: Props) {
  const s = useStyles();
  const cellMap = new Map(data.cells.map((c) => [`${c.portfolio}|${c.gate}`, c]));

  return (
    <div className={s.scroll}>
      <table className={s.table} aria-label="Transitions by portfolio and gate">
        <thead>
          <tr>
            <th scope="col">
              <span style={{ position: 'absolute', left: -9999 }}>Portfolio</span>
            </th>
            {data.gates.map((g) => (
              <th
                key={g.code}
                scope="col"
                className={mergeClasses(s.colHead, g.type === 'decision' && s.decision)}
              >
                {g.short}
                {g.type === 'decision' && (
                  <span className={s.decisionTag}>
                    <Diamond12Filled aria-hidden />
                    <Caption1>Decision</Caption1>
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.portfolios.map((p) => (
            <tr key={p}>
              <th scope="row" className={s.rowHead}>
                {p}
              </th>
              {data.gates.map((g) => {
                const cell = cellMap.get(`${p}|${g.code}`);
                const count = cell?.count ?? 0;
                if (count === 0) {
                  return (
                    <td key={g.code}>
                      <div
                        className={mergeClasses(s.cell, s.empty)}
                        role="img"
                        aria-label={`${p} at ${g.short}: no transitions`}
                      >
                        –
                      </div>
                    </td>
                  );
                }
                const rag = toRag(cell?.worst_rag);
                const c = ragColors[rag];
                const selected = selectedPortfolio === p && selectedGate === g.code;
                return (
                  <td key={g.code}>
                    <button
                      type="button"
                      className={mergeClasses(s.cell, s.clickable, selected && s.selected)}
                      style={{
                        color: c.foreground,
                        backgroundColor: c.background,
                        borderColor: c.border,
                      }}
                      aria-label={`${p} at ${g.short}: ${plural(count, 'transition')}, worst RAG ${
                        rag === 'Grey' ? 'Not started' : rag
                      }`}
                      onClick={() => onSelect(p, g.code)}
                    >
                      <span className={s.count}>{count}</span>
                      <Caption1>{rag === 'Grey' ? 'Not started' : rag}</Caption1>
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
