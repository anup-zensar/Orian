"""Mock AIService.chat, leadership_update, extract_intake and parse_command (M8, FR-090, FR-080).

Deterministic, no network, NO database access, NO clock access: everything the extractors may match
against arrives in ``vocab`` (built from the DB by ``domain.nl_intake.build_vocabulary``), and the
demo date arrives in ``vocab["today"]`` / ``context["today"]``. There is no hard-coded project type,
portfolio, region, option, role or person in this module (the admin will add them in the UI).

``services/mock/ai.py`` delegates here. Read-only (BR-050).
"""

from __future__ import annotations

import calendar
import difflib
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from app.services.interfaces import IntakeExtraction, ParsedCommand

INTENTS = (
    "status",  # "status of <transition>"            entities {"query"}
    "blocking",  # "what is blocking AtD|AtO for <t>" entities {"gate_short", "query"}
    "owner",  # "who owns <item id>"                 entities {"item_id"}
    "glossary",  # "what is OCET|AtD|AtO"            entities {"term"}; text = definition
    "red_transitions",  # "show red transitions"
    "fallback",
)

QUICK_ACTION_LABELS = (
    "Start Gate Review",
    "Assess Gate Readiness",
    "Track Owner Actions",
    "Draft Owner Reminders",
    "Create Leadership Update",
    "Create Support Model",
    "Create / Update OCET",
)

DEFAULT_TERMS: dict[str, str] = {
    "OCET": (
        "OCET is the Operate Cost Estimate Template: the run-cost estimate of a transition "
        "(cloud, licences, support). It is versioned, approved by the Planner and the OLM, and "
        "linked to the checklist items FW-008 and S45-006."
    ),
    "AtD": (
        "AtD (Agreement to Deploy) is the decision gate before go-live. The OR focal records "
        "Approve, Approve with conditions or Return after the approval chain has agreed."
    ),
    "AtO": (
        "AtO (Agreement to Operate) is the decision gate after hypercare, when the service is "
        "handed over to run. It follows the same approval chain as AtD."
    ),
}

_FALLBACK_EXAMPLES = (
    "status of TR-0001",
    "what is blocking AtD for TR-0001",
    "who owns S3-019",
    "ask Tom to finish the DPIA for S3-019 by Friday",
)


