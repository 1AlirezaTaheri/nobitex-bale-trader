"""Local-only PAPER child used for deliberate process-termination/recovery drills."""

import argparse
import asyncio
import json
import sys
import time
from decimal import Decimal as D

from backtest.final_audit import confined
from data.store import Store
from exchange.base import Book, MarketData, Request, Rules, Side
from exchange.paper import PaperExchange
from execution import OrderManager

BTC = "BTC/USDT"


class LocalMarket(MarketData):
    """A fixed in-memory book; no HTTP client or credentials exist in this worker."""

    async def get_orderbook(self, symbol):
        return Book(int(time.time()), ((D(100), D(10)),), ((D("100.1"), D(10)),))

    async def get_symbol_rules(self, symbol):
        return Rules(D(".000001"), D(".01"), D(".5"))

    async def get_candles(self, *args):
        return []


async def scenario(root, phase, recover):
    root = confined(root)
    root.mkdir(parents=True, exist_ok=True)
    with Store(root / "state.db") as store:
        exchange = PaperExchange(LocalMarket(), store, D(100), D(".0025"), D(".0015"), D(100))
        manager = OrderManager(exchange, store, BTC, 60)
        if recover:
            started = time.perf_counter()
            await manager.reconcile()
            print(
                json.dumps(
                    {
                        "recovery_seconds": time.perf_counter() - started,
                        "orders": store.db.execute("SELECT count(*) FROM paper_orders").fetchone()[
                            0
                        ],
                        "active": len(manager.active()),
                        "quantity": str(manager.position().quantity),
                        "uncommitted_marker": store.get("mid_cycle_marker"),
                        "reconciled": True,
                    }
                ),
                flush=True,
            )
            return
        await manager.reconcile()
        if phase == "cycle":
            store.db.execute("BEGIN IMMEDIATE")
            store.write("mid_cycle_marker", True)
            print("READY", flush=True)
            sys.stdin.readline()
        elif phase == "order":

            def interrupted_apply(*args):
                print("READY", flush=True)
                sys.stdin.readline()
                raise RuntimeError("Parent should terminate child before apply")

            manager._apply = interrupted_apply
            await manager.submit(
                Request("final-audit-crash-order", Side.BUY, D(".1"), D(101), D(5)), "local drill"
            )
        elif phase == "suspend":
            before = time.monotonic()
            print("READY", flush=True)
            sys.stdin.readline()
            print(
                json.dumps({"resumed": True, "elapsed_seconds": time.monotonic() - before}),
                flush=True,
            )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--phase", choices=("cycle", "order", "suspend"), required=True)
    p.add_argument("--recover", action="store_true")
    args = p.parse_args()
    asyncio.run(scenario(args.root, args.phase, args.recover))


if __name__ == "__main__":
    main()
