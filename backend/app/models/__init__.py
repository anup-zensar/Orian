"""SQLAlchemy models (spec §6). Importing this package registers every table on ``Base.metadata``."""

from app.models.gates import ApprovalRequest, ApprovalStep, GateReview
from app.models.modules import OcetEstimate, OcetLine, OcetVersion, SupportModel
from app.models.orion import (
    AuditEvent,
    LeadershipUpdate,
    Notification,
    OrionDraft,
    OrionProposal,
    OutboxMessage,
    ReminderRun,
)
from app.models.playbook import EvalTarget, PlaybookItem
from app.models.reference import (
    ApprovalChainConfig,
    AppSetting,
    FlavourRule,
    Portfolio,
    ReferenceData,
    ReminderRule,
    User,
)
from app.models.transition import AIProfile, TierAssessment, Transition, TransitionItem
from app.models.work import (
    Action,
    Condition,
    EvalResult,
    Evidence,
    ExceptionRecord,
    HypercareDefect,
    Risk,
)

__all__ = [
    "AIProfile",
    "Action",
    "AppSetting",
    "ApprovalChainConfig",
    "ApprovalRequest",
    "ApprovalStep",
    "AuditEvent",
    "Condition",
    "EvalResult",
    "EvalTarget",
    "Evidence",
    "ExceptionRecord",
    "FlavourRule",
    "GateReview",
    "HypercareDefect",
    "LeadershipUpdate",
    "Notification",
    "OcetEstimate",
    "OcetLine",
    "OcetVersion",
    "OrionDraft",
    "OrionProposal",
    "OutboxMessage",
    "PlaybookItem",
    "Portfolio",
    "ReferenceData",
    "ReminderRule",
    "ReminderRun",
    "Risk",
    "SupportModel",
    "TierAssessment",
    "Transition",
    "TransitionItem",
    "User",
]
