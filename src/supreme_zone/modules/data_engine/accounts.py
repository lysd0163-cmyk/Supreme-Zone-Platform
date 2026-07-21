from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import MT5Credentials


@dataclass(slots=True, frozen=True)
class MT5AccountProfile:
    label: str
    server: str
    login: int
    password: str

    def credentials(self) -> MT5Credentials:
        return MT5Credentials(server=self.server, login=self.login, password=self.password)


@dataclass(slots=True)
class MT5AccountManager:
    accounts: tuple[MT5AccountProfile, ...] = ()
    active_label: str | None = None

    def load(self, items: Iterable[MT5AccountProfile]) -> None:
        self.accounts = tuple(items)
        if self.active_label is None and self.accounts:
            self.active_label = self.accounts[0].label

    def active(self) -> MT5AccountProfile | None:
        if self.active_label is None:
            return self.accounts[0] if self.accounts else None
        for account in self.accounts:
            if account.label == self.active_label:
                return account
        return self.accounts[0] if self.accounts else None

    def set_active(self, label: str) -> None:
        self.active_label = label

    def labels(self) -> tuple[str, ...]:
        return tuple(account.label for account in self.accounts)
