from fastapi import APIRouter, HTTPException

from backend.models.intake_models import CompareRequest
from backend.models.output_models import DashboardPayload
from backend.pipeline.orchestrator import run_pipeline

router = APIRouter()


@router.post("/compare", response_model=DashboardPayload)
def compare(request: CompareRequest) -> DashboardPayload:
    try:
        return run_pipeline(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"AI pipeline unavailable: {exc}")
