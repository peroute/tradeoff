from fastapi import APIRouter
from backend.models.intake_models import CompareRequest
from backend.models.output_models import DashboardPayload

router = APIRouter()


@router.post("/compare", response_model=DashboardPayload)
async def compare(request: CompareRequest):
    from backend.pipeline.orchestrator import run_pipeline
    return await run_pipeline(request)
