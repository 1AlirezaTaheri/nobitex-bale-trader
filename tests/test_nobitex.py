import asyncio
import base64
import time
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import Settings
from exchange.base import Blocked, ExchangeError, TemporaryError
from exchange.nobitex import READ_ONLY, NobitexClient, Spec

D = Decimal


def test_ed25519_signature_covers_exact_request_path_and_bytes():
    signer = Ed25519PrivateKey.generate()
    key = base64.urlsafe_b64encode(signer.private_bytes_raw()).decode()
    settings = Settings(
        _env_file=None, nobitex_public_key="test-public-key", nobitex_private_key=key
    )
    captured = []

    def handler(request):
        captured.append(request)
        timestamp = request.headers["Nobitex-Timestamp"]
        payload = (
            timestamp.encode() + request.method.encode() + request.url.raw_path + request.content
        )
        signer.public_key().verify(
            base64.urlsafe_b64decode(request.headers["Nobitex-Signature"]), payload
        )
        assert request.headers["Nobitex-Key"] == "test-public-key"
        assert key.encode() not in request.content
        if request.url.path == "/v2/wallets":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "wallets": {
                        "btc": {"balance": "0", "blocked": "0"},
                        "usdt": {"balance": "100", "blocked": "2"},
                    },
                },
            )
        return httpx.Response(200, json={"status": "ok", "orders": []})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = NobitexClient(Spec.load(), http, settings)
            balances = await client.get_balances()
            assert balances["USDT"].free == 98
            assert await client.list_open_orders("BTC/USDT") == []

    asyncio.run(scenario())
    assert len(captured) == 2
    assert captured[1].url.query


def test_public_market_requests_never_attach_credentials():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "lastUpdate": int(time.time()) * 1000,
                "bids": [["100", "1"]],
                "asks": [["101", "1"]],
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            book = await NobitexClient(Spec.load(), http).get_orderbook("BTC/USDT")
            assert book.bid == 100 and book.ask == 101

    asyncio.run(scenario())
    assert not any(k.startswith("nobitex-") for k in seen[0].headers)


def test_retry_get_is_bounded_and_redacts_external_errors(monkeypatch):
    async def no_sleep(*args):
        pass

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, text="sensitive upstream error")

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(TemporaryError) as error:
                await NobitexClient(Spec.load(), http).get_orderbook("BTC/USDT")
            assert "sensitive" not in str(error.value)

    asyncio.run(scenario())
    assert len(calls) == 3


def test_long_retry_after_is_not_ignored():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "60"})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = NobitexClient(Spec.load(), http)
            with pytest.raises(TemporaryError):
                await client.get_orderbook("BTC/USDT")
            assert client.next_call["book"] - time.monotonic() > 59

    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "ok", "bids": [], "asks": []},
        {"status": "ok", "lastUpdate": 0, "bids": [["NaN", "1"]], "asks": [["101", "1"]]},
        {"status": "ok", "lastUpdate": 0, "bids": [["102", "1"]], "asks": [["101", "1"]]},
    ],
)
def test_bad_books_refused(payload):
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as http:
            with pytest.raises(ExchangeError):
                await NobitexClient(Spec.load(), http).get_orderbook("BTC/USDT")

    asyncio.run(scenario())


def test_malformed_candle_arrays_not_silently_truncated():
    payload = {
        "s": "ok",
        "t": [1800, 16200],
        "o": [100],
        "h": [102],
        "l": [99],
        "c": [101],
        "v": [1],
    }

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as http:
            with pytest.raises(ExchangeError):
                await NobitexClient(Spec.load(), http).get_candles("BTC/USDT", "4h", 1800, 30600)

    asyncio.run(scenario())


def test_historical_udf_zero_volume_is_preserved_not_coerced_to_missing():
    payload = {
        "s": "ok",
        "t": [1690317000, 1700080200, 1794947400],
        "o": [29200, 37451.7, 64000.05],
        "h": [29479, 37750, 65153],
        "l": [29100, 35555, 62500],
        "c": [29473.07, 35896.55, 62682.49],
        "v": [0, 0, 21.2926200334],
    }

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as http:
            client = NobitexClient(Spec.load(), http)
            old = await client.get_candles("BTC/USDT", "1d", 1690317000, 1690317000 + 86400)
            recent_zero = await client.get_candles("BTC/USDT", "1d", 1700080200, 1700080200 + 86400)
            recent_volume = await client.get_candles(
                "BTC/USDT", "1d", 1794947400, 1794947400 + 86400
            )
            assert [row.volume for row in old + recent_zero] == [0.0, 0.0]
            assert [row.volume for row in recent_volume] == [21.2926200334]

    asyncio.run(scenario())


def test_public_precision_and_fee_schema():
    payload = {
        "status": "ok",
        "nobitex": {
            "amountPrecisions": {"BTCUSDT": "0.000001"},
            "pricePrecisions": {"BTCUSDT": "0.01"},
            "minOrders": {"usdt": "0.5"},
            "tradingFees": {"takerFeesTether": ["0.13", "0.095"]},
        },
    }

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as http:
            client = NobitexClient(Spec.load(), http)
            rules = await client.get_symbol_rules("BTC/USDT")
            assert rules.quantity_step == D("0.000001")
            assert rules.price_tick == D("0.01")
            assert await client.get_fees("BTC/USDT") == D("0.0013")

    asyncio.run(scenario())


def test_no_withdrawal_transfer_or_mutating_api_transport():
    assert READ_ONLY == {
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

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("Network forbidden"))
        ) as http:
            with pytest.raises(Blocked):
                await NobitexClient(Spec.load(), http)._call("place", body={})

    asyncio.run(scenario())


def test_exchange_alignment_is_frame_specific():
    spec = Spec.load()
    assert spec.offset("4h") == 1800
    assert spec.offset("1h") == 1800
    assert spec.offset("1d") == 73800
    spec.raw["alignment_by_frame"]["4h"] = 14400
    with pytest.raises(Blocked):
        spec.offset("4h")


@pytest.mark.parametrize("ts", [1800.7, True, "1800"])
def test_candle_timestamp_is_not_silently_truncated_or_coerced(ts):
    payload = {"s": "ok", "t": [ts], "o": [100], "h": [102], "l": [99], "c": [101], "v": [1]}

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ) as http:
            with pytest.raises(ExchangeError):
                await NobitexClient(Spec.load(), http).get_candles("BTC/USDT", "4h", 1800, 16200)

    asyncio.run(scenario())
