from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
FRAMES = {"1h": 3600, "4h": 14400, "1d": 86400}
D = Decimal


class ConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="forbid", hide_input_in_errors=True, env_ignore_empty=True
    )
    mode: Literal["paper", "live"] = "paper"
    nobitex_public_key: SecretStr | None = None
    nobitex_private_key: SecretStr | None = None
    bale_bot_token: SecretStr | None = None
    bale_chat_id: int | None = Field(default=None, gt=0)
    max_capital_quote: D = Field(default=D(100), gt=0, le=1000000)
    allow_unprotected_positions: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, dotenv_settings

    @model_validator(mode="after")
    def pairs(self) -> "Settings":
        if bool(self.bale_bot_token) != (self.bale_chat_id is not None):
            raise ValueError("Configure both BALE_BOT_TOKEN and BALE_CHAT_ID or neither")
        if bool(self.nobitex_public_key) != bool(self.nobitex_private_key):
            raise ValueError("Configure both Nobitex API keys or neither")
        return self


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, frozen=True, allow_inf_nan=False
    )


class StrategyConfig(Strict):
    name: Literal["trend", "rsi"]
    symbol: Literal["BTC/USDT"]
    timeframe: Literal["1h", "4h", "1d"]
    fast: int = Field(gt=1, le=500)
    slow: int = Field(gt=1, le=500)
    trend: int = Field(gt=1, le=500)
    atr_period: int = Field(gt=1, le=200)
    atr_multiplier: float = Field(gt=0, le=20)
    min_atr_pct: float = Field(ge=0, lt=1)
    rsi_period: int = Field(gt=1, le=200)
    rsi_entry: float = Field(gt=0, lt=100)
    rsi_exit: float = Field(gt=0, lt=100)

    @field_validator("fast", "slow", "trend", "atr_period", "rsi_period", mode="before")
    @classmethod
    def strict_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("must be an integer")
        return value

    @model_validator(mode="after")
    def validate_periods(self) -> "StrategyConfig":
        if not self.fast < self.slow < self.trend or self.rsi_entry >= self.rsi_exit:
            raise ValueError("Require fast < slow < trend and rsi_entry < rsi_exit")
        return self

    @property
    def seconds(self) -> int:
        return FRAMES[self.timeframe]

    @property
    def warmup(self) -> int:
        return 3 * max(self.trend, self.atr_period, self.rsi_period) + 2


class RiskConfig(Strict):
    risk_pct: D = Field(gt=0, le=D("0.05"))
    max_positions: Literal[1]
    max_order_quote: D = Field(gt=0)
    max_daily_loss: D = Field(gt=0, lt=1)
    max_drawdown: D = Field(gt=0, lt=1)
    consecutive_losses: int = Field(gt=0, le=20)
    cooldown_bars: int = Field(gt=0, le=100)
    fee: D = Field(ge=0, lt=D("0.1"))
    slippage: D = Field(ge=0, lt=D("0.1"))
    max_spread: D = Field(gt=0, lt=D("0.1"))


class AppConfig(Strict):
    paper_cash: D = Field(gt=0, le=1000000)
    poll_seconds: int = Field(ge=5, le=60)
    reconcile_seconds: int = Field(ge=30, le=900)
    heartbeat_seconds: int = Field(ge=30)
    close_grace_seconds: int = Field(ge=0, le=60)
    entry_delay_seconds: int = Field(gt=60, le=600)
    order_timeout_seconds: int = Field(ge=10, le=300)
    api_error_limit: int = Field(ge=1, le=10)
    book_max_age_seconds: int = Field(ge=15, le=300)
    data_directory: Literal["data"]


def load_yaml(path: str) -> dict:
    try:
        result = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ConfigError(f"Expected a mapping in {path}")
        return result
    except (OSError, yaml.YAMLError):
        raise ConfigError(f"Cannot read or parse {path}") from None


def load() -> tuple[Settings, StrategyConfig, RiskConfig, AppConfig]:
    try:
        return (
            Settings(),
            StrategyConfig(**legacy_section("config/strategy.yaml")),
            RiskConfig(**legacy_section("config/risk.yaml")),
            AppConfig(**load_yaml("config/app.yaml")),
        )
    except ValidationError as exc:
        known = set().union(
            *(m.model_fields for m in (Settings, StrategyConfig, RiskConfig, AppConfig))
        )
        details = [
            f"{'.'.join(map(str, e['loc'])) if e['loc'] and e['loc'][0] in known else 'configuration'}"
            f" ({e['type']})"
            for e in exc.errors(include_input=False)
        ]
        raise ConfigError("Invalid " + ", ".join(details)) from None


def legacy_section(path: str) -> dict:
    values = load_yaml(path)
    values.pop("portfolio", None)
    return values
