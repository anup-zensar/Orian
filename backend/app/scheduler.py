"""Background scheduler (contract stub, M8b). The lead wires it into the app lifespan."""

from __future__ import annotations

from fastapi import FastAPI


def start_scheduler(app: FastAPI) -> None:
    """If ``get_settings().reminder_job_enabled`` is true, start an APScheduler
    ``BackgroundScheduler`` with one interval job (every 15 minutes, max_instances=1,
    coalesce=True) that opens a Session (``app.db.SessionLocal``), calls
    ``app.domain.reminders.run_reminders(db, user=None, triggered_by="scheduler")``, commits, and
    closes (exceptions logged, never raised). Stores the scheduler on ``app.state.scheduler``.
    Does nothing when the flag is false (default) or when already started."""
    raise NotImplementedError("M8")


def stop_scheduler() -> None:
    """Shut the scheduler down (wait=False) if running; safe to call when not started."""
    raise NotImplementedError("M8")
