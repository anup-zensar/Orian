"""AI tiering (BR-011, spec 7.2). PURE: no DB, no I/O.

Deterministic proposal from the intake fields (audience, write actions, sensitive data) and the five
tier questions TQ1..TQ5. Rules are evaluated in order; the first rule that matches decides:

1. TQ2 yes or TQ3 yes or sensitive data "SOX / MC"                                  -> Tier 4
2. TQ1 yes or audience "External" or sensitive data "Personal sensitive"
   or write actions "Yes"                                                            -> Tier 3
3. TQ5 yes                                                                            -> Tier 1
4. TQ4 yes                                                                            -> Tier 2
5. otherwise                                                                          -> Tier 3

The rationale lists the intake facts followed by the facts that triggered the deciding rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

TIER_QUESTION_IDS: tuple[str, ...] = ("TQ1", "TQ2", "TQ3", "TQ4", "TQ5")

AUDIENCE_EXTERNAL = "External"
SENSITIVE_PERSONAL = "Personal sensitive"
SENSITIVE_SOX_MC = "SOX / MC"
WRITE_YES = "Yes"
WRITE_NO = "No"

_AUDIENCE_FACT = {
    "Internal department": "Internal audience",
    "Enterprise": "Enterprise audience",
    AUDIENCE_EXTERNAL: "External audience",
}
_SENSITIVE_FACT = {
    "No": "No sensitive data",
    SENSITIVE_PERSONAL: "Personal sensitive data",
    SENSITIVE_SOX_MC: "SOX / MC data",
}


@dataclass(frozen=True)
class TierProposal:
    tier: int
    rationale: list[str] = field(default_factory=list)


def unknown_question_ids(answers: Mapping[str, bool]) -> list[str]:
    """Answer keys that are not TQ1..TQ5 (callers turn these into a 422)."""
    return [key for key in answers if key not in TIER_QUESTION_IDS]


def _intake_facts(
    audience: str | None, write_actions: str | None, sensitive_data: str | None
) -> list[str]:
    facts: list[str] = []
    if audience:
        facts.append(_AUDIENCE_FACT.get(audience, f"Audience: {audience}"))
    if write_actions:
        facts.append("No write actions" if write_actions == WRITE_NO else "Write actions: yes")
    if sensitive_data:
        facts.append(_SENSITIVE_FACT.get(sensitive_data, f"Sensitive data: {sensitive_data}"))
    return facts


def propose_tier(
    audience: str | None,
    write_actions: str | None,
    sensitive_data: str | None,
    answers: Mapping[str, bool],
) -> TierProposal:
    """BR-011. Missing answer keys count as "no"."""

    def yes(key: str) -> bool:
        return bool(answers.get(key, False))

    rationale = _intake_facts(audience, write_actions, sensitive_data)

    tier4: list[str] = []
    if yes("TQ2"):
        tier4.append("TQ2 = yes -> Tier 4")
    if yes("TQ3"):
        tier4.append("TQ3 = yes -> Tier 4")
    if sensitive_data == SENSITIVE_SOX_MC:
        tier4.append("Sensitive data SOX / MC -> Tier 4")
    if tier4:
        return TierProposal(4, rationale + tier4)

    tier3: list[str] = []
    if yes("TQ1"):
        tier3.append("TQ1 = yes -> Tier 3")
    if audience == AUDIENCE_EXTERNAL:
        tier3.append("External audience -> Tier 3")
    if sensitive_data == SENSITIVE_PERSONAL:
        tier3.append("Personal sensitive data -> Tier 3")
    if write_actions == WRITE_YES:
        tier3.append("Write actions = Yes -> Tier 3")
    if tier3:
        return TierProposal(3, rationale + tier3)

    if yes("TQ5"):
        return TierProposal(1, rationale + ["TQ5 = yes -> Tier 1"])
    if yes("TQ4"):
        return TierProposal(2, rationale + ["TQ4 = yes -> Tier 2"])
    return TierProposal(3, rationale + ["No rule matched -> Tier 3 (conservative default)"])
