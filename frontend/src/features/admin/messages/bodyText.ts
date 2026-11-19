// Message bodies are stored as small HTML snippets. The Admin edits them as plain text instead:
// paragraphs separated by a blank line, [label](deep_link) for the link, {{name}} for a value.
// If a body uses anything else, `toText` returns null and the editor shows the HTML as it is.

/** Placeholders that stand on their own line (a list or a closing line), not inside a paragraph. */
const BLOCK_PLACEHOLDERS = new Set([
  'item_list',
  'sign_off',
  'summary_html',
  'approver_line',
  'paragraphs',
]);

const LINK_HTML = /<a href="\{\{deep_link\}\}">([^<]*)<\/a>/g;
const LINK_TEXT = /\[([^\]]+)\]\(deep_link\)/g;

/** Plain-text form of a stored HTML body, or null when it cannot be shown losslessly. */
export function toText(html: string): string | null {
  const parts: string[] = [];
  const piece = /<p>([\s\S]*?)<\/p>|\{\{(\w+)\}\}/g;
  for (const m of html.matchAll(piece)) {
    if (m[1] !== undefined) {
      parts.push(m[1].replace(LINK_HTML, '[$1](deep_link)').replace(/<br>/g, '\n'));
    } else {
      parts.push(`{{${m[2]}}}`);
    }
  }
  const text = parts.join('\n\n');
  return toHtml(text) === html ? text : null;
}

/** Stored HTML form of the plain text the Admin typed. */
export function toHtml(text: string): string {
  return text
    .split(/\n{2,}/)
    .map((chunk) => chunk.trim())
    .filter((chunk) => chunk !== '')
    .map((chunk) => {
      const lone = /^\{\{(\w+)\}\}$/.exec(chunk);
      if (lone && BLOCK_PLACEHOLDERS.has(lone[1])) return chunk;
      const inner = chunk
        .replace(LINK_TEXT, '<a href="{{deep_link}}">$1</a>')
        .replace(/\n/g, '<br>');
      return `<p>${inner}</p>`;
    })
    .join('');
}

/** Every {{name}} used in the given texts. */
export function placeholdersIn(...texts: string[]): string[] {
  const names = new Set<string>();
  for (const t of texts) for (const m of t.matchAll(/\{\{\s*(\w+)\s*\}\}/g)) names.add(m[1]);
  return [...names];
}
