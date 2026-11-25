from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from math import isfinite

D = Decimal


class ExchangeError(Exception):
    """An exchange failure with a locally controlled diagnostic."""


class TemporaryError(ExchangeError):
    pass


class NotFound(ExchangeError):
    pass


class Blocked(ExchangeError):
    pass


def number(value: object) -> D:
    try:
        result = D(str(value))
    except (ValueError, InvalidOperation):
        raise ExchangeError("Malformed numeric response") from None
    if not result.is_finite() or result < 0 or result.adjusted() > 16:
        raise ExchangeError("Invalid numeric response")
    return result


@dataclass(frozen=True, slots=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if (
            type(self.ts) is not int
            or self.ts < 0
            or not all(map(isfinite, (self.open, self.high, self.low, self.close, self.volume)))
            or not 0
            < self.low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.high
            or self.volume < 0
        ):
            raise ValueError("Invalid OHLCV row")


@dataclass(frozen=True, slots=True)
class Book:
    ts: int
    bids: tuple[tuple[D, D], ...]
    asks: tuple[tuple[D, D], ...]

    @property
    def bid(self) -> D:
        return self.bids[0][0]

    @property
    def ask(self) -> D:
        return self.asks[0][0]


@dataclass(frozen=True, slots=True)
class Rules:
    quantity_step: D
    price_tick: D
    min_quote: D
    min_quantity: D = D(0)

    def __post_init__(self) -> None:
        if (
            not all(
                v.is_finite()
                for v in (self.quantity_step, self.price_tick, self.min_quote, self.min_quantity)
            )
            or min(self.quantity_step, self.price_tick, self.min_quote) <= 0
            or self.min_quantity < 0
        ):
            raise ValueError("Invalid symbol rules")


@dataclass(frozen=True, slots=True)
class Balance:
    free: D
    total: D

    def __post_init__(self) -> None:
        if (
            not self.free.is_finite()
            or not self.total.is_finite()
            or not 0 <= self.free <= self.total
        ):
            raise ValueError("Invalid balance")


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class State(StrEnum):
    SUBMITTING = "submitting"
    UNKNOWN = "unknown"
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    @property
    def terminal(self) -> bool:
        return self in (State.FILLED, State.CANCELLED, State.REJECTED)


@dataclass(frozen=True, slots=True)
class Request:
    client_id: str
    side: Side
    quantity: D
    limit: D
    stop_distance: D = D(0)

    def __post_init__(self) -> None:
        if (
            not self.client_id
            or len(self.client_id) > 64
            or self.side not in (Side.BUY, Side.SELL)
            or not all(v.is_finite() for v in (self.quantity, self.limit, self.stop_distance))
            or min(self.quantity, self.limit) <= 0
            or self.stop_distance < 0
        ):
            raise ValueError("Invalid order request")


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    state: State
    filled: D = D(0)
    quote: D = D(0)
    fee_base: D = D(0)
    fee_quote: D = D(0)
    client_id: str | None = None

    def __post_init__(self) -> None:
        if not all(
            v.is_finite() and v >= 0
            for v in (self.filled, self.quote, self.fee_base, self.fee_quote)
        ):
            raise ValueError("Invalid cumulative order amounts")


class MarketData(ABC):
    @abstractmethod
    async def get_candles(self, symbol: str, frame: str, start: int, end: int) -> list[Candle]: ...

    @abstractmethod
    async def get_orderbook(self, symbol: str) -> Book: ...

    @abstractmethod
    async def get_symbol_rules(self, symbol: str) -> Rules: ...


class Exchange(MarketData):
    @abstractmethod
    async def get_balances(self) -> dict[str, Balance]: ...

    @abstractmethod
    async def place_order(self, symbol: str, request: Request) -> Order: ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Order: ...

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str, *, by_client: bool = False) -> Order: ...

    @abstractmethod
    async def list_open_orders(self, symbol: str) -> list[Order]: ...

    @abstractmethod
    async def get_fees(self, symbol: str) -> D: ...
