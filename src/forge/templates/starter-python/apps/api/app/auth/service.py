import base64
import hashlib
import hmac
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import UUID, uuid7

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.auth.models import Account, PasswordResetToken, Session
from app.auth.schema import (
    AcceptInviteInput,
    AuthOptions,
    CredentialsInput,
    MessageResponse,
    ResetPasswordInput,
    SessionData,
)
from app.auth.schema import Account as AccountResponse
from app.core import (
    AccountPrincipal,
    ApiError,
    MailProvider,
    Settings,
    permissions_for,
)

if TYPE_CHECKING:
    from app.organisations import OrganisationsService

_PASSWORD_KEY_BYTES = 64
_PASSWORD_SALT_BYTES = 16
_PASSWORD_SCRYPT_N = 2**17
_PASSWORD_SCRYPT_R = 8
_PASSWORD_SCRYPT_P = 1
_PASSWORD_SCRYPT_MAXMEM = 256 * 1024 * 1024
_SESSION_LIFETIME = timedelta(days=30)
_RESET_TOKEN_LIFETIME = timedelta(hours=1)
_RESET_MESSAGE = "If an account exists, a reset link has been sent."


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _token() -> str:
    return (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(_PASSWORD_SALT_BYTES)
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_PASSWORD_SCRYPT_N,
        r=_PASSWORD_SCRYPT_R,
        p=_PASSWORD_SCRYPT_P,
        dklen=_PASSWORD_KEY_BYTES,
        maxmem=_PASSWORD_SCRYPT_MAXMEM,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).rstrip(b"=").decode("ascii")
    encoded_key = base64.urlsafe_b64encode(key).rstrip(b"=").decode("ascii")
    return f"scrypt${encoded_salt}${encoded_key}"


def _verify_password(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        expected_key = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
    except ValueError:
        return False
    if len(salt) != _PASSWORD_SALT_BYTES or len(expected_key) != _PASSWORD_KEY_BYTES:
        return False
    actual_key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_PASSWORD_SCRYPT_N,
        r=_PASSWORD_SCRYPT_R,
        p=_PASSWORD_SCRYPT_P,
        dklen=_PASSWORD_KEY_BYTES,
        maxmem=_PASSWORD_SCRYPT_MAXMEM,
    )
    return hmac.compare_digest(actual_key, expected_key)


def account_emails(db: DbSession, account_ids: Iterable[UUID]) -> dict[UUID, str]:
    """Each known account's email by its id, for modules that show who changed what."""
    rows = db.execute(
        select(Account.id, Account.email).where(Account.id.in_(set(account_ids)))
    )
    return {account_id: email for account_id, email in rows.tuples()}


