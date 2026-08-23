from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event, Lock, Thread

from sqlalchemy import select

from xhs_health.db import SessionLocal
from xhs_health.models import Account
from xhs_health.services.score_service import calculate_and_store_score


_log = logging.getLogger("xhs_health.scheduler")


@dataclass
class SchedulerSnapshot:
    name: str
    enabled: bool
    interval_seconds: int
    running: bool
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_status: str
    last_message: str | None
    total_runs: int
    scores_created: int


class ScoreScheduler:
    def __init__(self) -> None:
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self.enabled = False
        self.interval_seconds = 3600
        self.running = False
        self.last_started_at: datetime | None = None
        self.last_finished_at: datetime | None = None
        self.last_status = "idle"
        self.last_message: str | None = None
        self.total_runs = 0
        self.scores_created = 0

    def configure(self, enabled: bool, interval_seconds: int) -> None:
        self.enabled = enabled
        self.interval_seconds = max(60, interval_seconds)

    def start(self) -> None:
        if not self.enabled or self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="xhs-score-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def run_once(self) -> SchedulerSnapshot:
        with self._lock:
            self.running = True
            self.last_started_at = datetime.now(UTC)
            self.last_status = "running"
            self.last_message = None
        try:
            created = self._score_active_accounts()
            with self._lock:
                self.total_runs += 1
                self.scores_created += created
                self.last_status = "success"
                self.last_message = f"scored {created} active account(s)"
        except Exception as exc:  # pragma: no cover - defensive status surface
            with self._lock:
                self.total_runs += 1
                self.last_status = "failed"
                self.last_message = str(exc)
        finally:
            with self._lock:
                self.running = False
                self.last_finished_at = datetime.now(UTC)
        return self.snapshot()

    def snapshot(self) -> SchedulerSnapshot:
        with self._lock:
            return SchedulerSnapshot(
                name="active-account-score",
                enabled=self.enabled,
                interval_seconds=self.interval_seconds,
                running=self.running,
                last_started_at=self.last_started_at,
                last_finished_at=self.last_finished_at,
                last_status=self.last_status,
                last_message=self.last_message,
                total_runs=self.total_runs,
                scores_created=self.scores_created,
            )

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.run_once()

    def _score_active_accounts(self) -> int:
        with SessionLocal() as session:
            account_ids = list(
                session.scalars(select(Account.id).where(Account.status == "active")).all()
            )
            created = 0
            for account_id in account_ids:
                try:
                    calculate_and_store_score(session, account_id)
                    # Commit per account: a poisoned transaction on one account
                    # must not discard the scores already computed for the rest.
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    _log.warning("scheduler: score failed for account_id=%s: %s", account_id, exc)
                    continue
                created += 1
            return created


score_scheduler = ScoreScheduler()
