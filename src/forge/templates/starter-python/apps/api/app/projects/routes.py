from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.auth import AccountPrincipal, current_account, require_csrf
from app.core import ErrorEnvelope, SuccessEnvelope, get_db
from app.projects.schema import (
    Project,
    ProjectInput,
    ProjectListQuery,
    ProjectListResponse,
)
from app.projects.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.get(
    "",
    response_model=SuccessEnvelope[ProjectListResponse],
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
    summary="List the signed-in account’s projects.",
)
def list_projects(
    account: Annotated[AccountPrincipal, Depends(current_account)],
    query: Annotated[ProjectListQuery, Query()],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[ProjectListResponse]:
    return SuccessEnvelope(data=ProjectService(db).list(account, query))


@router.post(
    "",
    status_code=201,
    response_model=SuccessEnvelope[Project],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
    },
    summary="Create a project for the signed-in account.",
)
def create_project(
    input_data: ProjectInput,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(data=ProjectService(db).create(account, input_data))


@router.get(
    "/{project_id}",
    response_model=SuccessEnvelope[Project],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Read one project owned by the signed-in account.",
)
def get_project(
    project_id: UUID,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(data=ProjectService(db).get(account, project_id))


@router.put(
    "/{project_id}",
    response_model=SuccessEnvelope[Project],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Replace a project owned by the signed-in account.",
)
def update_project(
    project_id: UUID,
    input_data: ProjectInput,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(
        data=ProjectService(db).update(account, project_id, input_data)
    )


@router.delete(
    "/{project_id}",
    response_model=SuccessEnvelope[None],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Soft-delete a project owned by the signed-in account.",
)
def delete_project(
    project_id: UUID,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[None]:
    ProjectService(db).delete(account, project_id)
    return SuccessEnvelope(data=None)
