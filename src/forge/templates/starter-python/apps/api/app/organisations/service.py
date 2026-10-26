import hashlib
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import NamedTuple
from urllib.parse import urlencode
from uuid import UUID, uuid7

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import AccountPrincipal, ApiError, MailProvider, Role
from app.history import HistoryService
from app.organisations.models import Invite, Membership, Organisation
from app.organisations.schema import (
    Member,
    MemberListQuery,
    MemberListResponse,
    MemberPagination,
)


class OpenInvite(NamedTuple):
    id: UUID
    email: str
    organisation_id: UUID
    token_hash: str


def _invalid_invite() -> ApiError:
    return ApiError(
        400,
        "INVITE_INVALID",
        "This invite link is not valid. Ask an admin for a new one.",
    )


class OrganisationsService:
    def __init__(self, db: Session, history: HistoryService) -> None:
        self.db = db
        self.history = history

    def invite(
        self, email: str, account: AccountPrincipal, mail: MailProvider, app_origin: str
    ) -> None:
        token = secrets.token_urlsafe(32)
        credentials = {
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at_utc": datetime.now(UTC) + timedelta(days=7),
            "modified_by_account_id": account.id,
            "updated_at_utc": datetime.now(UTC),
        }
        self.db.execute(
            insert(Invite)
            .values(
                id=uuid7(),
                organisation_id=account.organisation_id,
                email=email,
                created_by_account_id=account.id,
                **credentials,
            )
            .on_conflict_do_update(
                index_elements=["organisation_id", "email"], set_=credentials
            )
        )
        # A provider refusal rolls back the pending invite with the request's session.
        mail.send_invite(
            email, f"{app_origin}/accept-invite?{urlencode({'token': token})}"
        )
        self.db.commit()

        # ponytail: saving the invite and its history are two calls; use a shared
        # transaction if atomic history becomes required.
        self.history.record(account, "member.invited", f"Invited {email}")

    def open_invite(self, token: str) -> OpenInvite:
        invite = self.db.scalar(
            select(Invite)
            .join(Organisation)
            .where(
                Invite.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                Invite.expires_at_utc > datetime.now(UTC),
                Organisation.deleted_at_utc.is_(None),
            )
        )
        if invite is None:
            raise _invalid_invite()
        return OpenInvite(
            invite.id, invite.email, invite.organisation_id, invite.token_hash
        )

    def join_from_invite(
        self, invite: OpenInvite, account_id: UUID, email: str
    ) -> AccountPrincipal:
        claimed = self.db.scalar(
            delete(Invite)
            .where(
                Invite.id == invite.id,
                Invite.token_hash == invite.token_hash,
                Invite.expires_at_utc > datetime.now(UTC),
            )
            .returning(Invite.id)
        )
        if claimed is None:
            raise _invalid_invite()
        self.db.add(
            Membership(
                id=uuid7(),
                organisation_id=invite.organisation_id,
                account_id=account_id,
                email=email,
                role="member",
                created_by_account_id=account_id,
                modified_by_account_id=account_id,
            )
        )
        self.db.commit()
        return AccountPrincipal(account_id, email, invite.organisation_id, "member")

    def change_role(
        self, account: AccountPrincipal, account_id: UUID, role: Role
    ) -> Member:
        if account_id == account.id:
            raise ApiError(
                403, "CANNOT_CHANGE_OWN_ROLE", "You cannot change your own role."
            )
        old_role = self.db.scalar(
            select(Membership.role).where(
                Membership.account_id == account_id,
                Membership.organisation_id == account.organisation_id,
                Membership.deleted_at_utc.is_(None),
            )
        )
        member = self.db.scalar(
            update(Membership)
            .where(
                Membership.account_id == account_id,
                Membership.organisation_id == account.organisation_id,
                Membership.deleted_at_utc.is_(None),
            )
            .values(role=role, modified_by_account_id=account.id)
            .returning(Membership)
        )
        if member is None:
            raise ApiError(404, "MEMBER_NOT_FOUND", "This member was not found.")
        self.db.commit()
        # ponytail: changing the role and its history are two calls; use a shared
        # transaction if atomic history becomes required.
        self.history.record(
            account,
            "member.role_changed",
            f"Changed {member.email} from {old_role} to {role}",
        )
        return Member.model_validate(member)

    def create_for_account(self, account_id: UUID, email: str) -> AccountPrincipal:
        organisation_id = uuid7()
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
                id=uuid7(),
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
