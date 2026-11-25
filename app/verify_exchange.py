import asyncio
import time

import httpx

from app.config import ConfigError, load
from data.history import boundary
from exchange.base import ExchangeError
from exchange.nobitex import NobitexClient, Spec


async def verify() -> int:
    settings, cfg, _, _ = load()
    spec = Spec.load()
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        market = NobitexClient(spec, http)
        now = int(time.time())
        end = boundary(now, cfg.seconds, spec.offset(cfg.timeframe))
        try:
            rows = await market.get_candles(cfg.symbol, cfg.timeframe, end - 4 * cfg.seconds, end)
            if not rows or rows[-1].ts != end - cfg.seconds:
                raise ExchangeError("Latest expected closed candle missing")
            print("PASS public candles")
            book = await market.get_orderbook(cfg.symbol)
            if not -10 <= int(time.time()) - book.ts <= 90:
                raise ExchangeError("Order book is stale")
            print("PASS public order book")
            await market.get_symbol_rules(cfg.symbol)
            await market.get_fees(cfg.symbol)
            print("PASS public rules and fee schedule (not live execution verification)")
        except ExchangeError as error:
            print(f"FAIL public probes: {error}")
        if not settings.nobitex_private_key or not settings.nobitex_public_key:
            print("SKIP private read probes: read-only key pair not configured")
        else:
            try:
                private = NobitexClient(spec, http, settings)
                await private.profile()
                await private.get_balances()
                orders = await private.list_open_orders(cfg.symbol)
                print("PASS signed profile, balances, and open-order list")
                if orders:
                    await private.get_order(cfg.symbol, orders[0].id)
                    print("PASS status by server ID")
                    if orders[0].client_id:
                        await private.get_order(cfg.symbol, orders[0].client_id, by_client=True)
                        print("PASS status by open client ID (not terminal recovery)")
                else:
                    print("SKIP order status: no existing open order to inspect")
            except ExchangeError as error:
                print(f"FAIL private probes: {error}")
    for item in spec.unverified():
        print(f"UNVERIFIED {item}")
    print("LIVE BLOCKED. Read-only probes cannot certify placement, cancellation, or protection.")
    return 2


def main() -> int:
    try:
        return asyncio.run(verify())
    except ConfigError as error:
        print(error)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
