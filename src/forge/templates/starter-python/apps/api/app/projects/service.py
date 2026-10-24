from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.auth import AccountPrincipal
from app.core import ApiError
from app.projects.models import Project as ProjectModel
from app.projects.schema import (
    Project,
    ProjectInput,
    ProjectListQuery,
    ProjectListResponse,
    ProjectPagination,
)


class ProjectService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def list(
        self, account: AccountPrincipal, query: ProjectListQuery
    ) -> ProjectListResponse:
        filters = (
            ProjectModel.account_id == account.id,
            ProjectModel.deleted_at_utc.is_(None),
        )
        sort_column = {
            "name": ProjectModel.name,
            "status": ProjectModel.status,
            "createdAtUtc": ProjectModel.created_at_utc,
            "updatedAtUtc": ProjectModel.updated_at_utc,
        }[query.sort_by]
        sort_expression = (
            sort_column.asc() if query.sort_order == "asc" else sort_column.desc()
        )
        projects = self.db.scalars(
            select(ProjectModel)
            .where(*filters)
            .order_by(sort_expression, ProjectModel.id.asc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        ).all()
        total_items = (
            self.db.scalar(
                select(func.count()).select_from(ProjectModel).where(*filters)
            )
            or 0
        )
        return ProjectListResponse(
            items=[Project.model_validate(project) for project in projects],
            pagination=ProjectPagination(
                page=query.page,
                limit=query.limit,
                total_items=total_items,
                total_pages=(total_items + query.limit - 1) // query.limit,
            ),
        )

    def get(self, account: AccountPrincipal, project_id: UUID) -> Project:
        project = self.db.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account.id,
                ProjectModel.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        return Project.model_validate(project)

    def create(self, account: AccountPrincipal, input_data: ProjectInput) -> Project:
        project = ProjectModel(
            id=uuid4(),
            account_id=account.id,
            name=input_data.name,
            status=input_data.status,
            created_by_account_id=account.id,
            modified_by_account_id=account.id,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return Project.model_validate(project)

    def update(
        self, account: AccountPrincipal, project_id: UUID, input_data: ProjectInput
    ) -> Project:
        project = self.db.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account.id,
                ProjectModel.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        project.name = input_data.name
        project.status = input_data.status
        project.modified_by_account_id = account.id
        self.db.commit()
        self.db.refresh(project)
        return Project.model_validate(project)

    def delete(self, account: AccountPrincipal, project_id: UUID) -> None:
        project = self.db.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account.id,
                ProjectModel.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        now = datetime.now(UTC)
        project.deleted_at_utc = now
        project.deleted_by_account_id = account.id
        project.modified_by_account_id = account.id
        self.db.commit()

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(404, "PROJECT_NOT_FOUND", "The project was not found.")
