from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    from backend.data_sources.visa_rules import is_loaded
    return {
        "status": "ok",
        "visa_rules_loaded": is_loaded("visa_rules"),
        "source_registry_loaded": is_loaded("source_registry"),
        "tax_rates_loaded": is_loaded("tax_rates"),
    }
