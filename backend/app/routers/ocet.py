"""OCET module (FR-060, BR-070, spec 8.10 and 9).

Routers commit the session after each mutation. Errors follow app.errors (403 permission,
404 missing, 409 business rule with ``reasons``, 422 validation).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import IdPath, get_current_user, get_db, require
from app.domain import ocet as domain
from app.errors import NotFound
from app.models import Transition, User
from app.permissions import Perm
from app.schemas.common import ErrorOut
from app.schemas.ocet import (
    OcetCompareOut,
    OcetOut,
    OcetSaveIn,
    RequestInputsIn,
    RequestInputsOut,
)

router = APIRouter(tags=["ocet"], dependencies=[Depends(get_current_user)])

_ERR = {
    403: {"model": ErrorOut},
    404: {"model": ErrorOut},
    409: {"model": ErrorOut},
    422: {"model": ErrorOut},
}


@router.get("/transitions/{transition_id}/ocet", response_model=OcetOut, responses=_ERR)
def get_ocet(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OcetOut:
    """Full OCET view of the CURRENT version (any authenticated role). 404 when the transition
    does not exist or has no OCET yet (the UI then offers ``POST /transitions/{id}/ocet``).
    """
    return domain.get_ocet_view(db, transition_id, user)


@router.post(
    "/transitions/{transition_id}/ocet",
    response_model=OcetOut,
    status_code=201,
    responses=_ERR,
)
def create_ocet(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_OCET)),
) -> OcetOut:
    """Create an empty estimate (v1 Draft). 403 without EDIT_OCET, 404 unknown transition, 409
    when an estimate already exists.
    """
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    estimate = domain.create_estimate(db, transition, user)
    out = domain.build_version_out(db, estimate.versions[0], user)
    db.commit()
    return out


@router.put("/ocet/versions/{version_id}/lines", response_model=OcetOut, responses=_ERR)
def save_lines(
    version_id: IdPath,
    payload: OcetSaveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_OCET)),
) -> OcetOut:
    """Bulk save lines of a version (spec 9). 409 when not Draft / Inputs pending; 422 for
    validation failures. Returns the refreshed OcetOut.
    """
    version = domain.save_lines(db, domain.get_version(db, version_id), payload, user)
    out = domain.build_version_out(db, version, user)
    db.commit()
    return out


@router.post("/ocet/versions/{version_id}/submit", response_model=OcetOut, responses=_ERR)
def submit_version(
    version_id: IdPath,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_OCET)),
) -> OcetOut:
    """Submit for approval: chain Planner -> OLM. 409 with ``reasons`` when blocked."""
    version = domain.submit_version(db, domain.get_version(db, version_id), user)
    out = domain.build_version_out(db, version, user)
    db.commit()
    return out


@router.post(
    "/transitions/{transition_id}/ocet/new-version",
    response_model=OcetOut,
    status_code=201,
    responses=_ERR,
)
def new_version(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_OCET)),
) -> OcetOut:
    """Create vN+1 (Draft) by copying the current version's lines."""
    version = domain.create_new_version(db, transition_id, user)
    out = domain.build_version_out(db, version, user)
    db.commit()
    return out


@router.post(
    "/ocet/versions/{version_id}/request-inputs",
    response_model=RequestInputsOut,
    responses=_ERR,
)
def request_inputs(
    version_id: IdPath,
    payload: RequestInputsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.EDIT_OCET)),
) -> RequestInputsOut:
    """Request missing inputs: lines -> Requested and one Orion draft per input owner (never sent
    automatically).
    """
    version = domain.get_version(db, version_id)
    draft_ids, requested = domain.request_inputs(db, version, payload.line_ids, user)
    db.commit()
    return RequestInputsOut(draft_ids=draft_ids, lines_requested=requested)


@router.get("/ocet/compare", response_model=OcetCompareOut, responses=_ERR)
def compare(
    from_version: int = Query(
        alias="from", ge=1, le=2**31 - 1, description="OcetVersion id (older)"
    ),
    to_version: int = Query(alias="to", ge=1, le=2**31 - 1, description="OcetVersion id (newer)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OcetCompareOut:
    """Diff of two versions of the same estimate. 404 unknown id; 422 different estimates."""
    return domain.compare_versions(db, from_version, to_version, user)
