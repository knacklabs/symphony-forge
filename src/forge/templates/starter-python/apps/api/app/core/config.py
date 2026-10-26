import os
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_CURRENCY = "INR"


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str
    app_origin: str
    port: int
    app_companies: str


def load_settings() -> Settings:
    app_companies = os.environ.get("APP_COMPANIES", "many")
    if app_companies not in {"one", "many"}:
        raise RuntimeError("APP_COMPANIES must be one or many.")

    app_env = os.environ.get("APP_ENV", "")
    if not app_env:
        raise RuntimeError("APP_ENV must be set.")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL must contain a PostgreSQL connection URL.")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix(
            "postgres://"
        )
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix(
            "postgresql://"
        )
    elif not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must contain a PostgreSQL connection URL.")

    app_origin = os.environ.get("APP_ORIGIN", "")
    try:
        parsed_origin = urlsplit(app_origin)
        valid_origin = (
            parsed_origin.scheme in {"http", "https"}
            and bool(parsed_origin.netloc)
            and not parsed_origin.path
            and not parsed_origin.query
            and not parsed_origin.fragment
            and parsed_origin.geturl() == app_origin
        )
    except ValueError:
        valid_origin = False
    if not valid_origin:
        raise RuntimeError("APP_ORIGIN must be a valid HTTP or HTTPS origin URL.")

    port_value = os.environ.get("PORT", "")
    try:
        port = int(port_value)
    except ValueError as error:
        raise RuntimeError("PORT must be a valid TCP port.") from error
    if port < 1 or port > 65535:
        raise RuntimeError("PORT must be a valid TCP port.")

    return Settings(
        database_url=database_url,
        app_env=app_env,
        app_origin=app_origin,
        port=port,
        app_companies=app_companies,
    )


def load_admin_credentials() -> dict[str, str]:
    return {
        "email": os.environ.get("ADMIN_EMAIL", ""),
        "password": os.environ.get("ADMIN_PASSWORD", ""),
    }
