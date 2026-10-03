"""FastAPI app for the ThermoTwin clinician dashboard.

Run: uv run uvicorn thermotwin.api.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from thermotwin.api.schemas import (
    Meta,
    PatientSummary,
    ReviewItem,
    Tier0Response,
    Timeline,
    WhatIfRequest,
    WhatIfResponse,
)
from thermotwin.api.service import PatientNotFoundError, TwinService
from thermotwin.nowearable import tier0_risk


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="THERMOTWIN_")

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.service = TwinService()
    yield


app = FastAPI(title="ThermoTwin API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_service(request: Request) -> TwinService:
    return request.app.state.service


Service = Annotated[TwinService, Depends(get_service)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/meta", response_model=Meta)
def meta(service: Service) -> Meta:
    return service.meta()


@app.get("/patients", response_model=list[PatientSummary])
def patients(
    service: Service, minute: Annotated[int | None, Query(ge=0)] = None
) -> list[PatientSummary]:
    return service.summaries(minute)


@app.get("/review", response_model=list[ReviewItem])
def review(service: Service) -> list[ReviewItem]:
    return service.review()


@app.get("/patients/{patient_id}/timeline", response_model=Timeline)
def timeline(patient_id: str, service: Service) -> Timeline:
    try:
        return service.timeline(patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"patient {patient_id} not found") from exc


@app.get("/tier0", response_model=Tier0Response)
def tier0(
    air_temp_c: Annotated[float, Query(description="Air temperature (°C)")],
    humidity_pct: Annotated[float, Query(ge=0, le=100, description="Relative humidity (%)")],
    hour: Annotated[float, Query(ge=0, lt=24, description="Hour of day (0-23.9)")],
    age: Annotated[int, Query(ge=0, le=120)],
    bmi: Annotated[float, Query(gt=0)],
    occupation: Annotated[str, Query(description="Worker occupation")],
    has_heat_drug: Annotated[bool, Query(description="On heat-illness-associated medication")],
) -> Tier0Response:
    result = tier0_risk(
        air_temp_c=air_temp_c,
        relative_humidity_pct=humidity_pct,
        hour=hour,
        age=age,
        bmi=bmi,
        occupation=occupation,
        has_heat_illness_drug=has_heat_drug,
    )
    return Tier0Response(
        wbgt_c=result.wbgt_c,
        risk_score=result.risk_score,
        alert=result.alert,
        tier=result.tier,
        reasons=list(result.reasons),
    )


@app.post("/patients/{patient_id}/whatif", response_model=WhatIfResponse)
def what_if(patient_id: str, body: WhatIfRequest, service: Service) -> WhatIfResponse:
    try:
        baseline, scenario, tl = service.what_if(patient_id, body.start_minute, body.duration_min)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"patient {patient_id} not found") from exc
    return WhatIfResponse(baseline=baseline, scenario=scenario, timeline=tl)
