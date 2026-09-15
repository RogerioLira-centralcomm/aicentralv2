"""Regras puras de saldo; persistência transacional entra no repositório."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CreditBalance:
    granted: int
    reserved: int
    captured: int
    released: int
    refunded: int
    adjusted: int

    @property
    def available(self) -> int:
        return max(0, self.granted + self.adjusted + self.refunded + self.released - self.reserved - self.captured)

    def can_reserve(self, cost: int) -> bool:
        return cost > 0 and self.available >= cost


def balance_from_ledger(rows) -> CreditBalance:
    totals = {key: 0 for key in ("monthly_grant", "reserve", "capture", "release", "refund", "adjustment")}
    for row in rows or ():
        kind = str(row.get("kind") or "")
        if kind in totals:
            totals[kind] += abs(int(row.get("amount") or 0))
    return CreditBalance(
        granted=totals["monthly_grant"], reserved=totals["reserve"], captured=totals["capture"],
        released=totals["release"], refunded=totals["refund"], adjusted=totals["adjustment"],
    )
