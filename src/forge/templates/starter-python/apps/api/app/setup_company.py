import sys

from pydantic import ValidationError

from app.auth import AuthService, CredentialsInput
from app.core import (
    ApiError,
    MailProvider,
    create_database,
    load_admin_credentials,
    load_settings,
)
from app.history import HistoryService
from app.organisations import OrganisationsService


def main() -> int:
    try:
        settings = load_settings()
    except RuntimeError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    credentials = CredentialsInput.model_validate(load_admin_credentials())
    engine, session_factory = create_database(settings.database_url)
    try:
        with session_factory() as db:
            service = AuthService(
                db,
                settings,
                MailProvider(settings, None),
                OrganisationsService(db, HistoryService(db)),
            )
            service.set_up_company(credentials)
            db.commit()
    finally:
        engine.dispose()
    sys.stdout.write("The company and its first admin are ready.\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as error:
        for issue in error.errors():
            sys.stderr.write(f"{issue['msg']}\n")
        raise SystemExit(1) from None
    except ApiError as error:
        sys.stderr.write(f"{error.message}\n")
        raise SystemExit(1) from None
    except Exception:
        sys.stderr.write(
            "Company setup failed. Check the app settings and database, then try again.\n"
        )
        raise SystemExit(1) from None
