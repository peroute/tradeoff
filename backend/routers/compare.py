from fastapi import APIRouter
from backend.models.intake_models import CompareRequest
from backend.models.output_models import DashboardPayload

router = APIRouter()


@router.post("/compare", response_model=DashboardPayload)
async def compare(request: CompareRequest):
    # Stubbed until Stage 2b + orchestrator land — returns a hardcoded,
    # schema-valid sample payload (self-labeled as sample, not live data).
    from backend.pipeline.sample_payload import build_sample_payload
    return build_sample_payload(request)
