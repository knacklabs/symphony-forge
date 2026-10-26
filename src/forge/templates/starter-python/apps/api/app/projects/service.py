import base64
import binascii
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid7

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.core import AccountPrincipal, ApiError
from app.projects.models import Project as ProjectModel
from app.projects.schema import (
    Project,
    ProjectInput,
    ProjectListQuery,
    ProjectListResponse,
    ProjectPaging,
)

# The list counts up to this many matching projects; above it the screen says "More than 10,000".
TOTAL_CAP = 10_000
SORT_COLUMNS = {
    "name": ProjectModel.name,
    "status": ProjectModel.status,
    "createdAtUtc": ProjectModel.created_at_utc,
    "updatedAtUtc": ProjectModel.updated_at_utc,
}
SORT_ATTRIBUTES = {
    "name": "name",
    "status": "status",
    "createdAtUtc": "created_at_utc",
    "updatedAtUtc": "updated_at_utc",
}


def _encode_cursor(sort_by: str, project: ProjectModel) -> str:
    """A cursor is the sort column, its value and the id of a page's first or last row."""
    value = getattr(project, SORT_ATTRIBUTES[sort_by])
    text = value.isoformat() if isinstance(value, datetime) else str(value)
    raw = json.dumps([sort_by, text, str(project.id)]).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_cursor(
    sort_by: str, cursor: str, field: str
) -> tuple[str | datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        cursor_sort, text, cursor_id = json.loads(raw)
        if (
            cursor_sort == sort_by
            and isinstance(text, str)
            and isinstance(cursor_id, str)
        ):
            if not sort_by.endswith("AtUtc"):
                return text, UUID(cursor_id)
            time = datetime.fromisoformat(text)
            if time.tzinfo is not None:
                return time, UUID(cursor_id)
    except binascii.Error, ValueError, TypeError:
        # An unreadable cursor gets the same field error as one for another sort.
        pass
    raise ApiError(
        400,
        "VALIDATION_ERROR",
        "Check the fields and try again.",
        {
            "fieldErrors": [
                {"field": field, "reason": "Open the first page of the list again."}
            ]
        },
    )


def _search_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class ProjectService:
    def __init__(self, db: DbSession) -> None:
        self.db = db

    def list(
        self, account: AccountPrincipal, query: ProjectListQuery
    ) -> ProjectListResponse:
        filters = [
            ProjectModel.organisation_id == account.organisation_id,
            ProjectModel.deleted_at_utc.is_(None),
        ]
        if query.search:
            filters.append(
                ProjectModel.name.ilike(_search_pattern(query.search), escape="\\")
            )
        if query.status is not None:
            filters.append(ProjectModel.status == query.status)
        column = SORT_COLUMNS[query.sort_by]
        # A previous page reads backwards from its cursor, then flips its rows back.
        backward = query.before is not None
        cursor = query.before if backward else query.after
        ascending = (query.sort_order == "asc") != backward
        statement = select(ProjectModel).where(*filters)
        if cursor is not None:
            value, cursor_id = _decode_cursor(
                query.sort_by, cursor, "before" if backward else "after"
            )
            statement = statement.where(
                or_(
                    column > value if ascending else column < value,
                    and_(
                        column == value,
                        ProjectModel.id > cursor_id
                        if ascending
                        else ProjectModel.id < cursor_id,
                    ),
                )
            )
        order = (
            (column.asc(), ProjectModel.id.asc())
            if ascending
            else (column.desc(), ProjectModel.id.desc())
        )
        rows = list(
            self.db.scalars(statement.order_by(*order).limit(query.limit + 1)).all()
        )
        total = (
            self.db.scalar(
                select(func.count()).select_from(
                    select(ProjectModel.id)
                    .where(*filters)
                    .limit(TOTAL_CAP + 1)
                    .subquery()
                )
            )
            or 0
        )
        more = len(rows) > query.limit
        projects = rows[: query.limit]
        if backward:
            projects.reverse()
        has_next = bool(projects) and (backward or more)
        has_previous = bool(projects) and (more if backward else cursor is not None)
        return ProjectListResponse(
            items=[Project.model_validate(project) for project in projects],
            paging=ProjectPaging(
                limit=query.limit,
                next_cursor=_encode_cursor(query.sort_by, projects[-1])
                if has_next
                else None,
                previous_cursor=_encode_cursor(query.sort_by, projects[0])
                if has_previous
                else None,
                total=min(total, TOTAL_CAP),
                total_capped=total > TOTAL_CAP,
            ),
        )

    def list_all(self, account: AccountPrincipal) -> Sequence[Project]:
        """Every project in the organisation, newest first, for the CSV export."""
        projects = self.db.scalars(
            select(ProjectModel)
            .where(
                ProjectModel.organisation_id == account.organisation_id,
                ProjectModel.deleted_at_utc.is_(None),
            )
            .order_by(ProjectModel.created_at_utc.desc(), ProjectModel.id.asc())
        ).all()
        return [Project.model_validate(project) for project in projects]

    def get(self, account: AccountPrincipal, project_id: UUID) -> Project:
        project = self.db.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.organisation_id == account.organisation_id,
                ProjectModel.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise self._not_found()
        return Project.model_validate(project)

    def create(self, account: AccountPrincipal, input_data: ProjectInput) -> Project:
        project = ProjectModel(
            id=uuid7(),
            organisation_id=account.organisation_id,
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
                ProjectModel.organisation_id == account.organisation_id,
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
                ProjectModel.organisation_id == account.organisation_id,
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
