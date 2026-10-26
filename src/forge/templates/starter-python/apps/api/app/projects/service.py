import base64
import binascii
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.core import AccountPrincipal, ApiError, has_permission
from app.history import HistoryEntry, HistoryService, Subject
from app.projects.models import Project as ProjectModel
from app.projects.permissions import PROJECT_PERMISSIONS
from app.projects.schema import (
    Project,
    ProjectExportQuery,
    ProjectInput,
    ProjectListQuery,
    ProjectListResponse,
    ProjectPaging,
)

# The changes route returns this many entries, newest first.
RECENT_CHANGES = 5
# The labels the change summaries use, in the order the form shows the fields.
FIELD_LABELS = {"name": "Name", "status": "Status"}
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
    raw = json.dumps([sort_by, text, str(project.id)], ensure_ascii=False).encode()
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


def _change_summary(project: ProjectModel, input_data: ProjectInput) -> str:
    """One "<Label> changed from <old> to <new>" per changed field, as the CSV shows them."""
    changes = []
    for field, label in FIELD_LABELS.items():
        before, after = str(getattr(project, field)), str(getattr(input_data, field))
        if before != after:
            changes.append(f"{label} changed from {before} to {after}")
    return "; ".join(changes)


def _search_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _sees_deleted(account: AccountPrincipal) -> bool:
    return has_permission(account.role, PROJECT_PERMISSIONS.restore)


def _filters(account: AccountPrincipal, query: ProjectExportQuery) -> list[Any]:
    """The organisation's projects that match the search and status filter.

    Deleted projects are left out unless the caller asks for them and may restore them.
    """
    filters: list[Any] = [ProjectModel.organisation_id == account.organisation_id]
    if not (query.deleted == "yes" and _sees_deleted(account)):
        filters.append(ProjectModel.deleted_at_utc.is_(None))
    if query.search:
        filters.append(
            ProjectModel.name.ilike(_search_pattern(query.search), escape="\\")
        )
    if query.status is not None:
        filters.append(ProjectModel.status == query.status)
    return filters


class ProjectService:
    def __init__(self, db: DbSession) -> None:
        self.db = db
        self.history = HistoryService(db)

    def list(
        self, account: AccountPrincipal, query: ProjectListQuery
    ) -> ProjectListResponse:
        filters = _filters(account, query)
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

    def list_all(
        self, account: AccountPrincipal, query: ProjectExportQuery
    ) -> Sequence[Project]:
        """The projects the list shows for this search and filter, newest first."""
        projects = self.db.scalars(
            select(ProjectModel)
            .where(*_filters(account, query))
            .order_by(ProjectModel.created_at_utc.desc(), ProjectModel.id.asc())
        ).all()
        return [Project.model_validate(project) for project in projects]

    def _find(
        self, account: AccountPrincipal, project_id: UUID, *conditions: Any
    ) -> ProjectModel:
        project = self.db.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.organisation_id == account.organisation_id,
                *conditions,
            )
        )
        if project is None:
            raise self._not_found()
        return project

    def _live(self, account: AccountPrincipal, project_id: UUID) -> ProjectModel:
        return self._find(account, project_id, ProjectModel.deleted_at_utc.is_(None))

    def _readable(self, account: AccountPrincipal, project_id: UUID) -> ProjectModel:
        """A live project, or a deleted one for a caller who may restore it."""
        if _sees_deleted(account):
            return self._find(account, project_id)
        return self._live(account, project_id)

    def get(self, account: AccountPrincipal, project_id: UUID) -> Project:
        return Project.model_validate(self._readable(account, project_id))

    def changes(
        self, account: AccountPrincipal, project_id: UUID
    ) -> Sequence[HistoryEntry]:
        """The project's newest changes; another organisation's project is not found."""
        self._readable(account, project_id)
        return self.history.list_for_subject(account, project_id, RECENT_CHANGES)

    # Each change and its Change history row commit together in one commit.
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
        self.history.record(
            account,
            "project.created",
            "Created the project",
            Subject(project.id, project.name),
        )
        self.db.commit()
        self.db.refresh(project)
        return Project.model_validate(project)

    def update(
        self, account: AccountPrincipal, project_id: UUID, input_data: ProjectInput
    ) -> Project:
        project = self._live(account, project_id)
        summary = _change_summary(project, input_data)
        project.name = input_data.name
        project.status = input_data.status
        project.modified_by_account_id = account.id
        # A replace that changes no field adds no history row.
        if summary:
            self.history.record(
                account, "project.changed", summary, Subject(project.id, project.name)
            )
        self.db.commit()
        self.db.refresh(project)
        return Project.model_validate(project)

    def delete(self, account: AccountPrincipal, project_id: UUID) -> None:
        project = self._live(account, project_id)
        project.deleted_at_utc = datetime.now(UTC)
        project.deleted_by_account_id = account.id
        project.modified_by_account_id = account.id
        self.history.record(
            account,
            "project.deleted",
            "Deleted the project",
            Subject(project.id, project.name),
        )
        self.db.commit()

    def restore(self, account: AccountPrincipal, project_id: UUID) -> Project:
        project = self._find(
            account, project_id, ProjectModel.deleted_at_utc.is_not(None)
        )
        project.deleted_at_utc = None
        project.deleted_by_account_id = None
        project.modified_by_account_id = account.id
        self.history.record(
            account,
            "project.restored",
            "Restored the project",
            Subject(project.id, project.name),
        )
        self.db.commit()
        self.db.refresh(project)
        return Project.model_validate(project)

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(404, "PROJECT_NOT_FOUND", "The project was not found.")
