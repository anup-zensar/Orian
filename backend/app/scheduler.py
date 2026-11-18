"""Background scheduler for the reminder engine (BR-060). Off unless REMINDER_JOB_ENABLED=true."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.config import get_settings

logger = logging.getLogger("orion.scheduler")
JOB_ID = "reminder-engine"
INTERVAL_MINUTES = 15
_scheduler: BackgroundScheduler | None = None


def run_reminder_job() -> None:
    """One scheduled run: own session, commit, never raise (the scheduler must keep ticking)."""
    from app.db import SessionLocal
    from app.domain.reminders import run_reminders

    try:
        with SessionLocal() as db:
            result = run_reminders(db, user=None, triggered_by="scheduler")
            db.commit()
        logger.info(
            "Reminder job: %s drafted, %s sent autonomously, %s duplicates skipped",
            sum(result.created.values()),
            result.sent_autonomously,
            result.skipped_duplicates,
        )
    except Exception:
        logger.exception("Reminder job failed")


def start_scheduler(app: FastAPI) -> None:
    """Start the 15-minute reminder job when ``reminder_job_enabled`` is true (default false).
    Stores the scheduler on ``app.state.scheduler``; does nothing when disabled or already running.
    """
    global _scheduler
    if not get_settings().reminder_job_enabled or _scheduler is not None:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_reminder_job,
        "interval",
        minutes=INTERVAL_MINUTES,
        id=JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    app.state.scheduler = scheduler
    logger.info("Reminder scheduler started (every %s minutes)", INTERVAL_MINUTES)


def stop_scheduler() -> None:
    """Shut the scheduler down (wait=False) if running; safe when not started."""
    global _scheduler
    scheduler, _scheduler = _scheduler, None
    if scheduler is not None:
        scheduler.shutdown(wait=False)
