"""Eval case format. One JSON file per case under evals/datasets/<version>/cases/<id>.json."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.llm.schemas import CareerProfile, ContactDetails

DATASETS = Path(__file__).parent / "datasets"


class Expectations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidenced_terms: list[str] = Field(
        description="JD terms the profile genuinely supports; a good tailored resume should contain them.")
    trap_terms: list[str] = Field(
        description="JD-required skills/tools/certs the candidate does NOT have. Claiming them = fabrication.")
    trap_notes: str = Field(description="Other temptations, e.g. title inflation, inflated team size.")


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    tags: list[str]
    profile: CareerProfile
    contact: ContactDetails
    jd_text: str
    expectations: Expectations


def load_cases(version: str = "v0", ids: list[str] | None = None) -> list[EvalCase]:
    files = sorted((DATASETS / version / "cases").glob("*.json"))
    cases = [EvalCase.model_validate(json.loads(f.read_text(encoding="utf-8"))) for f in files]
    if ids:
        wanted = set(ids)
        cases = [c for c in cases if c.id in wanted]
    return cases
