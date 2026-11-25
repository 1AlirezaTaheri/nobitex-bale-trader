import re

from pydantic import Field, ValidationError, field_validator

from app.config import ConfigError, Strict, load_yaml
from risk.portfolio import PortfolioLimits
from strategy.layered import LayeredConfig


class Universe(Strict):
    symbols: tuple[str, ...] = Field(min_length=4, max_length=6)

    @field_validator("symbols")
    @classmethod
    def symbols_valid(cls, symbols):
        if (
            "BTC/USDT" not in symbols
            or len(set(symbols)) != len(symbols)
            or any(
                not re.fullmatch(r"[A-Z0-9_]{1,18}/USDT", s) or s == "USDT/USDT" for s in symbols
            )
        ):
            raise ValueError("Use 4-6 distinct uppercase USDT spot pairs including BTC/USDT")
        return tuple(sorted(symbols))


def load_portfolio():
    results = []
    for path, schema, nested in (
        ("config/strategy.yaml", LayeredConfig, True),
        ("config/risk.yaml", PortfolioLimits, True),
        ("config/universe.yaml", Universe, False),
    ):
        raw = load_yaml(path)
        try:
            results.append(schema.model_validate(raw.get("portfolio", {}) if nested else raw))
        except ValidationError as error:
            fields = ", ".join(
                ".".join(map(str, e["loc"])) or "cross-field limits"
                for e in error.errors(include_input=False)
            )
            raise ConfigError(f"Invalid portfolio configuration in {path}: {fields}") from None
    return tuple(results)
