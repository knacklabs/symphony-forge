import hashlib
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import Account as AccountModel
from app.auth.models import Session as SessionModel
from app.auth.schema import (
    AcceptInviteInput,
    Account,
    CredentialsInput,
    ForgotPasswordInput,
    MessageResponse,
    ResetPasswordInput,
)
from app.auth.service import AuthService
from app.core import (
    AccountPrincipal,
    ApiError,
    ErrorEnvelope,
    MailProvider,
    Settings,
    SuccessEnvelope,
    admin_only,
    get_db,
    verify_csrf,
)
from app.history import HistoryService

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
invites_router = APIRouter(prefix="/api/v1/invites", tags=["Organisations"])


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _service(request: Request, db: DbSession) -> AuthService:
    # Import at request time: the organisations router also uses auth's session dependency.
    from app.organisations import OrganisationsService

    settings = _settings(request)
    correlation_id = cast(str | None, getattr(request.state, "correlation_id", None))
    return AuthService(
        db,
        settings,
        MailProvider(settings, correlation_id),
        OrganisationsService(db, HistoryService(db)),
    )


def current_account(
    request: Request, db: Annotated[DbSession, Depends(get_db)]
) -> AccountPrincipal:
    from app.organisations import OrganisationsService

    session_token = request.cookies.get("starter_session")
    if not session_token:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    session = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == session_hash)
    )
    if session is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
    if session.expires_at_utc <= datetime.now(UTC):
        db.delete(session)
        db.commit()
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")

    account = db.get(AccountModel, session.account_id)
    if account is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
    principal = OrganisationsService(db, HistoryService(db)).membership_for(account.id)
    if principal is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")
    request.state.csrf_token_hash = session.csrf_token_hash
    return principal


def require_csrf(
    request: Request,
    _account: Annotated[AccountPrincipal, Depends(current_account)],
) -> None:
    verify_csrf(request)


def _set_session_cookies(
    response: Response,
    session_token: str,
    csrf_token: str,
    expires_at_utc: datetime,
    settings: Settings,
) -> None:
    secure = settings.app_env not in {"development", "test"}
    max_age = int((expires_at_utc - datetime.now(UTC)).total_seconds())
    response.set_cookie(
        "starter_session",
        session_token,
        max_age=max_age,
        expires=expires_at_utc,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        "starter_csrf",
        csrf_token,
        max_age=max_age,
        expires=expires_at_utc,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    secure = settings.app_env not in {"development", "test"}
    response.delete_cookie(
        "starter_session", path="/", secure=secure, httponly=True, samesite="lax"
    )
    response.delete_cookie(
        "starter_csrf", path="/", secure=secure, httponly=False, samesite="lax"
    )


@router.post(
    "/sign-up",
    status_code=201,
    response_model=SuccessEnvelope[Account],
    responses={
        400: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        429: {"model": ErrorEnvelope},
    },
    summary="Create an account and start a session.",
)
def sign_up(
    request: Request,
    response: Response,
    credentials: CredentialsInput,
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Account]:
    settings = _settings(request)
    session = _service(request, db).sign_up(credentials)
    _set_session_cookies(
        response,
        session.session_token,
        session.csrf_token,
        session.expires_at_utc,
        settings,
    )
    return SuccessEnvelope(data=session.account)


@invites_router.post(
    "",
    status_code=201,
    response_model=SuccessEnvelope[MessageResponse],
    responses={
        status: {"model": ErrorEnvelope} for status in (400, 401, 403, 409, 422)
    },
    summary="Invite a person to your organisation.",
    description="Admins invite an email without an account. A new invite replaces its seven-day link. Production requires a mail provider.",
)
def invite(
    request: Request,
    input_data: ForgotPasswordInput,
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[MessageResponse]:
    return SuccessEnvelope(data=_service(request, db).invite(input_data.email, account))


@router.post(
    "/accept-invite",
    status_code=201,
    response_model=SuccessEnvelope[Account],
    responses={status: {"model": ErrorEnvelope} for status in (400, 409, 429)},
    summary="Join an organisation with an email invite.",
    description="The seven-day invite must match the email and works once. Creates an account and starts a session.",
)
def accept_invite(
    request: Request,
    response: Response,
    input_data: AcceptInviteInput,
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Account]:
    session = _service(request, db).accept_invite(input_data)
    _set_session_cookies(
        response,
        session.session_token,
        session.csrf_token,
        session.expires_at_utc,
        _settings(request),
    )
    return SuccessEnvelope(data=session.account)


@router.post(
    "/sign-in",
    response_model=SuccessEnvelope[Account],
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        429: {"model": ErrorEnvelope},
    },
    summary="Sign in and start a server session.",
)
def sign_in(
    request: Request,
    response: Response,
    credentials: CredentialsInput,
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[Account]:
    settings = _settings(request)
    session = _service(request, db).sign_in(credentials)
    _set_session_cookies(
        response,
        session.session_token,
        session.csrf_token,
        session.expires_at_utc,
        settings,
    )
    return SuccessEnvelope(data=session.account)


@router.get(
    "/me",
    response_model=SuccessEnvelope[Account],
    responses={401: {"model": ErrorEnvelope}},
    summary="Read the signed-in account.",
)
def me(
    account: Annotated[AccountPrincipal, Depends(current_account)],
) -> SuccessEnvelope[Account]:
    return SuccessEnvelope(
        data=Account(id=account.id, email=account.email, role=account.role)
    )


@router.post(
    "/sign-out",
    response_model=SuccessEnvelope[MessageResponse],
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
    summary="End the current server session.",
)
def sign_out(
    request: Request,
    response: Response,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    db: Annotated[DbSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> SuccessEnvelope[MessageResponse]:
    _clear_session_cookies(response, _settings(request))
    message = _service(request, db).sign_out(
        account.id, request.cookies.get("starter_session")
    )
    return SuccessEnvelope(data=message)


@router.post(
    "/forgot-password",
    response_model=SuccessEnvelope[MessageResponse],
    responses={400: {"model": ErrorEnvelope}, 429: {"model": ErrorEnvelope}},
    summary="Request a password reset link.",
)
def forgot_password(
    request: Request,
    input_data: ForgotPasswordInput,
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[MessageResponse]:
    message = _service(request, db).forgot_password(input_data.email)
    return SuccessEnvelope(data=message)


@router.post(
    "/reset-password",
    response_model=SuccessEnvelope[MessageResponse],
    responses={400: {"model": ErrorEnvelope}, 429: {"model": ErrorEnvelope}},
    summary="Set a new password with a single-use reset link.",
)
def reset_password(
    request: Request,
    input_data: ResetPasswordInput,
    db: Annotated[DbSession, Depends(get_db)],
) -> SuccessEnvelope[MessageResponse]:
    message = _service(request, db).reset_password(input_data)
    return SuccessEnvelope(data=message)
