from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session as DbSession

from app.auth import require_csrf
from app.core import (
    AccountPrincipal,
    CsvColumn,
    ErrorEnvelope,
    SuccessEnvelope,
    csv_response,
    get_db,
    require_permission,
    utc_date_time,
)
from app.history import HistoryEntry
from app.projects.permissions import PROJECT_PERMISSIONS
from app.projects.schema import (
    Project,
    ProjectExportQuery,
    ProjectInput,
    ProjectListQuery,
    ProjectListResponse,
)
from app.projects.service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

PROJECT_CSV_COLUMNS: tuple[CsvColumn[Project], ...] = (
    ("Name", lambda project: project.name),
    ("Status", lambda project: project.status.value),
    ("Created (UTC)", lambda project: utc_date_time(project.created_at_utc)),
    ("Updated (UTC)", lambda project: utc_date_time(project.updated_at_utc)),
)


@router.get(
    "",
    response_model=SuccessEnvelope[ProjectListResponse],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
    },
    summary="List your organisation’s projects.",
)
def list_projects(
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.view))
    ],
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
    summary="Create a project for your organisation.",
)
def create_project(
    input_data: ProjectInput,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.create))
    ],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(data=ProjectService(db).create(account, input_data))


# Declared before "/{project_id}", so "export" is not read as a project identifier.
@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {"description": "The projects.csv file, newest first."},
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
    },
    summary="Download the projects that match the list's search and filter as CSV.",
)
def export_projects(
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.view))
    ],
    query: Annotated[ProjectExportQuery, Query()],
    db: Annotated[DbSession, Depends(get_db)],
) -> Response:
    return csv_response(
        "projects.csv", PROJECT_CSV_COLUMNS, ProjectService(db).list_all(account, query)
    )


@router.get(
    "/{project_id}",
    response_model=SuccessEnvelope[Project],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Read one project in your organisation.",
)
def get_project(
    project_id: UUID,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.view))
    ],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(data=ProjectService(db).get(account, project_id))


@router.get(
    "/{project_id}/changes",
    response_model=SuccessEnvelope[list[HistoryEntry]],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="List the newest 5 changes to one project in your organisation.",
)
def list_project_changes(
    project_id: UUID,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.view))
    ],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[list[HistoryEntry]]:
    return SuccessEnvelope(data=ProjectService(db).changes(account, project_id))


@router.put(
    "/{project_id}",
    response_model=SuccessEnvelope[Project],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Replace a project in your organisation.",
)
def update_project(
    project_id: UUID,
    input_data: ProjectInput,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.edit))
    ],
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
    summary="Soft-delete a project in your organisation.",
)
def delete_project(
    project_id: UUID,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.delete))
    ],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[None]:
    ProjectService(db).delete(account, project_id)
    return SuccessEnvelope(data=None)


@router.post(
    "/{project_id}/restore",
    response_model=SuccessEnvelope[Project],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
    summary="Restore a deleted project in your organisation.",
)
def restore_project(
    project_id: UUID,
    account: Annotated[
        AccountPrincipal, Depends(require_permission(PROJECT_PERMISSIONS.restore))
    ],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Project]:
    return SuccessEnvelope(data=ProjectService(db).restore(account, project_id))
