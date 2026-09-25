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
    Timeline,
    WhatIfRequest,
    WhatIfResponse,
)
from thermotwin.api.service import PatientNotFoundError, TwinService


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


@app.post("/patients/{patient_id}/whatif", response_model=WhatIfResponse)
def what_if(patient_id: str, body: WhatIfRequest, service: Service) -> WhatIfResponse:
    try:
        baseline, scenario, tl = service.what_if(patient_id, body.start_minute, body.duration_min)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"patient {patient_id} not found") from exc
    return WhatIfResponse(baseline=baseline, scenario=scenario, timeline=tl)
