import os
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from urllib.parse import urlsplit

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


@dataclass(frozen=True)
class ModelSettings:
    key: SecretStr = field(repr=False)
    model: str
    cap_micros: int
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal
    base_url: str | None = None

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        # USD per million tokens times tokens is already micro-dollars.
        return int(
            (
                input_tokens * self.input_usd_per_mtok
                + output_tokens * self.output_usd_per_mtok
            ).to_integral_value(rounding=ROUND_CEILING)
        )


def load_settings() -> ModelSettings:
    # This optional module owns its provider settings. Importing it reads none.
    values = os.environ
    key = values.get("ASSISTANT_AI_KEY", "").strip()
    model = values.get("ASSISTANT_MODEL", "").strip()
    if not key:
        raise RuntimeError("ASSISTANT_AI_KEY must be set.")
    if not model:
        raise RuntimeError("ASSISTANT_MODEL must be set.")

    def number(name: str) -> Decimal:
        value = values.get(name, "").strip()
        if not value:
            raise RuntimeError(f"{name} must be set.")
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            raise RuntimeError(
                f"{name} must be a finite non-negative number."
            ) from None
        if not parsed.is_finite() or parsed < 0:
            raise RuntimeError(f"{name} must be a finite non-negative number.")
        return parsed

    cap = number("ASSISTANT_SPEND_CAP_USD") * 1_000_000
    if cap != cap.to_integral_value():
        raise RuntimeError(
            "ASSISTANT_SPEND_CAP_USD must use at most six decimal places."
        )
    base_url = values.get("ASSISTANT_AI_URL", "").strip() or None
    if base_url is not None:
        try:
            url = urlsplit(base_url)
            valid = url.scheme in {"http", "https"} and bool(url.hostname)
            valid = valid and not url.username and not url.password and not url.fragment
        except ValueError:
            valid = False
        if not valid:
            raise RuntimeError(
                "ASSISTANT_AI_URL must be an HTTP or HTTPS URL without credentials."
            )
    return ModelSettings(
        key=SecretStr(key),
        model=model,
        cap_micros=int(cap),
        input_usd_per_mtok=number("ASSISTANT_PRICE_INPUT_USD_PER_MTOK"),
        output_usd_per_mtok=number("ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK"),
        base_url=base_url,
    )


def create_model(settings: ModelSettings) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.key,
        model=settings.model,
        base_url=settings.base_url,
        timeout=20,
        max_retries=1,
        stream_usage=True,
    )
