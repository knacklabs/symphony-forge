import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.auth.mail import MailProvider
from app.auth.models import Account, PasswordResetToken, Session
from app.auth.schema import Account as AccountResponse
from app.auth.schema import (
    CredentialsInput,
    MessageResponse,
    ResetPasswordInput,
    SessionData,
)
from app.core import ApiError, Settings

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


class AuthService:
    def __init__(
        self, db: DbSession, settings: Settings, mail_provider: MailProvider
    ) -> None:
        self.db = db
        self.settings = settings
        self.mail_provider = mail_provider

    def sign_up(self, credentials: CredentialsInput) -> SessionData:
        account_id = uuid4()
        account = Account(
            id=account_id,
            email=credentials.email,
            password_hash=_hash_password(credentials.password),
            created_by_account_id=account_id,
            modified_by_account_id=account_id,
        )
        session_data = self._new_session(
            AccountResponse(id=account_id, email=credentials.email)
        )
        try:
            self.db.add(account)
            self.db.flush()
            self.db.add(self._session_row(account_id, session_data))
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ApiError(
                409,
                "EMAIL_ALREADY_REGISTERED",
                "An account already uses that email.",
            ) from error
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
        session_data = self._new_session(
            AccountResponse(id=account.id, email=account.email)
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
                id=uuid4(),
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
            id=uuid4(),
            account_id=account_id,
            token_hash=_sha256(session_data.session_token),
            csrf_token_hash=_sha256(session_data.csrf_token),
            expires_at_utc=session_data.expires_at_utc,
        )
