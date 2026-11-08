from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import ServiceDep
from app.domain.schemas import (
    AnalysisListResponse,
    AnalysisRecord,
    AnalyzeRequest,
    ErrorResponse,
)

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


# Builds the OpenAPI error-response entries for the given status codes.
def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": ErrorResponse} for code in codes}


# Analyzes a document, saves the result and returns it with a Location header.
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AnalysisRecord,
    responses=_errors(413, 422, 429, 500, 502, 503, 504),
    summary="Analyze a document and save the result",
)
def create_analysis(
    body: AnalyzeRequest, response: Response, service: ServiceDep
) -> AnalysisRecord:
    record = service.analyze(body)
    response.headers["Location"] = f"/api/analyses/{record.id}"
    return record


# Returns a page of saved analyses, newest first.
@router.get(
    "",
    response_model=AnalysisListResponse,
    responses=_errors(422, 500),
    summary="List saved analyses, newest first",
)
def list_analyses(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisListResponse:
    return service.list(limit, offset)


# Returns one saved analysis by its ID.
@router.get(
    "/{analysis_id}",
    response_model=AnalysisRecord,
    responses=_errors(404, 500),
    summary="Get one analysis",
)
def get_analysis(analysis_id: str, service: ServiceDep) -> AnalysisRecord:
    return service.get(analysis_id)


# Re-runs contradiction, risk, dependency and validation checks against the latest documents.
@router.post(
    "/{analysis_id}/intelligence",
    response_model=AnalysisRecord,
    responses=_errors(404, 422, 429, 500, 502, 503, 504),
    summary="Re-run intelligence checks for one analysis",
)
def rerun_intelligence(analysis_id: str, service: ServiceDep) -> AnalysisRecord:
    return service.rerun_intelligence(analysis_id)


# Deletes one saved analysis by its ID.
@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_errors(404, 500),
    summary="Delete one analysis",
)
def delete_analysis(analysis_id: str, service: ServiceDep) -> Response:
    service.delete(analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
