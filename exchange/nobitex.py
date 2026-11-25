import asyncio
import base64
import json
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import FRAMES, Settings, load_yaml
from exchange.base import (
    Balance,
    Blocked,
    Book,
    Candle,
    Exchange,
    ExchangeError,
    NotFound,
    Order,
    Request,
    Rules,
    Side,
    State,
    TemporaryError,
    number,
)

READ_ONLY = frozenset(
    {
        "candles",
        "book",
        "books",
        "market_stats",
        "options",
        "profile",
        "balances",
        "orders",
        "status",
    }
)
CHECKS = frozenset(
    {
        "authenticated_read_contract",
        "fee_currency_and_fill_accounting",
        "terminal_client_order_id_recovery",
        "live_limit_and_cancel_semantics",
        "executable_symbol_precision",
        "native_protection_lifecycle",
    }
)


@dataclass(frozen=True, slots=True)
class Spec:
    raw: dict

    @classmethod
    def load(cls) -> "Spec":
        return cls(load_yaml("exchange/nobitex_spec.yaml"))

    def unverified(self) -> list[str]:
        checks = self.raw.get("verification", {})
        # Write semantics cannot be promoted by editing YAML or by a successful read probe.
        return sorted({*CHECKS, *(k for k, v in checks.items() if v != "VERIFIED")})

    def offset(self, frame: str) -> int:
        try:
            value = self.raw["alignment_by_frame"][frame]
            if type(value) is not int or not 0 <= value < FRAMES[frame]:
                raise ValueError
            return value
        except (KeyError, TypeError, ValueError):
            raise Blocked("Missing or invalid exchange candle alignment") from None


