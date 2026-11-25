"""Strict configuration for the isolated daily timing PAPER experiment."""

from typing import Literal

from pydantic import Field, ValidationError, model_validator

from app.config import ConfigError, Strict, load_yaml


class TimingConfig(Strict):
    enabled: bool = False
    candidate: Literal["A", "B", "C", "D"] = "A"
    symbols: tuple[Literal["BTC/USDT", "ETH/USDT"], ...] = ("BTC/USDT", "ETH/USDT")
    preregistration: str = "docs/STRATEGY_V3_PREREGISTRATION.md"
    warmup: int = Field(default=300, ge=300, le=3000)

    @model_validator(mode="after")
    def unique_symbols(self):
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("Timing PAPER symbols must be unique")
        return self


def load_timing():
    try:
        return TimingConfig(**load_yaml("config/timing.yaml"))
    except ValidationError as error:
        names = ", ".join(
            ".".join(map(str, item["loc"])) for item in error.errors(include_input=False)
        )
        raise ConfigError("Invalid timing configuration: " + names) from None
