// Tiny markdown-style editing mode for draft bodies. Text is always HTML-escaped first, so the
// generated HTML can only contain the few tags produced here (p, ul/li, strong, em, a, br).

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const SAFE_URL = /^(https?:\/\/|mailto:)/i;

function inline(raw: string): string {
  let t = escapeHtml(raw);
  t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label: string, url: string) => {
    const href = url.replace(/&amp;/g, '&');
    return SAFE_URL.test(href) ? `<a href="${escapeHtml(href)}">${label}</a>` : m;
  });
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  return t;
}

/** Markdown-style text (paragraphs, "- " bullets, **bold**, *italic*, [text](https://...)) to HTML. */
export function markdownToHtml(md: string): string {
  const blocks = md
    .replace(/\r\n/g, '\n')
    .trim()
    .split(/\n{2,}/);
  const out: string[] = [];
  for (const block of blocks) {
    if (!block.trim()) continue;
    const lines = block.split('\n');
    if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
      out.push(
        `<ul>${lines.map((l) => `<li>${inline(l.replace(/^\s*[-*]\s+/, ''))}</li>`).join('')}</ul>`,
      );
    } else {
      out.push(`<p>${lines.map(inline).join('<br>')}</p>`);
    }
  }
  return `<html><body style="font-family:Segoe UI,Arial,sans-serif;font-size:14px">${out.join('')}</body></html>`;
}

/** Best-effort HTML to markdown-style text, used to start the text mode from the saved body. */
export function htmlToMarkdown(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const walk = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return (node.textContent ?? '').replace(/\s+/g, ' ');
    if (!(node instanceof HTMLElement)) return '';
    const kids = () => Array.from(node.childNodes).map(walk).join('');
    switch (node.tagName) {
      case 'SCRIPT':
      case 'STYLE':
      case 'HEAD':
        return '';
      case 'STRONG':
      case 'B':
        return `**${kids()}**`;
      case 'EM':
      case 'I':
        return `*${kids()}*`;
      case 'A':
        return `[${kids()}](${node.getAttribute('href') ?? ''})`;
      case 'BR':
        return '\n';
      case 'LI':
        return `- ${kids().trim()}\n`;
      case 'UL':
      case 'OL':
        return `\n\n${kids().trim()}\n\n`;
      case 'P':
      case 'DIV':
      case 'H1':
      case 'H2':
      case 'H3':
      case 'TR':
        return `\n\n${kids().trim()}\n\n`;
      default:
        return kids();
    }
  };
  return walk(doc.body)
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const EMAIL = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

export const splitAddresses = (v: string): string[] =>
  v
    .split(/[,;\s]+/)
    .map((a) => a.trim())
    .filter(Boolean);

/** Returns an error message for a recipient list, or null when valid. */
export function validateRecipients(v: string, required: boolean): string | null {
  const list = splitAddresses(v);
  if (list.length === 0) return required ? 'Add at least one recipient' : null;
  const bad = list.filter((a) => !EMAIL.test(a));
  return bad.length > 0 ? `Not a valid email address: ${bad.join(', ')}` : null;
}