class NobitexClient(Exchange):
    def __init__(self, spec: Spec, http: httpx.AsyncClient, settings: Settings | None = None):
        self.spec, self.http = spec, http
        self.lock = asyncio.Lock()
        self.next_call: dict[str, float] = {}
        self.key: str | None = None
        self.signer: Ed25519PrivateKey | None = None
        self.options_cache: tuple[float, dict] | None = None
        if spec.raw.get("base_url") != "https://apiv2.nobitex.ir":
            raise Blocked("Unexpected Nobitex origin")
        if settings and settings.nobitex_private_key and settings.nobitex_public_key:
            try:
                self.key = settings.nobitex_public_key.get_secret_value()
                self.signer = Ed25519PrivateKey.from_private_bytes(
                    base64.b64decode(
                        settings.nobitex_private_key.get_secret_value(),
                        altchars=b"-_",
                        validate=True,
                    )
                )
            except (ValueError, TypeError):
                raise Blocked("Invalid Nobitex signing key format") from None

    async def _call(
        self, name: str, *, params: dict | None = None, body: dict | None = None, symbol: str = ""
    ) -> dict[str, Any]:
        if name not in READ_ONLY:
            raise Blocked("UNVERIFIED Nobitex writes are disabled in this build")
        method, pattern, auth, rpm = self.spec.raw["endpoints"][name]
        path = pattern.format(symbol=symbol.replace("/", ""))
        if not path.startswith("/") or path.startswith("//"):
            raise Blocked("Unexpected Nobitex endpoint")
        raw = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
        for attempt in range(3):
            async with self.lock:
                await asyncio.sleep(max(0, self.next_call.get(name, 0) - time.monotonic()))
                self.next_call[name] = time.monotonic() + 60 / rpm
            headers = {"User-Agent": "TraderBot/NobitexBaleTrader-0.1"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            req = self.http.build_request(
                method,
                self.spec.raw["base_url"] + path,
                params=params,
                content=raw,
                headers=headers,
            )
            if auth:
                if not self.signer or not self.key:
                    raise Blocked("Nobitex READ key pair required")
                auth_spec = self.spec.raw["auth"]
                timestamp = str(int(time.time()))
                signed = timestamp.encode() + method.encode() + req.url.raw_path + raw
                req.headers[auth_spec["key_header"]] = self.key
                req.headers[auth_spec["timestamp_header"]] = timestamp
                req.headers[auth_spec["signature_header"]] = base64.urlsafe_b64encode(
                    self.signer.sign(signed)
                ).decode()
            retry_after = 0.0
            try:
                response = await self.http.send(req, follow_redirects=False)
                status = response.status_code
                if 200 <= status < 300:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ExchangeError("Unexpected Nobitex response")
                    if data.get("status") == "ok" or data.get("s") in {"ok", "no_data"}:
                        return data
                    if name == "status" and data.get("code") in {"OrderNotFound", "NotFound"}:
                        raise NotFound("Order not found")
                    raise ExchangeError(f"Nobitex rejected {name}")
                if status in {401, 403}:
                    raise Blocked(f"Nobitex {name}: HTTP {status} (access/permissions/IP)")
                if status != 429 and status < 500:
                    raise ExchangeError(f"Nobitex {name}: HTTP {status}")
                header = response.headers.get("Retry-After", "")
                if header.isascii() and header.isdigit() and len(header) < 8:
                    retry_after = float(header)
            except httpx.RequestError:
                pass
            except (ValueError, TypeError):
                raise ExchangeError(f"Malformed Nobitex {name} response") from None
            if retry_after:
                self.next_call[name] = max(self.next_call[name], time.monotonic() + retry_after)
            if attempt < 2 and retry_after <= 10:
                await asyncio.sleep(max(retry_after, 0.5 * 2**attempt + random.random() / 4))
            else:
                break
        raise TemporaryError(f"Nobitex {name} unavailable after bounded retries")

    async def get_candles(self, symbol: str, frame: str, start: int, end: int) -> list[Candle]:
        if end <= start or end - start > self.spec.raw["history_limit"] * FRAMES[frame]:
            raise ExchangeError("Invalid candle request window")
        data = await self._call(
            "candles",
            params={
                "symbol": symbol.replace("/", ""),
                "resolution": self.spec.raw["resolutions"][frame],
                "from": start,
                "to": end - 1,
            },
        )
        if data["s"] == "no_data":
            return []
        try:
            if any(
                not isinstance(data[k], list) or len(data[k]) > self.spec.raw["history_limit"]
                for k in "tohlcv"
            ) or any(type(ts) is not int for ts in data["t"]):
                raise ValueError
            rows = [
                Candle(int(ts), *map(float, values))
                for ts, *values in zip(*(data[k] for k in "tohlcv"), strict=True)
                if start <= int(ts) < end
            ]
            if len({x.ts for x in rows}) != len(rows):
                raise ValueError
            return sorted(rows, key=lambda x: x.ts)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ExchangeError("Malformed Nobitex candles") from None

    async def get_orderbook(self, symbol: str) -> Book:
        return self.parse_book(await self._call("book", symbol=symbol))

    @staticmethod
    def parse_book(data: dict) -> Book:
        try:

            def levels(key: str, reverse: bool) -> tuple:
                return tuple(
                    sorted(((number(p), number(q)) for p, q in data[key]), reverse=reverse)
                )

            book = Book(
                int(data["lastUpdate"]) // 1000, levels("bids", True), levels("asks", False)
            )
            if not (0 < book.bid < book.ask) or any(
                p <= 0 or q <= 0 for p, q in (*book.bids, *book.asks)
            ):
                raise ValueError
            return book
        except (KeyError, TypeError, ValueError, IndexError):
            raise ExchangeError("Malformed, empty or crossed Nobitex order book") from None

    async def options(self) -> dict:
        if self.options_cache is None or time.monotonic() - self.options_cache[0] > 300:
            self.options_cache = (time.monotonic(), await self._call("options"))
        return self.options_cache[1]

    async def get_symbol_rules(self, symbol: str) -> Rules:
        options = await self.options()
        fields = self.spec.raw["precision"]
        key = symbol.replace("/", "")
        try:
            obj = options["nobitex"]
            values = (
                number(obj[fields["quantity_key"]][key]),
                number(obj[fields["price_key"]][key]),
                number(obj[fields["minimum_key"]][symbol.split("/")[1].lower()]),
            )
            if min(values) <= 0:
                raise ValueError
            return Rules(*values)
        except (KeyError, TypeError, ValueError):
            raise ExchangeError("Nobitex public symbol rules absent or malformed") from None

    async def get_fees(self, symbol: str) -> Decimal:
        # Public conservative ceiling, not an authenticated account fee contract.
        try:
            values = (await self.options())["nobitex"]["tradingFees"]["takerFeesTether"]
            fee = max(number(v) for v in values) / 100
            if fee >= Decimal("0.1"):
                raise ValueError
            return fee
        except (KeyError, TypeError, ValueError):
            raise ExchangeError("Nobitex public fee schedule unavailable") from None

    async def profile(self) -> None:
        result = await self._call("profile")
        if not isinstance(result.get("profile"), dict):
            raise ExchangeError("Unexpected Nobitex profile schema")

    async def get_balances(self) -> dict[str, Balance]:
        data = await self._call("balances", body={"currencies": "btc,usdt", "type": "spot"})
        try:
            result = {}
            for symbol in ("BTC", "USDT"):
                wallet = data["wallets"][symbol.lower()]
                total, blocked = number(wallet["balance"]), number(wallet["blocked"])
                if total < blocked:
                    raise ValueError
                result[symbol] = Balance(total - blocked, total)
            return result
        except (KeyError, TypeError, ValueError):
            raise ExchangeError("Unexpected Nobitex wallet schema") from None

    @staticmethod
    def _order(obj: dict) -> Order:
        try:
            filled = number(obj["matchedAmount"])
            status = obj["status"].lower()
            state = {
                "new": State.OPEN,
                "active": State.OPEN,
                "inactive": State.OPEN,
                "done": State.FILLED,
                "canceled": State.CANCELLED,
                "rejected": State.REJECTED,
            }[status]
            if state == State.OPEN and filled:
                state = State.PARTIAL
            side = Side(obj["type"])
            fee = number(obj["fee"])
            # UNVERIFIED: provisional fee direction; this adapter is read-only.
            return Order(
                str(int(obj["id"])),
                state,
                filled,
                number(obj["totalPrice"]),
                fee if side == Side.BUY else Decimal(0),
                fee if side == Side.SELL else Decimal(0),
                obj.get("clientOrderId"),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ExchangeError("Unexpected Nobitex order schema") from None

    async def list_open_orders(self, symbol: str) -> list[Order]:
        src, dst = symbol.lower().split("/")
        result: list[Order] = []
        for page in range(1, 21):
            data = await self._call(
                "orders",
                params={
                    "status": "open",
                    "tradeType": "spot",
                    "srcCurrency": src,
                    "dstCurrency": dst,
                    "details": 2,
                    "page": page,
                    "pageSize": 100,
                },
            )
            rows = data.get("orders")
            if not isinstance(rows, list):
                raise ExchangeError("Unexpected Nobitex order-list schema")
            result.extend(map(self._order, rows))
            if len(rows) < 100 and not data.get("hasNext"):
                if len({o.id for o in result}) != len(result) or any(
                    o.state.terminal for o in result
                ):
                    raise ExchangeError("Inconsistent Nobitex open orders")
                return result
        raise ExchangeError("Nobitex order pagination limit reached")

    async def get_order(self, symbol: str, order_id: str, *, by_client: bool = False) -> Order:
        data = await self._call(
            "status", body={"clientOrderId": order_id} if by_client else {"id": int(order_id)}
        )
        return self._order(data.get("order", {}))

    async def place_order(self, symbol: str, request: Request) -> Order:
        raise Blocked("UNVERIFIED live placement is not enabled in this build")

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        raise Blocked("UNVERIFIED live cancellation is not enabled in this build")
