"""Checklist items: /transitions/{id}/items, PATCH /items/{id}, POST /items/bulk (FR-031, BR-030). M4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import IdPath, get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.items import (
    BulkItemsIn,
    BulkResultOut,
    ItemFilters,
    ItemListOut,
    ItemOut,
    ItemPatchIn,
)

router = APIRouter(tags=["items"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/items", response_model=ItemListOut)
def list_items(
    transition_id: str,
    filters: Annotated[ItemFilters, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemListOut:
    """Checklist for one transition (spec 8.7 a/b, FR-031). Any signed-in user.

    * 404 when the transition does not exist.
    * Before the assessment is launched (``assessment_launched_at`` null) there are no TransitionItems:
      return ``items=[]``, zero summaries and zero counts (not an error).
    * ``filters.gate`` defaults to the transition's ``current_gate``; unless ``all_gates`` is true only
      items whose ``due_gate`` is at or before it (``GATE_ORDER``) are returned. Unknown gate code: 422.
    * ``applicability`` defaults to "applies" (Applies); "excluded" = Not applicable (tier, project type,
      portfolio or manual N/A, ``excluded_by`` says which); "to_confirm"; "all".
    * ``mine`` = items owned by the current user; ``owner`` = a user id; ``q`` searches id/title/
      description/owner name. ``status`` and ``lens`` are exact matches.
    * ``summary`` always has three rows (Business, Technical, Compliance) for the EFFECTIVE gate over
      applicable items (BR-020: done / in progress / not started / open gaps / critical gaps / readiness
      percent, items covered by an open condition due after the current gate count as done-equivalent per
      the shared readiness rule). It ignores the lens/source/status/owner/q filters.
    * ``excluded_count`` / ``excluded_by_tier_count`` count the transition's Not applicable items
      (all gates) so the UI can show "N items excluded by tier".
    * Sort: due gate order, lens order (Business, Technical, Compliance), playbook ``sort_order``.
    * Per-row ``can_edit`` / ``edit_denied_reason`` are computed for the current user: Compliance items
      need ``Perm.UPDATE_C_STATUS`` (IRM), Business/Technical need ``Perm.UPDATE_BT_STATUS``
      (OR focal, PM, Architect, OLM); the reason is ``DENIAL_REASONS`` of the missing permission.
    """
    from app.domain import items

    return items.list_items(db, transition_id, filters, user)


@router.patch("/items/{item_id}", response_model=ItemOut)
def patch_item(
    item_id: IdPath,
    body: ItemPatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemOut:
    """Update one TransitionItem (``item_id`` is the integer TransitionItem.id). Only fields in
    ``body.model_fields_set`` are applied. Enforces BR-030 / spec 7.5 and writes ONE AuditEvent
    (entity "TransitionItem", action "updated", before/after of changed fields, actor_type Human).
    ``last_updated_by`` = user, ``last_updated_source`` = "Human". Orion never calls this (BR-050).

    Errors:
    * 404 item not found.
    * 403 (reason from ``DENIAL_REASONS``): status change on a Compliance item without
      ``Perm.UPDATE_C_STATUS``; status change on a B/T item without ``Perm.UPDATE_BT_STATUS``;
      ``design_effectiveness`` without ``Perm.UPDATE_C_STATUS``; ``applicability`` / N/A on a B/T item
      without ``Perm.CONFIRM_SCOPE`` (OR focal); N/A on a Compliance item without
      ``Perm.UPDATE_C_STATUS`` (IRM). Owner and note changes: ``Perm.UPDATE_BT_STATUS`` for B/T items,
      ``Perm.UPDATE_C_STATUS`` or the item's current owner for Compliance items.
    * 422 invalid input (reasons list): status not in ``STATUSES_BY_LENS[lens]``; unknown owner user;
      ``gap_severity`` not Critical/Major/Minor.
    * 409 business-rule violation (reasons list):
      - status Gap / Non-compliant needs ``gap_severity`` AND a non-empty note (given now or already on
        the item);
      - N/A / Not applicable status (or applicability "Not applicable") needs ``na_reason``; applicability
        "Not applicable" also sets the lens N/A status, applicability "Applies" restores "Not started"
        when the item was N/A;
      - "Compliant with conditions" requires ``body.condition`` (owner, due_gate, text) and creates the
        Condition via ``app.domain.conditions.create_condition`` (set_at_gate = transition.current_gate,
        actor Human); due gate must not be before the current gate;
      - "Compliant" requires design_effectiveness Yes or N/A (given now or stored);
      - the item's transition is Closed; or the assessment has not been launched.
    * Leaving a Gap status clears ``gap_severity``. Leaving "Compliant with conditions" does NOT close
      the Condition automatically. Setting Complete/Compliant on an item with an Open condition leaves the
      condition open (humans close it).
    Returns the refreshed ``ItemOut`` (can_edit computed for the caller).
    """
    from app.domain import items

    result = items.patch_item(db, item_id, body, user)
    db.commit()
    return result


@router.post("/items/bulk", response_model=BulkResultOut)
def bulk_items(
    body: BulkItemsIn,
    user: User = Depends(require(Perm.CONFIRM_SCOPE)),
    db: Session = Depends(get_db),
) -> BulkResultOut:
    """Bulk actions for the OR focal (spec 8.7 b): set owner and/or mark N/A with a reason.

    * 403 unless OR focal (``Perm.CONFIRM_SCOPE``).
    * 422 when neither ``owner_user_id`` nor ``mark_na`` is given, ``mark_na.reason`` is blank, or the owner
      user does not exist.
    * Each id is processed independently; ``skipped`` gets {id, reason} for unknown ids, items of a
      transition the user is not allowed to change, Compliance items when marking N/A (only IRM may mark
      Compliance N/A, so the OR focal cannot), and items already N/A. Others are in ``updated``.
    * One AuditEvent per updated item (Human). Marking N/A sets applicability "Not applicable", the lens
      N/A status, ``na_reason``.
    """
    from app.domain import items

    result = items.bulk_items(db, body, user)
    db.commit()
    return result
