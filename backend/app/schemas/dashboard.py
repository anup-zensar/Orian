"""GET /dashboard – role-aware home page (spec §8.1, FR-010)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.audit import AuditEventOut
from app.schemas.common import KpiTileOut, UserOut


class WorkItemOut(BaseModel):
    """One row of "My work": an item I own, an action I own, or an approval step waiting for me."""

    kind: str  # item | action | approval
    id: str  # playbook item id (S45-014), action id (ACT-001) or approval request id (APR-0001)
    title: str
    transition_id: str
    transition_name: str
    status: str
    lens: str | None  # items only
    gap_severity: str | None  # items in Gap / Non-compliant
    due_label: str  # e.g. "AtD · 21 days", "Due 2026-11-21", "Waiting 1 day"
    due_date: date | None  # sort key (decision date for items, due date for actions)
    link: str  # deep link route, e.g. /transitions/TR-0001/assessment?item=S45-014


class PortfolioTileOut(BaseModel):
    """LEADERSHIP sees portfolio summary tiles instead of "My work" (spec §8.1)."""

    portfolio: str
    transitions: int
    red: int
    amber: int
    green: int
    grey: int
    average_readiness: int | None
    decisions_14d: int
    critical_gaps: int


class DashboardOut(BaseModel):
    user: UserOut
    today: date
    kpis: list[KpiTileOut]
    my_work: list[
        WorkItemOut
    ]  # most urgent first, at most 200 rows; my_work_total counts all (empty for LEADERSHIP)
    my_work_total: int
    portfolio_tiles: list[PortfolioTileOut]  # LEADERSHIP only, otherwise empty
    recent_activity: list[AuditEventOut]  # last 10 audit events whose transition is one of mine
