from dataclasses import replace
from decimal import Decimal

from execution import OrderManager
from risk import trail

D = Decimal


class Protection:
    """Software stop only. Never pretend this is an exchange-resident protective order."""

    exchange_resident = False

    def __init__(self, manager: OrderManager):
        self.manager = manager

    def hit(self, bid: D) -> bool:
        position = self.manager.position()
        return bool(position.quantity and bid <= position.stop)

    def tighten(self, high: D, distance: D) -> None:
        position = self.manager.position()
        if not position.quantity:
            return
        stop = trail(position.stop, high, distance)
        if stop != position.stop:
            with self.manager.store.db:
                self.manager.save_position(replace(position, stop=stop))
