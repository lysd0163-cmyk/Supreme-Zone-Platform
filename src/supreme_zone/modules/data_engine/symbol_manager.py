from __future__ import annotations

import re
from dataclasses import dataclass, field


_SYMBOL_PATTERN = re.compile(r"(?<![A-Z])([A-Z]{3})\s*/?\s*([A-Z]{3})(?![A-Z])")
_DELIMITER_PATTERN = re.compile(r"[\n,;،|]+")


@dataclass(slots=True)
class SymbolManager:
    symbols: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def _normalize_symbol(cls, symbol: str) -> str:
        text = str(symbol).upper().strip()
        compact = text.replace(" ", "").replace("/", "")
        if len(compact) == 6 and compact.isalpha():
            return f"{compact[:3]}/{compact[3:]}"
        return text

    @classmethod
    def _expand_symbols(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = _DELIMITER_PATTERN.split(str(value))

        normalized: list[str] = []
        for item in items:
            text = str(item).upper().strip()
            if not text:
                continue
            matches = [f"{base}/{quote}" for base, quote in _SYMBOL_PATTERN.findall(text)]
            if matches:
                for match in matches:
                    if match not in normalized:
                        normalized.append(match)
                continue

            symbol = cls._normalize_symbol(text)
            if symbol and symbol not in normalized:
                normalized.append(symbol)
        return tuple(normalized)

    def load(self, symbols: list[str] | tuple[str, ...] | None) -> None:
        self.symbols = self._expand_symbols(symbols)

    def add(self, symbol: str) -> None:
        expanded = self._expand_symbols([symbol])
        if not expanded:
            return
        self.symbols = tuple(sorted(set(self.symbols) | set(expanded)))

    def contains(self, symbol: str) -> bool:
        normalized = self._normalize_symbol(symbol)
        return normalized in self.symbols