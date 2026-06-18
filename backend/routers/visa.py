from fastapi import APIRouter
from backend.data_sources.visa_rules import list_country_visas

router = APIRouter()


@router.get("/visa/{country}")
def get_visa(country: str):
    visas = list_country_visas(country)
    if not visas:
        return {"modeled": False}
    return visas