# ---------------------------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------------------------
def fold(text: str) -> str:
    """Lower-case and strip accents, keeping the length of the text (character positions stay valid)."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch)[:1]
        out.append(base.lower() if base else ch.lower())
    return "".join(out)


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens_of(text: str) -> list[str]:
    """Normalised word list: folded, ``-_/`` read as spaces, punctuation dropped, plural s ignored."""
    cleaned = re.sub(r"[-_/]", " ", fold(text))
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return [_singular(w) for w in cleaned.split()]


MASK = "\x00"
FUZZY_MAX_TOKENS = 600  # the typo-tolerant stage is skipped for longer texts (cost is quadratic)


def _score(tokens: Sequence[str], phrase: Sequence[str]) -> tuple[float, list[int]]:
    """(score, matched token positions): 1.0 contiguous phrase, 0.9 all words in a 6-word window,
    0.75 fuzzy (difflib ratio >= 0.85), else 0."""
    n = len(phrase)
    if n == 0:
        return 0.0, []
    for i in range(len(tokens) - n + 1):
        if list(tokens[i : i + n]) == list(phrase):
            return 1.0, list(range(i, i + n))
    if n >= 2:
        width = max(6, n)
        for i in range(len(tokens)):
            window = tokens[i : i + width]
            if all(p in window for p in phrase):
                return 0.9, [i + window.index(p) for p in phrase]
    joined = " ".join(phrase)
    if len(joined) >= 5 and len(tokens) <= FUZZY_MAX_TOKENS:  # a hostile paste must stay cheap
        for i in range(len(tokens) - n + 1):
            chunk = " ".join(tokens[i : i + n])
            matcher = difflib.SequenceMatcher(None, chunk, joined)
            if matcher.real_quick_ratio() < 0.85 or matcher.quick_ratio() < 0.85:
                continue  # cheap upper bounds: ratio() cannot reach 0.85
            if matcher.ratio() >= 0.85:
                return 0.75, list(range(i, i + n))
    return 0.0, []


def _entry_name(item: Any) -> str:
    return str(item["name"] if isinstance(item, Mapping) else item)


def _candidates(vocab: Mapping[str, Any], kind: str, items: Sequence[Any]) -> list[dict[str, Any]]:
    """Candidate list [{value, label, phrases}] with admin synonyms merged (vocab["synonyms"][kind])."""
    extra = (vocab.get("synonyms") or {}).get(kind, {})
    out = []
    for item in items:
        name = _entry_name(item)
        phrases = [name]
        if isinstance(item, Mapping):
            phrases += list(item.get("synonyms") or [])
        phrases += list(extra.get(name, []))
        out.append({"value": name, "label": name, "phrases": phrases})
    return sorted(out, key=lambda c: c["label"])


def _pick(
    tokens: list[str], cands: Sequence[Mapping[str, Any]], *, partial: bool = False
) -> dict[str, Any]:
    """Best candidate among ``cands`` (found / inferred / ambiguous / missing); masks matched tokens."""
    scored: list[tuple[float, str, Mapping[str, Any], list[int]]] = []
    for cand in cands:
        best = (0.0, [])
        for phrase in cand["phrases"]:
            ptokens = tokens_of(phrase)
            score, pos = _score(tokens, ptokens)
            if score > best[0]:
                best = (score, pos)
        if partial and best[0] == 0.0:
            best = _partial(tokens, cand, cands)
        if best[0] >= 0.75:
            scored.append((best[0], cand["label"], cand, best[1]))
    if not scored:
        return {"state": "missing", "value": None, "score": 0.0, "candidates": [], "positions": []}
    scored.sort(key=lambda s: (-s[0], s[1]))
    top = scored[0][0]
    tied = [s for s in scored if top - s[0] <= 0.05]
    if len(tied) > 1:
        options = [{"value": s[2]["value"], "label": s[2]["label"]} for s in tied]
        return {
            "state": "ambiguous",
            "value": None,
            "score": top,
            "candidates": options,
            "positions": [],
        }
    score, _, cand, pos = scored[0]
    state = "found" if score >= 0.9 else "inferred"
    return {
        "state": state,
        "value": cand["value"],
        "score": score,
        "candidates": [],
        "positions": pos,
        "label": cand["label"],
    }


def _partial(
    tokens: Sequence[str], cand: Mapping[str, Any], cands: Sequence[Mapping[str, Any]]
) -> tuple[float, list[int]]:
    """One distinctive word of a multi-word candidate ("Retail" for "Retail Site Systems") -> 0.8."""
    for phrase in cand["phrases"]:
        ptokens = tokens_of(phrase)
        if len(ptokens) < 2:
            continue
        for word in ptokens:
            if len(word) < 4 or word not in tokens:
                continue
            shared = any(
                word in tokens_of(p)
                for other in cands
                if other is not cand
                for p in other["phrases"]
            )
            if not shared:
                return 0.8, [tokens.index(word)]
    return 0.0, []


def _mask(tokens: list[str], positions: Sequence[int]) -> None:
    for p in positions:
        if 0 <= p < len(tokens):
            tokens[p] = MASK


def _snippet(raw: str, words: Sequence[str], width: int = 40) -> str:
    folded = fold(raw)
    for word in words:
        idx = folded.find(word)
        if idx >= 0:
            start = max(0, idx - width)
            end = min(len(raw), idx + len(word) + width)
            return " ".join(raw[start:end].split())[:300]
    return ""


# ---------------------------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------------------------
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name} | {
    name.lower(): i for i, name in enumerate(calendar.month_abbr) if name
}
_MONTHS["sept"] = 9
_WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\b(?:\s*,?\s*(\d{{4}}))?(?!\d)"
)
_MONTH_DAY = re.compile(
    rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?(?!\d)"
)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DM = re.compile(r"\b(\d{1,2})/(\d{1,2})\b(?![/\d])")
_IN_N = re.compile(r"\bin\s+(\d{1,3})\s+(day|week)s?\b")
_WEEKDAY = re.compile(r"\b(?:(next|this)\s+)?(" + "|".join(_WEEKDAYS) + r")\b")
_END_MONTH = re.compile(r"\bend\s+of\s+(?:the\s+)?month\b")
_REL_WORD = re.compile(r"\b(today|tomorrow)\b")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_occurrence(month: int, day: int, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        candidate = _safe_date(year, month, day)
        if candidate is not None and candidate >= today:
            return candidate
    return None


def parse_dates(raw: str, today: date, *, relative: bool = True) -> list[dict[str, Any]]:
    """Every date mentioned: [{start, end, date, text}] ordered by position, no overlaps."""
    folded = fold(raw)
    found: list[dict[str, Any]] = []
    taken: list[tuple[int, int]] = []

    def free(span: tuple[int, int]) -> bool:
        return all(span[1] <= a or span[0] >= b for a, b in taken)

    def add(span: tuple[int, int], value: date | None) -> None:
        if value is not None and free(span):
            taken.append(span)
            found.append(
                {"start": span[0], "end": span[1], "date": value, "text": raw[span[0] : span[1]]}
            )

    for m in _ISO.finditer(folded):
        add(m.span(), _safe_date(int(m[1]), int(m[2]), int(m[3])))
    for m in _DMY.finditer(folded):
        add(m.span(), _safe_date(int(m[3]), int(m[2]), int(m[1])))
    for m in _DAY_MONTH.finditer(folded):
        month, day = _MONTHS[m[2]], int(m[1])
        value = _safe_date(int(m[3]), month, day) if m[3] else _next_occurrence(month, day, today)
        add(m.span(), value)
    for m in _MONTH_DAY.finditer(folded):
        month, day = _MONTHS[m[1]], int(m[2])
        value = _safe_date(int(m[3]), month, day) if m[3] else _next_occurrence(month, day, today)
        add(m.span(), value)
    for m in _DM.finditer(folded):
        add(m.span(), _next_occurrence(int(m[2]), int(m[1]), today))
    if relative:
        for m in _REL_WORD.finditer(folded):
            add(m.span(), today if m[1] == "today" else today + timedelta(days=1))
        for m in _IN_N.finditer(folded):
            days = int(m[1]) * (7 if m[2] == "week" else 1)
            add(m.span(), today + timedelta(days=days))
        for m in _WEEKDAY.finditer(folded):
            delta = (_WEEKDAYS[m[2]] - today.weekday()) % 7 or 7
            add(m.span(), today + timedelta(days=delta))
        for m in _END_MONTH.finditer(folded):
            last = calendar.monthrange(today.year, today.month)[1]
            add(m.span(), date(today.year, today.month, last))
    return sorted(found, key=lambda d: d["start"])


def _parse_today(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date(2000, 1, 1)


# ---------------------------------------------------------------------------------------------
# chat (keyword intents)
# ---------------------------------------------------------------------------------------------
_STATUS_RE = re.compile(
    r"^(?:what(?:'s| is)\s+(?:the\s+)?)?(?:status|state)\s+(?:of|for|on)\s+(?P<q>.+?)\s*[?.!]*$"
    r"|^how\s+is\s+(?P<q2>.+?)\s+(?:doing|going|looking)\s*[?.!]*$",
    re.IGNORECASE,
)
_BLOCKING_RE = re.compile(
    r"^what(?:'s| is| are)?\s+(?:currently\s+)?(?:blocking|stopping|stops|blocks|holding up)\s+"
    r"(?:(?P<gate>[a-z0-9_ ()-]{2,20}?)\s+)?(?:for|on|of|in)\s+(?P<q>.+?)\s*[?.!]*$",
    re.IGNORECASE,
)
_OWNER_RE = re.compile(
    r"^who\s+(?:owns|is\s+(?:the\s+)?owner\s+of|has)\s+(?:item\s+)?(?P<id>[A-Za-z]+\d*-\d+)\s*[?.!]*$",
    re.IGNORECASE,
)
_GLOSSARY_RE = re.compile(
    r"^(?:what(?:'s| is| does)|explain|define|tell me about)\s+(?:the\s+)?(?P<t>[A-Za-z0-9 /&-]{2,30}?)"
    r"(?:\s+mean)?\s*[?.!]*$",
    re.IGNORECASE,
)
_RED_RE = re.compile(
    r"\b(?:red\s+transitions?|transitions?\s+(?:that\s+are|which\s+are)?\s*(?:red|at\s+risk)"
    r"|which\s+transitions?\s+(?:are|is)\s+(?:red|at\s+risk))\b",
    re.IGNORECASE,
)


def chat(message: str, context: Mapping[str, Any]) -> dict[str, Any]:
    """Keyword intent router: returns {"intent": one of INTENTS, "entities": {...}, "text": str}.
    Case-insensitive, tolerant of punctuation/extra spaces; ``text`` is the glossary definition for
    ``glossary``, the helpful fallback (lists the 7 quick actions) for ``fallback`` and "" otherwise.
    ``context`` may carry ``transition_id`` used when the message omits the transition and ``terms``
    (glossary: term -> definition, read from reference data by the caller)."""
    text = " ".join((message or "").split())
    terms: Mapping[str, str] = context.get("terms") or DEFAULT_TERMS
    ctx_tid = context.get("transition_id")

    m = _BLOCKING_RE.match(text)
    if m:
        gate_words = (m.group("gate") or "").strip()
        return {
            "intent": "blocking",
            "entities": {"gate_short": gate_words, "query": m.group("q").strip()},
            "text": "",
        }
    m = _STATUS_RE.match(text)
    if m:
        query = (m.group("q") or m.group("q2") or "").strip()
        return {"intent": "status", "entities": {"query": query}, "text": ""}
    m = _OWNER_RE.match(text)
    if m:
        return {"intent": "owner", "entities": {"item_id": m.group("id").upper()}, "text": ""}
    if _RED_RE.search(text):
        return {"intent": "red_transitions", "entities": {}, "text": ""}
    m = _GLOSSARY_RE.match(text)
    if m:
        wanted = " ".join(tokens_of(m.group("t")))
        for term in sorted(terms):
            if " ".join(tokens_of(term)) == wanted:
                return {"intent": "glossary", "entities": {"term": term}, "text": terms[term]}
    if re.match(r"^(?:status|how are we doing)\s*[?.!]*$", text, re.IGNORECASE) and ctx_tid:
        return {"intent": "status", "entities": {"query": str(ctx_tid)}, "text": ""}
    return {"intent": "fallback", "entities": {}, "text": fallback_text()}


def fallback_text() -> str:
    actions = " - ".join(QUICK_ACTION_LABELS)
    return (
        "I can help with: "
        + actions
        + ". You can also ask, for example: "
        + "; ".join(f'"{e}"' for e in _FALLBACK_EXAMPLES)
        + ". I draft and recommend; you decide."
    )


# ---------------------------------------------------------------------------------------------
# leadership_update (FR-080)
# ---------------------------------------------------------------------------------------------
def _n(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _human_date(value: Any) -> str:
    """ "2026-11-18" -> "18 Nov 2026" (the app's date style); anything else is returned as text."""
    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return f"{day.day} {day.strftime('%b %Y')}"


def leadership_update(scope_data: Mapping[str, Any]) -> str:
    """Markdown from ``domain.leadership.collect_scope_data`` output. First line ``# <title>``;
    sections ``## Headline``, ``## Status by portfolio`` (and by gate), ``## Top risks and
    blockers``, ``## Decisions due in the next 30 days``, ``## Asks for leadership``, ``## Wins``.
    Includes recent AtD/AtO approvals (date, approver) and remaining risks. Deterministic; ends with
    "Generated by Orion agent"."""
    d = scope_data
    title = d.get("title") or "Leadership update"
    transitions = list(d.get("transitions") or [])
    portfolios = list(d.get("portfolios") or [])
    risks = list(d.get("risks") or [])
    decisions = list(d.get("decisions_next_30_days") or [])
    approvals = list(d.get("approvals") or [])
    asks = list(d.get("asks") or [])
    wins = list(d.get("wins") or [])
    today = d.get("today", "")

    rag = Counter(t.get("rag") for t in transitions)
    lines = [f"# {title}", "", f"_As of {_human_date(today)}_", "", "## Headline", ""]
    head = (
        f"{_n(len(transitions), 'transition')} in scope: {rag.get('Red', 0)} Red, "
        f"{rag.get('Amber', 0)} Amber, {rag.get('Green', 0)} Green"
    )
    if rag.get("Grey", 0):
        head += f", {rag['Grey']} not launched"
    lines.append(head + ".")
    for a in approvals[:2]:
        lines.append(
            f"{a['type']} approved for {a['name']} on {_human_date(a['date'])}"
            + (f" (by {a['approver']})" if a.get("approver") else "")
            + "."
        )
    if risks:
        lines.append(f"Biggest remaining risk: {risks[0]['text']}.")
    elif transitions:
        lines.append("No open critical risks or blockers.")

    lines += ["", "## Status by portfolio", ""]
    if portfolios:
        lines += [
            "| Portfolio | Transitions | Red | Amber | Green | Not launched |",
            "|---|---|---|---|---|---|",
        ]
        for p in portfolios:
            c = p["rag"]
            lines.append(
                f"| {p['name']} | {p['count']} | {c.get('Red', 0)} | {c.get('Amber', 0)} | "
                f"{c.get('Green', 0)} | {c.get('Grey', 0)} |"
            )
    else:
        lines.append("No transitions in scope.")
    gates = Counter(t.get("gate_short") for t in transitions)
    if gates:
        lines += [
            "",
            "**By gate:** "
            + ", ".join(f"{g}: {n}" for g, n in sorted(gates.items(), key=lambda kv: str(kv[0]))),
        ]
    lines += [
        "",
        "| Transition | Gate | Readiness | RAG | Next decision |",
        "|---|---|---|---|---|",
    ]
    for t in transitions:
        when = _human_date(t["next_decision"]) if t.get("next_decision") else "-"
        if t.get("days") is not None:
            when += f" ({t['days']} d)"
        lines.append(
            f"| {t['name']} ({t['id']}) | {t.get('gate_short', '')} | {t.get('readiness', 0)}% | "
            f"{t.get('rag', '')} | {when} |"
        )

    lines += ["", "## Top risks and blockers", ""]
    lines += [f"- {r['text']}" for r in risks] or ["- None open."]

    lines += ["", "## Decisions due in the next 30 days", ""]
    lines += [
        f"- {x['gate_short']} decision for {x['name']} on {_human_date(x['date'])} ({_n(x['days'], 'day')}), "
        f"status {x['rag']}"
        for x in decisions
    ] or ["- No gate decisions due in the next 30 days."]

    lines += ["", "## Asks for leadership", ""]
    lines += [f"- {a}" for a in asks] or ["- No asks at this time."]

    lines += ["", "## Wins", ""]
    lines += [f"- {w}" for w in wins] or ["- No new wins to report."]
    lines += ["", "_Generated by Orion agent. Orion drafts, people decide._"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------------------------
def _role_phrases(vocab: Mapping[str, Any]) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    for role in vocab.get("roles", []):
        label = re.sub(r"\(.*?\)", " ", str(role.get("label", "")))
        phrases = [tokens_of(str(role["code"])), tokens_of(label)]
        out[role["code"]] = [p for p in phrases if p]
    return out


def _window_roles(
    folded: str, start: int, end: int, role_phrases: Mapping[str, list[list[str]]]
) -> set[str]:
    window = tokens_of(folded[max(0, start - 40) : end + 40])
    found = set()
    for role, phrases in role_phrases.items():
        for phrase in phrases:
            if _score(window, phrase)[0] == 1.0:
                found.add(role)
    return found


def _user_candidate(user: Mapping[str, Any], role_labels: Mapping[str, str]) -> dict[str, str]:
    return {
        "value": user["id"],
        "label": f"{user['name']} ({role_labels.get(user['role'], user['role'])})",
    }


def find_people(raw: str, vocab: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Users mentioned in ``raw`` -> role-picker field -> {state, value, score, candidates, evidence}.

    Full name -> found; first name unique among users -> found; a first name shared by several users
    is narrowed by a role cue within 40 characters ("architect Mei", "Mei (OLM)") and is "ambiguous"
    when it still matches several users of the same role."""
    folded = fold(raw)
    users = sorted(vocab.get("users", []), key=lambda u: u["id"])
    role_fields: Mapping[str, str] = vocab.get("role_fields", {})
    field_of_role = {role: field for field, role in role_fields.items()}
    role_labels = {r["code"]: r.get("label", r["code"]) for r in vocab.get("roles", [])}
    role_phrases = _role_phrases(vocab)
    mentions: list[dict[str, Any]] = []  # {users: [user], score, start, end, full}

    for user in users:
        name_tokens = tokens_of(user["name"])
        if not name_tokens:
            continue
        full_re = r"\b" + r"[\s.-]+".join(re.escape(fold(w)) for w in user["name"].split()) + r"\b"
        full = re.search(full_re, folded)
        if full:
            mentions.append(
                {
                    "users": [user],
                    "score": 1.0,
                    "start": full.start(),
                    "end": full.end(),
                    "full": True,
                }
            )
    covered = [(m["start"], m["end"]) for m in mentions]
    done_first: set[str] = set()
    for user in users:
        name_tokens = tokens_of(user["name"])
        if not name_tokens or name_tokens[0] in done_first:
            continue
        first = name_tokens[0]
        if len(first) < 2:
            continue
        for m in re.finditer(r"\b" + re.escape(fold(user["name"].split()[0])) + r"\b", folded):
            if any(a <= m.start() < b for a, b in covered):
                continue
            same = [u for u in users if tokens_of(u["name"])[:1] == [first]]
            if len(same) == 1:
                mentions.append(
                    {"users": same, "score": 0.9, "start": m.start(), "end": m.end(), "full": False}
                )
                continue
            cued = _window_roles(folded, m.start(), m.end(), role_phrases)
            narrowed = [u for u in same if u["role"] in cued] or same
            mentions.append(
                {
                    "users": narrowed,
                    "score": 0.9 if len(narrowed) == 1 else 0.8,
                    "start": m.start(),
                    "end": m.end(),
                    "full": False,
                }
            )
        done_first.add(first)

    by_field: dict[str, list[dict[str, Any]]] = {}
    for mention in mentions:
        roles = {u["role"] for u in mention["users"] if u["role"] in field_of_role}
        for role in sorted(roles):
            members = [u for u in mention["users"] if u["role"] == role]
            by_field.setdefault(field_of_role[role], []).append({**mention, "users": members})

    result: dict[str, dict[str, Any]] = {}
    for field, items in by_field.items():
        distinct: dict[str, dict[str, Any]] = {}
        ambiguous: list[Mapping[str, Any]] = []
        for item in items:
            if len(item["users"]) == 1:
                distinct.setdefault(item["users"][0]["id"], item)
            else:
                ambiguous.extend(item["users"])
        pool = {u["id"]: u for u in ambiguous} | {uid: i["users"][0] for uid, i in distinct.items()}
        if len(pool) == 1 and len(distinct) == 1:
            uid, item = next(iter(distinct.items()))
            result[field] = {
                "state": "found" if item["score"] >= 0.9 else "inferred",
                "value": uid,
                "score": item["score"],
                "candidates": [],
                "evidence": _snippet(raw, [fold(raw)[item["start"] : item["end"]]]),
            }
        else:
            cands = [
                _user_candidate(u, role_labels)
                for u in sorted(pool.values(), key=lambda u: u["id"])
            ]
            first_item = items[0]
            result[field] = {
                "state": "ambiguous",
                "value": None,
                "score": 0.8,
                "candidates": cands,
                "evidence": _snippet(raw, [fold(raw)[first_item["start"] : first_item["end"]]]),
            }
    return result


# ---------------------------------------------------------------------------------------------
# extract_intake
# ---------------------------------------------------------------------------------------------
_PRJ_RE = re.compile(r"\bPRJ\d+\b", re.IGNORECASE)
_NAME_STRIP = re.compile(r"^(?:the|a|an|our|new)\s+", re.IGNORECASE)
_NAME_TAIL = re.compile(
    r"\s+(?:project|solution|transition|application|app|programme|program)$", re.IGNORECASE
)
_NAME_RES = (
    re.compile(r"\b(?:called|named)\s+[\"'“‘]?(?P<n>[^\"'”’,.;\n]{2,80})", re.IGNORECASE),
    re.compile(
        r"\b(?:transition|project|solution)\s*[:\-–]\s*(?P<n>[^,.;\n]{2,80}?)(?=\s+for\b|\s+in\b|,|;|\.|\n|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfor\s+(?:the\s+)?(?P<n>[^,.;\n]{2,80}?)\s+(?:project|solution|transition|application|app)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:review|assessment|transition|project|solution)\s+for\s+(?:the\s+)?(?P<n>[^,.;\n]{2,80}?)(?=,|;|\.|\n|\s+in\s+|\s+-\s+|$)",
        re.IGNORECASE,
    ),
)
_SUBJECT_RE = re.compile(r"^\s*subject\s*:\s*(?P<n>.+)$", re.IGNORECASE | re.MULTILINE)
_SITE_RE = re.compile(
    r"site\s*(?:id)?\s*[:#]?\s*([A-Za-z0-9-]{3,})[\s,;(]+(?:site\s*)?key\s*[:#]?\s*([A-Za-z0-9-]+)",
    re.IGNORECASE,
)
_DATE_CUE = re.compile(
    r"(decision|go[\s-]?live|launch|deadline|gate|\bby\b|\bdue\b|target)\s*(?:date)?\s*(?:is|on|of|:|=)?\s*$"
)
_NEG_CUES = ("no", "without", "none", "zero")


def _field(
    value: Any = None,
    state: str = "missing",
    source: str | None = None,
    confidence: float = 0.0,
    evidence: str | None = None,
    candidates: list[dict[str, str]] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "state": state,
        "source": source,
        "confidence": round(confidence, 2),
        "evidence": (evidence or None) and evidence[:300],
        "candidates": candidates or [],
        "note": note,
    }


def _from_pick(pick: Mapping[str, Any], raw: str, source: str = "text") -> dict[str, Any]:
    if pick["state"] == "missing":
        return _field()
    words = [pick.get("label") or ""] if pick["state"] in ("found", "inferred") else []
    evidence = _snippet(raw, [fold(w) for w in words if w]) if words else None
    return _field(
        pick["value"],
        pick["state"],
        source,
        pick["score"],
        evidence,
        list(pick["candidates"]),
        "Several matches - choose one" if pick["state"] == "ambiguous" else None,
    )


def _is_negative(option: str) -> bool:
    toks = tokens_of(option)
    return bool(toks) and toks[0] in ("no", "none")


def _pick_option(
    work: list[str],
    raw: str,
    folded: str,
    field: str,
    options: Sequence[str],
    vocab: Mapping[str, Any],
) -> dict[str, Any]:
    cands = _candidates(vocab, field, options)
    negatives = [o for o in options if _is_negative(o)]
    field_tokens = tokens_of(field.replace("_", " "))
    # "no write actions", "without sensitive data", "write actions: yes" ----------------------
    if negatives:
        field_re = r"[\s_-]*".join(re.escape(w) for w in field.split("_"))
        field_re = (
            r"\b" + field_re.replace(r"write[\s_-]*actions", r"write[\s_-]*actions?") + r"s?\b"
        )
        for m in re.finditer(field_re, folded):
            before = tokens_of(folded[max(0, m.start() - 24) : m.start()])[-3:]
            if any(w in _NEG_CUES for w in before):
                return _field(negatives[0], "found", "text", 0.9, _snippet(raw, [m.group(0)]))
            after = tokens_of(folded[m.end() : m.end() + 30])[:2]
            for opt in options:
                otok = tokens_of(opt)
                if otok and after[: len(otok)] == otok:
                    return _field(opt, "found", "text", 0.9, _snippet(raw, [m.group(0)]))
            positives = [o for o in options if o not in negatives]
            if len(positives) == 1 and len(options) == 2:
                return _field(positives[0], "found", "text", 0.9, _snippet(raw, [m.group(0)]))
    non_neg = [c for c in cands if not _is_negative(c["label"])]
    pick = _pick(work, non_neg)
    if pick["state"] != "missing":
        _mask(work, pick["positions"])
        return _from_pick(pick, raw)
    if negatives and re.search(
        r"\b(?:" + "|".join(_NEG_CUES) + r")\s+" + r"\s+".join(map(re.escape, field_tokens[:1])),
        folded,
    ):
        return _field(negatives[0], "inferred", "text", 0.75, _snippet(raw, [field_tokens[0]]))
    return _field()


def _extract_name(text: str, vocab: Mapping[str, Any], reject: set[str]) -> dict[str, Any]:
    def clean(candidate: str) -> str:
        candidate = candidate.strip(" \"'“”‘’:-–")
        candidate = _NAME_STRIP.sub("", candidate)
        candidate = _NAME_TAIL.sub("", candidate)
        candidate = re.sub(r"\bPRJ\d+\b", "", candidate, flags=re.IGNORECASE).strip(" ,-")
        return candidate[:80].strip()

    def acceptable(candidate: str) -> bool:
        toks = tokens_of(candidate)
        return bool(toks) and not set(toks) <= reject and len(candidate) >= 2

    subject = _SUBJECT_RE.search(text)
    sources: list[tuple[str, str]] = []
    if subject:
        name = re.sub(r"^(?:\s*(?:re|fwd?)\s*:\s*)+", "", subject.group("n"), flags=re.IGNORECASE)
        sources.append((name, "Subject line"))
    for rx in _NAME_RES:
        for m in rx.finditer(text):
            sources.append((m.group("n"), m.group(0)))
    for candidate, evidence in sources:
        value = clean(candidate)
        if acceptable(value):
            conf = 0.9 if evidence.lower().startswith(("called", "named", "subject")) else 0.8
            return _field(
                value, "found" if conf >= 0.9 else "inferred", "text", conf, evidence[:200]
            )
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if (
        first
        and len(first) <= 80
        and ":" not in first
        and len(text.splitlines()) > 2
        and acceptable(clean(first))
    ):
        return _field(clean(first), "inferred", "text", 0.6, first)
    return _field()


def _extract_dates(raw: str, today: date) -> dict[str, Any]:
    folded = fold(raw)
    cued = []
    for d in parse_dates(raw, today, relative=False):
        before = folded[max(0, d["start"] - 30) : d["start"]]
        if _DATE_CUE.search(before):
            cued.append(d)
    if not cued:
        return _field()
    distinct = sorted({d["date"] for d in cued})
    if len(distinct) > 1:
        cands = [{"value": x.isoformat(), "label": x.isoformat()} for x in distinct]
        return _field(
            None, "ambiguous", "text", 0.7, cued[0]["text"], cands, "Several dates mentioned"
        )
    first = cued[0]
    return _field(
        first["date"].isoformat(), "found", "text", 0.9, _snippet(raw, [fold(first["text"])])
    )


def _extract_sites(raw: str) -> dict[str, Any]:
    rows = [{"site_id": m[1], "site_key": m[2]} for m in _SITE_RE.finditer(raw)]
    if not rows:
        lines = raw.splitlines()
        for i, ln in enumerate(lines):
            if re.match(r"^\s*sites?\s*[:\-]?\s*$", ln, re.IGNORECASE):
                for row in lines[i + 1 :]:
                    parts = [p.strip() for p in re.split(r"[,;\t]", row) if p.strip()]
                    if len(parts) == 2 and re.match(r"^[A-Za-z0-9-]{3,}$", parts[0]):
                        rows.append({"site_id": parts[0], "site_key": parts[1]})
                    elif row.strip():
                        break
    if not rows:
        return _field()
    unique = list({(r["site_id"], r["site_key"]): r for r in rows}.values())
    return _field(unique, "found", "text", 0.9, f"{len(unique)} site(s) in the text")


def extract_intake(
    text: str, vocab: Mapping[str, Any], servicenow: Mapping[str, Any] | None = None
) -> IntakeExtraction:
    """Deterministic intake extractor (spec 8.4). No DB, no network, no randomness; every list is
    iterated in sorted order and ties are broken alphabetically. All matching is against ``vocab``
    (built from the DB by ``domain.nl_intake.build_vocabulary``) - there is NO hard-coded project type,
    portfolio, region, option, role or person in this function.

    Normalisation: lower-case, accents stripped, ``-_/`` -> space, punctuation removed, plural "s"
    ignored, whitespace collapsed. ``match(phrase, candidates)`` scores each candidate (its name and
    its ``synonyms``) against the text: 1.0 whole-phrase match on word boundaries; 0.9 all words of the
    candidate present within a 6-word window; 0.75 ``difflib.SequenceMatcher`` ratio >= 0.85 on a
    window of the same length; 0.8 one distinctive word of a multi-word candidate ("Retail" for
    "Retail Site Systems") when no other candidate shares it. One best candidate (>= 0.9) -> state
    "found" (below -> "inferred"); two or more candidates tied within 0.05 -> "ambiguous" with the
    candidates and no value. Confidence = the score. ServiceNow values (``servicenow``) win over the
    text for the fields ServiceNow knows. ``summary`` is "Found N of M fields"."""
    raw = text or ""
    today = _parse_today(vocab.get("today"))
    folded = fold(raw)
    work = tokens_of(raw)
    fields: dict[str, dict[str, Any]] = {}

    prj = _PRJ_RE.search(raw)
    prj_id = prj.group(0).upper() if prj else None

    portfolio_cands = _candidates(vocab, "portfolio", vocab.get("portfolios", []))
    type_cands = _candidates(vocab, "project_type", vocab.get("project_types", []))
    region_cands = _candidates(vocab, "region", vocab.get("regions", []))

    # exact pass (masks what it uses) then a partial pass for what is still open ----------------
    picks: dict[str, dict[str, Any]] = {}
    for name, cands in (
        ("portfolio", portfolio_cands),
        ("project_type", type_cands),
        ("region", region_cands),
    ):
        pick = _pick(work, cands)
        picks[name] = pick
        if pick["state"] in ("found", "inferred"):
            _mask(work, pick["positions"])
    for name, cands in (
        ("portfolio", portfolio_cands),
        ("project_type", type_cands),
        ("region", region_cands),
    ):
        if picks[name]["state"] == "missing":
            pick = _pick(work, cands, partial=True)
            picks[name] = pick
            if pick["state"] in ("found", "inferred"):
                _mask(work, pick["positions"])
    for name in ("project_type", "portfolio", "region"):
        fields[name] = _from_pick(picks[name], raw)

    for option_field in sorted(vocab.get("options", {})):
        fields[option_field] = _pick_option(
            work, raw, folded, option_field, vocab["options"][option_field], vocab
        )

    people = find_people(raw, vocab)
    for field in sorted(vocab.get("role_fields", {})):
        res = people.get(field)
        if res:
            fields[field] = _field(
                res["value"],
                res["state"],
                "text",
                res["score"],
                res["evidence"],
                res["candidates"],
                "Several people match - choose one" if res["state"] == "ambiguous" else None,
            )
        else:
            fields[field] = _field()

    fields["next_decision_date"] = _extract_dates(raw, today)
    reject = set()
    for cands in (portfolio_cands, type_cands, region_cands):
        for c in cands:
            reject.update(tokens_of(c["label"]))
    reject |= set(tokens_of("gate review new start create launch"))
    fields["name"] = _extract_name(raw, vocab, reject)
    fields["servicenow_project_id"] = (
        _field(prj_id, "found", "text", 1.0, prj.group(0)) if prj else _field()
    )
    fields["market"] = _field()
    fields["description"] = _field()

    portfolio_value = fields["portfolio"]["value"]
    requires_sites = False
    if servicenow and servicenow.get("portfolio"):
        portfolio_value = servicenow["portfolio"]
    for p in vocab.get("portfolios", []):
        if p["name"] == portfolio_value and p.get("requires_sites"):
            requires_sites = True
    fields["sites"] = _extract_sites(raw) if requires_sites else _field()

    if servicenow:
        _apply_servicenow(fields, servicenow, vocab, prj_id)

    if not fields["description"]["value"]:
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(raw.split()))
        desc = " ".join(s for s in sentences[:2] if s)[:400]
        if desc and len(raw.split()) >= 30:
            fields["description"] = _field(desc, "inferred", "text", 0.5, desc[:200])

    found = sum(1 for f in fields.values() if f["state"] in ("found", "inferred"))
    return IntakeExtraction(
        fields=fields,
        servicenow_project_id=prj_id,
        summary=f"Found {found} of {len(fields)} fields",
    )


def _apply_servicenow(
    fields: dict[str, dict[str, Any]],
    record: Mapping[str, Any],
    vocab: Mapping[str, Any],
    prj_id: str | None,
) -> None:
    allowed: dict[str, set[str]] = {
        "project_type": {_entry_name(p) for p in vocab.get("project_types", [])},
        "portfolio": {_entry_name(p) for p in vocab.get("portfolios", [])},
        "region": set(vocab.get("regions", [])),
        "investment_type": set(vocab.get("options", {}).get("investment_type", [])),
        "delivery_method": set(vocab.get("options", {}).get("delivery_method", [])),
    }
    note = f"From ServiceNow {prj_id}" if prj_id else "From ServiceNow"
    for key in (
        "name",
        "project_type",
        "portfolio",
        "region",
        "market",
        "investment_type",
        "delivery_method",
        "description",
    ):
        value = record.get(key)
        if value in (None, ""):
            continue
        if key in allowed and value not in allowed[key]:
            if fields[key]["state"] == "missing":
                fields[key] = _field(
                    None, "missing", None, 0.0, None, None, "ServiceNow value not in the list"
                )
            continue
        fields[key] = _field(
            value,
            "found",
            "servicenow",
            1.0,
            f"ServiceNow {prj_id}" if prj_id else None,
            None,
            note,
        )
    pm_id = record.get("pm_user_id")
    pm_name = record.get("pm")
    pm_field = next((f for f, role in vocab.get("role_fields", {}).items() if role == "PM"), None)
    if pm_field is None:
        return
    if not pm_id and pm_name:
        for u in sorted(vocab.get("users", []), key=lambda x: x["id"]):
            if u["role"] == "PM" and fold(u["name"]).strip() == fold(str(pm_name)).strip():
                pm_id = u["id"]
                break
    if pm_id:
        fields[pm_field] = _field(
            pm_id,
            "found",
            "servicenow",
            1.0,
            f"ServiceNow {prj_id}" if prj_id else None,
            None,
            note,
        )


# ---------------------------------------------------------------------------------------------
# parse_command
# ---------------------------------------------------------------------------------------------
MAX_CLAUSES = 5
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "on",
        "in",
        "at",
        "by",
        "with",
        "and",
        "or",
        "is",
        "are",
        "be",
        "please",
        "can",
        "could",
        "would",
        "you",
        "me",
        "my",
        "we",
        "us",
        "i",
        "it",
        "this",
        "that",
        "these",
        "those",
        "from",
        "as",
        "do",
        "does",
        "did",
        "will",
        "should",
        "shall",
        "about",
        "so",
        "if",
        "then",
        "than",
        "also",
        "just",
        "have",
        "has",
        "had",
        "get",
        "got",
        "let",
        "make",
        "need",
        "want",
        "like",
        "some",
        "any",
        "all",
        "every",
        "each",
    ]
)
_ITEM_ID = re.compile(r"\b([A-Za-z]{1,6}\d{0,3}-\d{1,4})\b")
_TR_ID = re.compile(r"\bTR-\d{1,6}\b", re.IGNORECASE)
_NON_ITEM_PREFIXES = ("TR", "PRJ", "CON", "ACT", "EX", "EVD", "APR", "DEF", "CR", "EV")
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

_REFUSALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "bypass",
        re.compile(
            r"\b(?:act\s+as|pretend|impersonate|bypass|ignore\s+(?:the\s+)?(?:rules|permissions|checks)|"
            r"as\s+if\s+i\s+(?:am|were)|on\s+behalf\s+of\s+the|you\s+are\s+now|override\s+(?:the\s+)?(?:rules|permissions))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "delete_data",
        re.compile(
            r"^\W*(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:delete|erase|purge|wipe|clear|drop|reset)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "send_message",
        re.compile(
            r"^\W*(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:send|email|mail|post)\b|\bsend\b.*\b(?:now|immediately|right\s+away)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "record_decision",
        re.compile(
            r"\b(?:approve[ds]?|reject(?:ed)?|sign(?:ed)?[\s-]?off|decline[ds]?|"
            r"accept\s+(?:this\s+|the\s+|that\s+)?(?:evidence|risk|exception|tier|gate|condition|ocet|support\s+model)|"
            r"confirm\s+(?:the\s+)?tier|close\s+(?:the\s+)?(?:con-?\d+|condition|gate|risk|exception)|"
            r"mark(?:ed)?\b.*\b(?:compliant|non[\s-]?compliant|not\s+compliant|approved)|"
            r"set\b.*\bdesign\s+effectiveness)\b",
            re.IGNORECASE,
        ),
    ),
)
_CONFIG_VERB = r"add|create|new|change|rename|edit|configure|delete|remove|set\s+up|enable|disable"


def split_clauses(message: str, verbs: Sequence[str] = ()) -> list[str]:
    """Clauses of a message: split on ``;``, newlines, ``. ``, `` and then `` and `` and `` before a verb."""
    text = message.replace("\r", "\n")
    parts = re.split(
        r"[;\n]+|(?<=[.!?])\s+(?=\S)|\band\s+then\b|\bthen\b(?=\s+[a-z])", text, flags=re.IGNORECASE
    )
    out: list[str] = []
    verb_re = (
        re.compile(
            r"\s+and\s+(?=(?:" + "|".join(map(re.escape, sorted(verbs))) + r")\b)", re.IGNORECASE
        )
        if verbs
        else None
    )
    for part in parts:
        pieces = verb_re.split(part) if verb_re else [part]
        out.extend(p.strip(" ,.-•*\t") for p in pieces if p and p.strip(" ,.-•*\t"))
    return [c for c in out if len(c) >= 3]


def _cue_sets(
    catalog: Sequence[Mapping[str, Any]], names: set[str]
) -> tuple[dict[str, set[str]], Counter[str]]:
    cues: dict[str, set[str]] = {}
    for entry in catalog:
        words: set[str] = set()
        sources = [*entry.get("examples", []), entry.get("label", ""), *entry.get("cues", [])]
        for source in sources:
            if str(source).startswith("("):
                continue
            for w in tokens_of(str(source)):
                if (
                    len(w) >= 3
                    and w not in _STOP
                    and not any(c.isdigit() for c in w)
                    and w not in names
                ):
                    words.add(w)
        cues[entry["intent"]] = words
    df: Counter[str] = Counter()
    for words in cues.values():
        df.update(words)
    return cues, df


def _name_tokens(vocab: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    for u in vocab.get("users", []):
        names.update(tokens_of(u["name"]))
    for t in vocab.get("transitions", []):
        names.update(tokens_of(t["name"]))
    for p in vocab.get("portfolios", []):
        names.update(tokens_of(_entry_name(p)))
    return names


def _find_transition(clause: str, tokens: list[str], vocab: Mapping[str, Any]) -> dict[str, Any]:
    """Transition by id (TR-0001) or by a distinctive part of its name (longest shared n-gram)."""
    transitions = vocab.get("transitions", [])
    m = _TR_ID.search(clause)
    if m:
        wanted = m.group(0).upper()
        for t in transitions:
            if t["id"].upper() == wanted:
                return {"state": "found", "value": t["id"], "candidates": []}
        return {"state": "unknown", "value": wanted, "candidates": []}
    best: dict[str, int] = {}
    stop = _STOP | {
        "transition",
        "project",
        "item",
        "action",
        "gate",
        "review",
        "status",
        "update",
        "evidence",
        "owner",
        "note",
    }
    for t in transitions:
        ntoks = tokens_of(t["name"])
        top = 0
        for size in range(min(4, len(ntoks)), 0, -1):
            for i in range(len(ntoks) - size + 1):
                gram = ntoks[i : i + size]
                if size == 1 and (len(gram[0]) < 5 or gram[0] in stop):
                    continue
                if _score(tokens, gram)[0] == 1.0:
                    top = max(top, sum(len(g) for g in gram))
        if top:
            best[t["id"]] = top
    if not best:
        return {"state": "missing", "value": None, "candidates": []}
    peak = max(best.values())
    winners = sorted(tid for tid, score in best.items() if score == peak)
    if len(winners) == 1:
        return {"state": "found", "value": winners[0], "candidates": []}
    names = {t["id"]: t["name"] for t in transitions}
    return {
        "state": "ambiguous",
        "value": None,
        "candidates": [{"value": w, "label": f"{names[w]} ({w})"} for w in winners],
    }


def _find_items(clause: str) -> list[str]:
    out: list[str] = []
    for m in _ITEM_ID.finditer(clause):
        value = m.group(1).upper()
        prefix = re.match(r"[A-Z]+", value)
        if prefix and prefix.group(0) in _NON_ITEM_PREFIXES and not re.match(r"^[A-Z]+\d", value):
            continue
        if value not in out:
            out.append(value)
    return out


def _find_gate(tokens: list[str], vocab: Mapping[str, Any]) -> str | None:
    cands = []
    for g in vocab.get("gates", []):
        short = g.get("short", "")
        # "SG4 (AtD)" is also known as "AtD" (the text inside the brackets)
        phrases = [g["code"], short, *re.findall(r"\(([^)]+)\)", short)]
        cands.append({"value": g["code"], "label": g["code"], "phrases": [p for p in phrases if p]})
    pick = _pick(list(tokens), cands)
    return pick["value"] if pick["state"] == "found" else None


def _status_of(tokens: list[str], vocab: Mapping[str, Any]) -> str | None:
    best: tuple[int, str] | None = None
    for entry in vocab.get("status_words", []):
        ptoks = tokens_of(entry["phrase"])
        if ptoks and _score(tokens, ptoks)[0] == 1.0 and (best is None or len(ptoks) > best[0]):
            best = (len(ptoks), entry["status"])
    return best[1] if best else None


def _severity_of(tokens: list[str], vocab: Mapping[str, Any]) -> str | None:
    for sev in vocab.get("severities", []):
        if tokens_of(sev) and _score(tokens, tokens_of(sev))[0] == 1.0:
            return sev
    return None


def _priority_of(tokens: list[str], vocab: Mapping[str, Any]) -> str | None:
    for pr in vocab.get("priorities", []):
        if tokens_of(pr) and _score(tokens, tokens_of(pr))[0] == 1.0:
            return pr
    return None


def _because(clause: str) -> str | None:
    m = re.search(r"\b(?:because|since|as)\b\s+(?P<t>.+)$", clause, re.IGNORECASE)
    return m.group("t").strip(" .") if m else None


def _title_from(clause: str, owner_name: str | None, dates: list[dict[str, Any]]) -> str:
    title = clause
    for d in reversed(dates):
        if d["end"] <= len(title):
            # drop the date and the word that introduced it ("by 2027-01-15 on TR-1" -> "on TR-1")
            head = re.sub(
                r"\b(?:by|due|before|until|on)\s*$", "", title[: d["start"]], flags=re.IGNORECASE
            )
            title = head + " " + title[d["end"] :]
    title = re.sub(r"\b(?:by|due|before|until|on)\s*$", "", title.strip(), flags=re.IGNORECASE)
    title = re.sub(
        r"^\W*(?:please\s+)?(?:can\s+you\s+)?(?:ask|tell|get|have|remind)\s+",
        "",
        title.strip(),
        flags=re.IGNORECASE,
    )
    title = re.sub(r"^\W*(?:an?\s+)?action\s+(?:for|to)\s+", "", title, flags=re.IGNORECASE)
    if owner_name:
        parts = owner_name.split()
        pattern = (
            r"^\W*(?:"
            + r"[\s.-]+".join(re.escape(p) for p in parts)
            + r"|"
            + re.escape(parts[0])
            + r")\b\s*(?:to\b|:|-)?\s*"
        )
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+(?:by|due)\s*$", "", title.strip(), flags=re.IGNORECASE).strip(" ,.:;-")
    title = " ".join(title.split())
    if not title:
        title = " ".join(clause.split())
    return (title[:1].upper() + title[1:])[:120]


def _lens_status_note(clause: str) -> str | None:
    m = re.search(r"\b(?:note|comment)\b[^:\n]*:\s*(?P<t>.+)$", clause, re.IGNORECASE)
    if m:
        return m.group("t").strip(" .")
    because = _because(clause)
    if because:
        return because
    m = re.search(r"[,–-]\s+(?P<t>[^,]{3,})$", clause)
    if m:
        return m.group("t").strip(" .")
    m = re.search(r":\s*(?P<t>.+)$", clause)
    return m.group("t").strip(" .") if m else None


def _facts(
    clause: str, vocab: Mapping[str, Any], context: Mapping[str, Any], today: date
) -> dict[str, Any]:
    tokens = tokens_of(clause)
    people = find_people(clause, vocab)
    role_fields = vocab.get("role_fields", {})
    user_by_id = {u["id"]: u for u in vocab.get("users", [])}
    mentioned = {
        f: r for f, r in people.items() if r["state"] in ("found", "inferred") and r["value"]
    }
    ambiguous_people = {f: r for f, r in people.items() if r["state"] == "ambiguous"}
    # owner candidates: every mentioned user, any role (first mention first)
    owners = [user_by_id[r["value"]] for r in mentioned.values() if r["value"] in user_by_id]
    # users with no picker (Planner...) are matched too: look at the full user list by name
    folded = fold(clause)
    extra: list[dict[str, Any]] = []
    first_names = Counter(
        tokens_of(u["name"])[0] for u in vocab.get("users", []) if tokens_of(u["name"])
    )
    for u in sorted(vocab.get("users", []), key=lambda x: x["id"]):
        if u["role"] in role_fields.values() or not tokens_of(u["name"]):
            continue
        full = re.search(
            r"\b" + r"[\s.-]+".join(re.escape(fold(w)) for w in u["name"].split()) + r"\b", folded
        )
        first = tokens_of(u["name"])[0]
        by_first = first_names[first] == 1 and re.search(
            r"\b" + re.escape(fold(u["name"].split()[0])) + r"\b", folded
        )
        if full or by_first:
            m = full or by_first
            extra.append({"user": u, "pos": m.start() if m else 0})
    ordered = [(fold(clause).find(fold(u["name"].split()[0])), u) for u in owners] + [
        (e["pos"], e["user"]) for e in extra
    ]
    ordered.sort(key=lambda p: (p[0] if p[0] >= 0 else 10**6, p[1]["id"]))
    users = [u for _, u in ordered]
    dates = parse_dates(clause, today)
    return {
        "tokens": tokens,
        "transition": _find_transition(clause, tokens, vocab),
        "items": _find_items(clause),
        "users": users,
        "ambiguous_people": ambiguous_people,
        "dates": dates,
        "status": _status_of(tokens, vocab),
        "severity": _severity_of(tokens, vocab),
        "priority": _priority_of(tokens, vocab),
        "gate": _find_gate(tokens, vocab),
        "url": (_URL_RE.search(clause).group(0).rstrip(".,;)") if _URL_RE.search(clause) else None),
        "because": _because(clause),
        "overdue": bool(re.search(r"\b(?:overdue|late|past\s+due)\b", folded)),
        "people": people,
    }


def _argument_found(arg: str, facts: Mapping[str, Any], intent: str) -> bool:
    name = arg.rstrip("?")
    if name in ("item_id", "item_ids"):
        return bool(facts["items"])
    if name == "owner_user_id":
        return bool(facts["users"])
    if name == "due_date":
        return bool(facts["dates"])
    if name == "transition":
        return facts["transition"]["state"] in ("found", "ambiguous")
    if name == "gate":
        return facts["gate"] is not None
    if name == "status":
        return facts["status"] is not None
    if name == "gap_severity":
        return facts["severity"] is not None
    if name == "url | text":
        return facts["url"] is not None
    return False


def _refusal_intent(
    clause: str,
    facts: Mapping[str, Any],
    catalog_intents: set[str],
    cfg_nouns: Sequence[str],
) -> str | None:
    folded = fold(clause)
    for intent, rx in _REFUSALS:
        if intent not in catalog_intents:
            continue
        if intent == "send_message" and re.match(r"^\W*(?:ask|tell|remind)\b", folded):
            continue
        if rx.search(clause):
            return intent
    about_transition = bool(_TR_ID.search(clause)) or bool(facts["items"])
    if (
        not about_transition
        and facts["transition"]["state"] == "found"
        and not re.search(r"\b(?:add|create|new|called|named)\b", folded)
    ):
        about_transition = True
    if "change_config" in catalog_intents and not about_transition and cfg_nouns:
        nouns = "|".join(
            r"\s+".join(re.escape(w) for w in noun.split())
            for noun in sorted(cfg_nouns, key=len, reverse=True)
        )
        pattern = (
            r"\b(?:"
            + _CONFIG_VERB
            + r")\s+(?:(?:an?|the|new|another|some|my|our|all)\s+){0,3}(?:"
            + nouns
            + r")s?\b"
        )
        if re.search(pattern, folded):
            return "change_config"
    return None


def parse_command(
    message: str,
    catalog: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[ParsedCommand]:
    """Deterministic command parser for free text.

    1. Split the message into clauses on ``;``, newlines, `` and then ``, `` and `` before a verb and
       ``. `` (at most 5 clauses are parsed; one more is returned when the message had more, so the
       caller can tell that the rest was ignored).
    2. Intent per clause = highest score over ``catalog`` entries: cue words (derived from the catalog
       examples, labels and ``cues`` at call time, weighted by how few intents share them), +3 for each
       catalog example whose significant words are all present, +1 per argument actually found.
       Refusal intents win on their cue words (approve, sign off, accept evidence, close a condition,
       delete, send now, act as) and on a request to change project types, portfolios or users.
       Score < 2.5 -> clause ignored.
    3. Arguments are resolved against ``vocab`` with the same matching as ``extract_intake``:
       transition by id ``TR-\\d+`` or name, item ids ``[A-Za-z]+\\d*-\\d+``, users by name, gate by
       code or short name, dates (ISO, ``d Mon``, ``Mon d``, ``dd/mm``, today / tomorrow,
       ``(next )?<weekday>``, ``in N days|weeks``, ``end of month``), priority and status words from
       the vocabulary.
    4. ``missing`` = required args of the catalog entry that were not found; ``ambiguous`` = args with
       several candidates. Never returns an intent absent from ``catalog``; nothing found -> [].
    Same input -> same output."""
    today = _parse_today(context.get("today") or vocab.get("today"))
    spec = {e["intent"]: e for e in catalog}
    catalog_intents = set(spec)
    names = _name_tokens(vocab)
    cues, df = _cue_sets(catalog, names)
    verbs = {
        tokens_of(str(e.get("label", "")))[0] for e in catalog if tokens_of(str(e.get("label", "")))
    }
    for entry in catalog:
        for example in entry.get("examples", []):
            if not str(example).startswith("(") and tokens_of(str(example)):
                verbs.add(tokens_of(str(example))[0])
    verbs = {v for v in verbs if len(v) >= 3 and v not in _STOP}
    clauses = split_clauses(message, sorted(verbs))
    cfg_nouns = list(spec.get("change_config", {}).get("cues", []))
    skip = {"status", "blocking", "owner", "glossary", "red_transitions"}  # answered by chat()

    commands: list[ParsedCommand] = []
    for clause in clauses[: MAX_CLAUSES + 1]:
        facts = _facts(clause, vocab, context, today)
        refusal = _refusal_intent(clause, facts, catalog_intents, cfg_nouns)
        ctokens = set(facts["tokens"])
        if refusal:
            commands.append(
                ParsedCommand(
                    intent=refusal,
                    arguments={"items": facts["items"], "transition": facts["transition"]["value"]},
                    missing=[],
                    ambiguous={},
                    confidence=0.9,
                    excerpt=clause[:300],
                )
            )
            continue
        scores: list[tuple[float, int, str]] = []
        changes_hint = _transition_changes(clause, facts, vocab)
        for order, entry in enumerate(catalog):
            intent = entry["intent"]
            if intent in skip or entry.get("result") == "refusal":
                continue
            score = sum(2.0 / df[w] for w in cues.get(intent, set()) & ctokens)
            for example in entry.get("examples", []):
                if str(example).startswith("("):
                    continue
                sig = {w for w in tokens_of(str(example)) if w not in _STOP and w not in names}
                if sig and sig <= ctokens:
                    score += 3.0
            for arg in entry.get("args", []):
                if _argument_found(arg, facts, intent):
                    score += 1.0 if not arg.endswith("?") else 0.5
            if intent == "create_action" and facts["users"] and facts["dates"]:
                score += 2.0
            if (
                intent == "update_item"
                and facts["items"]
                and (facts["status"] or facts["severity"])
            ):
                score += 1.5
            if intent == "update_transition" and not facts["items"] and changes_hint:
                score += 3.5
            if intent == "add_evidence" and facts["url"]:
                score += 1.5
            scores.append((score, -order, intent))
        if not scores:
            continue
        scores.sort(reverse=True)
        best_score, _, intent = scores[0]
        if best_score < 2.5:
            continue
        commands.append(
            _build_command(spec[intent], intent, clause, facts, vocab, context, today, best_score)
        )
    return commands


def _build_command(
    entry: Mapping[str, Any],
    intent: str,
    clause: str,
    facts: dict[str, Any],
    vocab: Mapping[str, Any],
    context: Mapping[str, Any],
    today: date,
    score: float,
) -> ParsedCommand:
    args: dict[str, Any] = {}
    missing: list[str] = []
    ambiguous: dict[str, list[dict[str, str]]] = {}
    tr = facts["transition"]
    if tr["state"] == "found":
        args["transition_id"] = tr["value"]
    elif tr["state"] == "ambiguous":
        ambiguous["transition"] = tr["candidates"]
    elif tr["state"] == "unknown":
        args["unknown_transition"] = tr["value"]
    items = facts["items"] or (
        [context["item_id"]]
        if context.get("item_id")
        and not facts["transition"]["value"]
        and re.search(r"\bthis\s+item\b", fold(clause))
        else []
    )
    first_date = facts["dates"][0]["date"].isoformat() if facts["dates"] else None
    owner = facts["users"][0] if facts["users"] else None
    amb_people = facts["ambiguous_people"]

    if intent == "create_action":
        if owner:
            args["owner_user_id"] = owner["id"]
        elif amb_people:
            ambiguous["owner_user_id"] = next(iter(amb_people.values()))["candidates"]
        if first_date:
            args["due_date"] = first_date
        args["item_ids"] = items
        if facts["priority"]:
            args["priority"] = facts["priority"]
        args["title"] = _title_from(clause, owner["name"] if owner else None, facts["dates"])
    elif intent == "draft_chaser":
        args["item_ids"] = items
        if owner:
            args["owner_user_id"] = owner["id"]
        if facts["overdue"]:
            args["overdue"] = True
    elif intent == "request_inputs":
        pass
    elif intent == "request_exception":
        if items:
            args["item_id"] = items[0]
        args["text"] = (facts["because"] or " ".join(clause.split())).strip()
    elif intent == "request_approval":
        if facts["gate"]:
            args["gate"] = facts["gate"]
    elif intent == "accept_applicability":
        folded = fold(clause)
        applies = None
        if re.search(
            r"\b(?:does\s*n[o']?t|do\s*n[o']?t|not)\s+(?:apply|applicable|relevant)|\bn/?a\b|out\s+of\s+scope|no\s+longer\s+applies",
            folded,
        ):
            applies = "No"
        elif re.search(r"\b(?:applies|apply|applicable|in\s+scope|relevant)\b", folded):
            applies = "Yes"
        if items and applies:
            args["decisions"] = [
                {"item_id": i, "applies": applies, "reason": facts["because"]} for i in items
            ]
    elif intent == "update_item":
        if items:
            args["item_id"] = items[0]
        if owner and re.search(r"\b(?:assign|give|owner|owned|reassign|to)\b", fold(clause)):
            args["owner_user_id"] = owner["id"]
        elif amb_people:
            ambiguous["owner_user_id"] = next(iter(amb_people.values()))["candidates"]
        if facts["status"]:
            args["status"] = facts["status"]
        if facts["severity"]:
            args["gap_severity"] = facts["severity"]
            args.setdefault("status", "Gap")
        note = (
            _lens_status_note(clause)
            if (
                re.search(r"\bnote\b|\bcomment\b", fold(clause))
                or args.get("status") == "Gap"
                or facts["because"]
            )
            else None
        )
        if note:
            args["note"] = note
    elif intent == "add_evidence":
        if items:
            args["item_id"] = items[0]
        if facts["url"]:
            args["url"] = facts["url"]
            tail = clause.split(facts["url"])[0]
            title = re.sub(
                r"^\W*(?:please\s+)?(?:add|attach|link)\s+(?:an?\s+)?(?:evidence|link|document)?\s*(?:to|for|on)?\s*",
                "",
                tail,
                flags=re.IGNORECASE,
            )
            title = _ITEM_ID.sub("", title).strip(" :-,.")
            args["title"] = title or "Evidence link"
    elif intent == "update_transition":
        args["changes"] = _transition_changes(clause, facts, vocab)
    elif intent == "assess_gate_readiness":
        if facts["gate"]:
            args["gate"] = facts["gate"]
    elif intent == "create_leadership_update":
        folded = fold(clause)
        portfolios = [_entry_name(p) for p in vocab.get("portfolios", [])]
        pick = _pick(
            list(facts["tokens"]), _candidates(vocab, "portfolio", portfolios), partial=True
        )
        if pick["state"] in ("found", "inferred"):
            args["scope"], args["scope_id"] = "portfolio", pick["value"]
        elif tr["state"] == "found":
            args["scope"], args["scope_id"] = "transition", tr["value"]
        elif re.search(r"\b(?:all|every|everything|whole|overall|portfolio|global)\b", folded):
            args["scope"] = "all"
    elif intent == "open_module":
        folded_tokens = facts["tokens"]
        for module in vocab.get("modules", []):
            for phrase in module.get("phrases", []):
                if _score(folded_tokens, tokens_of(phrase))[0] == 1.0:
                    args["module"] = module["key"]
                    break
            if "module" in args:
                break

    db_resolved = {"version_id", "line_ids", "changes", "decisions", "text", "title"}
    for arg in entry.get("args", []):
        name = arg.rstrip("?")
        if arg.endswith("?") or name in ("version_id", "line_ids"):
            continue
        if name == "transition":
            continue  # resolved with the context by the caller
        if name == "url | text":
            if "url" not in args and "text" not in args:
                missing.append("url")
            continue
        if name == "gate":
            continue  # defaults to the decision gate of the transition (caller)
        key = {"item_ids": "item_ids", "item_id": "item_id"}.get(name, name)
        value = args.get(key)
        if name in ambiguous or (value not in (None, "", [], {})):
            if name in ambiguous and not value:
                missing.append(name)
            continue
        if name in db_resolved and name not in ("changes", "decisions", "text", "title"):
            continue
        missing.append(name)
    if intent == "update_item" and not any(
        k in args for k in ("owner_user_id", "note", "status", "gap_severity")
    ):
        missing.append("changes")
    return ParsedCommand(
        intent=intent,
        arguments=args,
        missing=list(dict.fromkeys(missing)),
        ambiguous=ambiguous,
        confidence=round(min(1.0, score / 8.0), 2),
        excerpt=clause[:300],
    )


def _transition_changes(
    clause: str, facts: Mapping[str, Any], vocab: Mapping[str, Any]
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    folded = fold(clause)
    if facts["dates"] and re.search(r"\b(?:decision|go[\s-]?live|deadline|launch|gate)\b", folded):
        changes["next_decision_date"] = facts["dates"][0]["date"].isoformat()
    role_phrases = _role_phrases(vocab)
    role_fields = vocab.get("role_fields", {})
    field_of_role = {role: field for field, role in role_fields.items()}
    if facts["users"]:
        user = facts["users"][0]
        cued = [
            role
            for role, phrases in role_phrases.items()
            if any(_score(facts["tokens"], p)[0] == 1.0 for p in phrases)
        ]
        # the role named in the sentence must be the user's own role (a person cannot fill another role)
        if user["role"] in cued and user["role"] in field_of_role:
            changes[field_of_role[user["role"]]] = user["id"]
    for field, kind, items in (
        ("project_type", "project_type", vocab.get("project_types", [])),
        ("portfolio", "portfolio", vocab.get("portfolios", [])),
        ("region", "region", vocab.get("regions", [])),
    ):
        label_words = tokens_of(field.replace("_", " "))
        if _score(facts["tokens"], label_words)[0] == 1.0:
            pick = _pick(list(facts["tokens"]), _candidates(vocab, kind, items))
            if pick["state"] == "found":
                changes[field] = pick["value"]
    return changes
