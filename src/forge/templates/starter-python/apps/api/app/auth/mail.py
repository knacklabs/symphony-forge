from app.core import Settings, log_event


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
                "app.auth.mail",
                {"resetUrl": reset_url},
                environment=self.settings.app_env,
                correlation_id=self.correlation_id,
            )
