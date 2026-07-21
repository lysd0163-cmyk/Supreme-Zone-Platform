from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SymbolManager:
    symbols: tuple[str, ...] = field(default_factory=tuple)

    def load(self, symbols: list[str] | tuple[str, ...] | None) -> None:
        self.symbols = tuple(sorted({str(symbol).upper() for symbol in (symbols or ()) if str(symbol).strip()}))

    def add(self, symbol: str) -> None:
        normalized = symbol.upper().strip()
        if not normalized:
            return
        self.symbols = tuple(sorted(set(self.symbols) | {normalized}))

    def contains(self, symbol: str) -> bool:
        return symbol.upper().strip() in self.symbols
