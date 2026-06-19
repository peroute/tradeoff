from typing import Literal
from pydantic import BaseModel

CareerStage = Literal["new_grad", "early_career", "mid_career", "senior"]

SupportedCountry = Literal["US", "UK", "Canada", "Australia", "Germany", "France"]


class CompareRequest(BaseModel):
    citizenship: str
    degree_field: str
    career_stage: CareerStage
    country_a: SupportedCountry
    country_b: SupportedCountry
    user_context: str


class ParsedProfile(BaseModel):
    citizenship: str
    degree_field: str
    career_stage: CareerStage
    country_a: SupportedCountry
    country_b: SupportedCountry
    user_context: str
