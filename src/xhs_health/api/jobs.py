from fastapi import APIRouter

from xhs_health.schemas import SchedulerStatusOut
from xhs_health.services.scheduler import score_scheduler


router = APIRouter()


@router.get("/score-scheduler", response_model=SchedulerStatusOut)
def get_score_scheduler_status() -> SchedulerStatusOut:
    return SchedulerStatusOut.model_validate(score_scheduler.snapshot().__dict__)


@router.post("/score-scheduler/run", response_model=SchedulerStatusOut)
def run_score_scheduler_once() -> SchedulerStatusOut:
    return SchedulerStatusOut.model_validate(score_scheduler.run_once().__dict__)
