"""Allow-list HTML sanitiser for Orion draft / email bodies (PLAN A-56, VAPT).

Standard library only (``html.parser``). Anything not on the allow-list is removed:

* tags: p br ul ol li strong em b i a h3 h4 table thead tbody tr th td span div; other tags are
  dropped but their text is kept, except script/style/iframe/object/embed/... which are dropped
  together with their content;
* attributes: only ``href`` on ``a`` and only for http, https, mailto or relative URLs (so
  ``javascript:``, ``data:`` ... links lose their href); event handlers and ``style`` never survive;
* comments, doctype and processing instructions are removed; text is re-escaped.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

ALLOWED_TAGS: frozenset[str] = frozenset(
    [
        "p",
        "br",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "b",
        "i",
        "a",
        "h3",
        "h4",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "span",
        "div",
    ]
)
VOID_TAGS: frozenset[str] = frozenset({"br"})
# Dropped together with everything inside them.
DROP_WITH_CONTENT: frozenset[str] = frozenset(
    {
        "script",
        "style",
        "iframe",
        "frame",
        "frameset",
        "object",
        "embed",
        "noscript",
        "template",
        "head",
        "title",
        "svg",
        "math",
        "textarea",
        "select",
        "applet",
    }
)
SAFE_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})

_CONTROL = re.compile(r"[\x00-\x20\x7f-\x9f]+")
_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")


def safe_url(value: str | None) -> str | None:
    """``value`` when it is an http(s)/mailto or relative URL, else ``None``."""
    if not value:
        return None
    compact = _CONTROL.sub("", html.unescape(value))  # "java\tscript:" and entity tricks
    if not compact:
        return None
    if compact.startswith("//") or compact.startswith("\\"):
        return None  # protocol-relative: could point anywhere
    scheme = _SCHEME.match(compact)
    if scheme:
        return value.strip() if scheme.group(1).lower() in SAFE_SCHEMES else None
    if ":" in compact.split("/")[0].split("?")[0].split("#")[0]:
        return None  # unknown scheme-like prefix
    return value.strip()


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip: list[str] = []  # open drop-with-content tags

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip:
            if tag in DROP_WITH_CONTENT and tag == self.skip[-1]:
                self.skip.append(tag)
            return
        if tag in DROP_WITH_CONTENT:
            self.skip.append(tag)
            return
        if tag not in ALLOWED_TAGS:
            return
        if tag in VOID_TAGS:
            self.out.append(f"<{tag}>")
            return
        rendered = f"<{tag}"
        if tag == "a":
            href = safe_url(dict(attrs).get("href"))
            if href is not None:
                rendered += f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
        self.out.append(rendered + ">")
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROP_WITH_CONTENT:
            return  # self-closing script/iframe: nothing to skip
        self.handle_starttag(tag, attrs)
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag in VOID_TAGS or tag not in ALLOWED_TAGS or tag not in self.stack:
            return
        while self.stack:  # close any unclosed children first
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_html(value: str | None) -> str:
    """Return ``value`` reduced to the allow-listed markup (idempotent)."""
    if not value:
        return ""
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return parser.result()


def escape_text(value: object) -> str:
    """HTML-escape a plain value for interpolation into generated bodies."""
    return html.escape("" if value is None else str(value), quote=True)
