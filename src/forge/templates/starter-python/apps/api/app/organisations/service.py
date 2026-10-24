from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import AccountPrincipal
from app.organisations.models import Membership, Organisation
from app.organisations.schema import (
    Member,
    MemberListQuery,
    MemberListResponse,
    MemberPagination,
)


class OrganisationsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_account(self, account_id: UUID, email: str) -> AccountPrincipal:
        organisation_id = uuid4()
        self.db.add(
            Organisation(
                id=organisation_id,
                created_by_account_id=account_id,
                modified_by_account_id=account_id,
            )
        )
        self.db.flush()
        self.db.add(
            Membership(
                id=uuid4(),
                organisation_id=organisation_id,
                account_id=account_id,
                email=email,
                role="admin",
                created_by_account_id=account_id,
                modified_by_account_id=account_id,
            )
        )
        self.db.flush()
        return AccountPrincipal(account_id, email, organisation_id, "admin")

    def membership_for(self, account_id: UUID) -> AccountPrincipal | None:
        member = self.db.scalar(
            select(Membership)
            .join(Organisation)
            .where(
                Membership.account_id == account_id,
                Membership.deleted_at_utc.is_(None),
                Organisation.deleted_at_utc.is_(None),
            )
        )
        if member is None:
            return None
        return AccountPrincipal(
            member.account_id, member.email, member.organisation_id, member.role
        )

    def list(self, organisation_id: UUID, query: MemberListQuery) -> MemberListResponse:
        statement = select(Membership).where(
            Membership.organisation_id == organisation_id,
            Membership.deleted_at_utc.is_(None),
        )
        total = (
            self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        members = self.db.scalars(
            statement.order_by(Membership.created_at_utc.asc(), Membership.id.asc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        ).all()
        return MemberListResponse(
            items=[Member.model_validate(member) for member in members],
            pagination=MemberPagination(
                page=query.page,
                limit=query.limit,
                total_items=total,
                total_pages=(total + query.limit - 1) // query.limit,
            ),
        )

    def list_all(self, organisation_id: UUID) -> Sequence[Member]:
        members = self.db.scalars(
            select(Membership)
            .where(
                Membership.organisation_id == organisation_id,
                Membership.deleted_at_utc.is_(None),
            )
            .order_by(Membership.created_at_utc.asc(), Membership.id.asc())
        ).all()
        return [Member.model_validate(member) for member in members]
