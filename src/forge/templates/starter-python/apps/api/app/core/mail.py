from app.core.config import Settings
from app.core.errors import ApiError
from app.core.logging import log_event


class MailProvider:
    def __init__(self, settings: Settings, correlation_id: str | None) -> None:
        self.settings = settings
        self.correlation_id = correlation_id

    def send_password_reset(self, _email: str, reset_url: str) -> None:
        if self.settings.app_env in {"development", "test"}:
            log_event(
                None,
                "info",
                "Password reset link created for local mail",
                "app.core.mail",
                {"resetUrl": reset_url},
                environment=self.settings.app_env,
                correlation_id=self.correlation_id,
            )

    def send_invite(self, _email: str, invite_url: str) -> None:
        if self.settings.app_env not in {"development", "test"}:
            raise ApiError(
                422, "MAIL_NOT_CONFIGURED", "Email is not set up for this app yet."
            )
        log_event(
            None,
            "info",
            "Invite link created for local mail",
            "app.core.mail",
            {"inviteUrl": invite_url},
            environment=self.settings.app_env,
            correlation_id=self.correlation_id,
        )
