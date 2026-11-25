import argparse
import asyncio
import time

import httpx

from app.config import ROOT, ConfigError, load
from data.history import History
from data.store import Store
from exchange.base import ExchangeError
from exchange.nobitex import NobitexClient, Spec


async def download(max_pages: int) -> None:
    _, cfg, _, app = load()
    spec = Spec.load()
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        with Store(ROOT / app.data_directory / "candles.db") as store:
            history = History(
                store,
                NobitexClient(spec, http),
                cfg,
                spec.offset(cfg.timeframe),
                spec.raw["history_limit"],
            )
            count, pages, reason = await history.download(int(time.time()), max_pages)
            available = len(store.candles(cfg.symbol, cfg.timeframe))
            print(
                f"{cfg.symbol} {cfg.timeframe}: {count} fetched across {pages} windows; "
                f"{available} unique cached. Stop: {reason}."
            )
            if available < cfg.warmup + 300:
                print(
                    "History is too short for meaningful evaluation; collect more or supply candle CSV."
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Download closed public Nobitex BTC/USDT candles")
    parser.add_argument(
        "--max-pages", type=int, default=100, choices=range(1, 501), metavar="1..500"
    )
    args = parser.parse_args()
    try:
        asyncio.run(download(args.max_pages))
    except (ConfigError, ExchangeError) as error:
        print(error)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
