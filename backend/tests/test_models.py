import pytest
from pydantic import ValidationError

from backend.models.fact_models import CostData, WageData


def test_retrieved_at_defaults_to_iso_timestamp():
    w = WageData(
        country="US", currency="USD", gross_annual=1.0,
        granularity="national_average", source="OECD",
    )
    assert "T" in w.retrieved_at  # ISO 8601

    c = CostData(
        city="X", country="US", currency="USD",
        cost_of_living_index=1.0, source="Numbeo (mock)",
    )
    assert "T" in c.retrieved_at


def test_bad_granularity_rejected():
    with pytest.raises(ValidationError):
        WageData(
            country="US", currency="USD", gross_annual=1.0,
            granularity="bogus", source="OECD",
        )