class AuthService:
    def __init__(
        self,
        db: DbSession,
        settings: Settings,
        mail_provider: MailProvider,
        organisations: OrganisationsService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.mail_provider = mail_provider
        self.organisations = organisations

    def sign_up(self, credentials: CredentialsInput) -> SessionData:
        if not self.options().sign_up_open:
            raise ApiError(
                403,
                "SIGN_UP_CLOSED",
                "This app is for one company. Ask an admin of your team for an invite.",
            )
        account = self.set_up_company(credentials)
        session_data = self._new_session(account)
        self.db.add(self._session_row(account.id, session_data))
        self.db.commit()
        return session_data

    def options(self) -> AuthOptions:
        return AuthOptions(sign_up_open=self.settings.app_companies == "many")

    def set_up_company(self, credentials: CredentialsInput) -> AccountResponse:
        account = self._create_account(credentials)
        principal = self.organisations.create_for_account(account.id, account.email)
        return AccountResponse(
            id=account.id,
            email=account.email,
            role=principal.role,
            permissions=permissions_for(principal.role),
        )

    def _create_account(
        self,
        credentials: CredentialsInput,
        conflict_message: str = "An account already uses that email.",
    ) -> Account:
        account_id = uuid7()
        account = Account(
            id=account_id,
            email=credentials.email,
            password_hash=_hash_password(credentials.password),
            created_by_account_id=account_id,
            modified_by_account_id=account_id,
        )
        try:
            self.db.add(account)
            self.db.flush()
        except IntegrityError as error:
            self.db.rollback()
            raise ApiError(
                409,
                "EMAIL_ALREADY_REGISTERED",
                conflict_message,
            ) from error
        return account

    def invite(self, email: str, account: AccountPrincipal) -> MessageResponse:
        if self.db.scalar(select(Account.id).where(Account.email == email)) is not None:
            raise ApiError(
                409, "EMAIL_ALREADY_REGISTERED", "That person already has an account."
            )
        self.organisations.invite(
            email, account, self.mail_provider, self.settings.app_origin
        )
        return MessageResponse(message="Invite sent.")

    def accept_invite(self, input_data: AcceptInviteInput) -> SessionData:
        invite = self.organisations.open_invite(input_data.token)
        if invite.email != input_data.email:
            raise ApiError(
                400,
                "INVITE_INVALID",
                "This invite link is not valid. Ask an admin for a new one.",
            )
        account = self._create_account(
            input_data,
            "An account already uses that email, so it cannot join this organisation.",
        )
        self.db.commit()
        # ponytail: a failure between these module calls leaves an account with no membership
        # and 401; support must remove it before another attempt.
        principal = self.organisations.join_from_invite(
            invite, account.id, account.email
        )
        session_data = self._new_session(
            AccountResponse(
                id=account.id,
                email=account.email,
                role=principal.role,
                permissions=permissions_for(principal.role),
            )
        )
        self.db.add(self._session_row(account.id, session_data))
        self.db.commit()
        return session_data

    def sign_in(self, credentials: CredentialsInput) -> SessionData:
        account = self.db.scalar(
            select(Account).where(Account.email == credentials.email)
        )
        if account is None or not _verify_password(
            credentials.password, account.password_hash
        ):
            raise ApiError(
                401, "INVALID_CREDENTIALS", "The email or password is incorrect."
            )
        principal = self.organisations.membership_for(account.id)
        if principal is None:
            raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
        session_data = self._new_session(
            AccountResponse(
                id=account.id,
                email=account.email,
                role=principal.role,
                permissions=permissions_for(principal.role),
            )
        )
        self.db.add(self._session_row(account.id, session_data))
        self.db.commit()
        return session_data

    def sign_out(self, account_id: UUID, session_token: str | None) -> MessageResponse:
        if session_token:
            self.db.execute(
                delete(Session).where(
                    Session.account_id == account_id,
                    Session.token_hash == _sha256(session_token),
                )
            )
            self.db.commit()
        return MessageResponse(message="You have signed out.")

    def forgot_password(self, email: str) -> MessageResponse:
        account = self.db.scalar(select(Account).where(Account.email == email))
        if account is None:
            return MessageResponse(message=_RESET_MESSAGE)

        token = _token()
        self.db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.account_id == account.id
            )
        )
        self.db.add(
            PasswordResetToken(
                id=uuid7(),
                account_id=account.id,
                token_hash=_sha256(token),
                expires_at_utc=datetime.now(UTC) + _RESET_TOKEN_LIFETIME,
            )
        )
        self.db.commit()
        reset_url = (
            f"{self.settings.app_origin}/reset-password?{urlencode({'token': token})}"
        )
        self.mail_provider.send_password_reset(account.email, reset_url)
        return MessageResponse(message=_RESET_MESSAGE)

    def reset_password(self, input_data: ResetPasswordInput) -> MessageResponse:
        password_hash = _hash_password(input_data.password)
        with self.db.begin():
            reset = self.db.scalar(
                select(PasswordResetToken)
                .where(PasswordResetToken.token_hash == _sha256(input_data.token))
                .with_for_update()
            )
            now = datetime.now(UTC)
            if reset is None or reset.expires_at_utc <= now:
                raise ApiError(
                    400,
                    "RESET_TOKEN_INVALID",
                    "This reset link has expired. Request a new one.",
                )
            account = self.db.get(Account, reset.account_id)
            if account is None:
                raise ApiError(
                    400,
                    "RESET_TOKEN_INVALID",
                    "This reset link has expired. Request a new one.",
                )
            account.password_hash = password_hash
            self.db.execute(
                delete(PasswordResetToken).where(
                    PasswordResetToken.account_id == account.id
                )
            )
            self.db.execute(delete(Session).where(Session.account_id == account.id))
        return MessageResponse(
            message="Your password has been reset. Sign in with your new password."
        )

    @staticmethod
    def _new_session(account: AccountResponse) -> SessionData:
        return SessionData(
            account=account,
            session_token=_token(),
            csrf_token=_token(),
            expires_at_utc=datetime.now(UTC) + _SESSION_LIFETIME,
        )

    @staticmethod
    def _session_row(account_id: UUID, session_data: SessionData) -> Session:
        return Session(
            id=uuid7(),
            account_id=account_id,
            token_hash=_sha256(session_data.session_token),
            csrf_token_hash=_sha256(session_data.csrf_token),
            expires_at_utc=session_data.expires_at_utc,
        )
