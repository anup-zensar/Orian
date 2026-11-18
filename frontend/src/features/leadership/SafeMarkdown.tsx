import { Fragment, type ReactNode } from 'react';
import { makeStyles, tokens } from '@fluentui/react-components';

// Renders the small markdown subset of leadership updates as React elements. Nothing is ever
// injected as HTML, so model/user text cannot add markup or scripts.

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    lineHeight: tokens.lineHeightBase300,
    '& h2, & h3, & h4, & p, & ul, & ol': { margin: 0 },
    '& h2': { fontSize: tokens.fontSizeBase500 },
    '& h3': { fontSize: tokens.fontSizeBase400, marginTop: tokens.spacingVerticalS },
    '& h4': { fontSize: tokens.fontSizeBase300 },
    '& ul, & ol': { paddingLeft: tokens.spacingHorizontalXXL },
    '& table': { borderCollapse: 'collapse', width: '100%' },
    '& th, & td': {
      border: `1px solid ${tokens.colorNeutralStroke2}`,
      padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
      textAlign: 'left',
    },
    '& code': { fontFamily: tokens.fontFamilyMonospace },
  },
});

const TOKEN = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\b_[^_\s][^_]*_\b|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g;
const SAFE_URL = /^(https?:\/\/|mailto:)/i;
const BULLET = /^\s*([-*]|\d+\.)\s+/;

function inline(text: string, keyBase: string): ReactNode[] {
  return text.split(TOKEN).map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (/^(\*[^*\s][^*]*\*|_[^_\s][^_]*_)$/.test(part)) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    if (/^`[^`]+`$/.test(part)) return <code key={key}>{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) {
      return SAFE_URL.test(link[2]) ? (
        <a key={key} href={link[2]} target="_blank" rel="noreferrer noopener">
          {link[1]}
        </a>
      ) : (
        <Fragment key={key}>{link[1]}</Fragment>
      );
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => c.trim());

const isSeparatorRow = (line: string) => /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes('-');

export function SafeMarkdown({ source }: { source: string }) {
  const s = useStyles();
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = `b${i}`;
    if (!line.trim()) {
      i += 1;
    } else if (/^#{1,3}\s/.test(line)) {
      const level = line.match(/^#+/)?.[0].length ?? 1;
      // the page already has an h1, so markdown headings start at h2
      const Tag = `h${level + 1}` as 'h2' | 'h3' | 'h4';
      out.push(<Tag key={key}>{inline(line.replace(/^#+\s*/, ''), key)}</Tag>);
      i += 1;
    } else if (BULLET.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && BULLET.test(lines[i])) {
        items.push(lines[i].replace(BULLET, ''));
        i += 1;
      }
      const lis = items.map((t, n) => <li key={`${key}-${n}`}>{inline(t, `${key}-${n}`)}</li>);
      out.push(ordered ? <ol key={key}>{lis}</ol> : <ul key={key}>{lis}</ul>);
    } else if (line.trim().startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        if (!isSeparatorRow(lines[i])) rows.push(cells(lines[i]));
        i += 1;
      }
      const [head = [], ...body] = rows;
      out.push(
        <div key={key} style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                {head.map((c, n) => (
                  <th key={n}>{inline(c, `${key}h${n}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((r, n) => (
                <tr key={n}>
                  {r.map((c, m) => (
                    <td key={m}>{inline(c, `${key}r${n}c${m}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else {
      const para: string[] = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^(#{1,3}\s|\s*[-*]\s+|\s*\d+\.\s+|\s*\|)/.test(lines[i])
      ) {
        para.push(lines[i]);
        i += 1;
      }
      out.push(<p key={key}>{inline(para.join(' '), key)}</p>);
    }
  }
  return <div className={s.root}>{out}</div>;
}
