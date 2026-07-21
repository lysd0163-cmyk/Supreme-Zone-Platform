from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .bootstrap import bootstrap
from .platform import SupremeZonePlatform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="supreme-zone-platform")
    parser.add_argument("--strategy", type=str, default=None, help="Path to the strategy file")
    parser.add_argument("--bars", type=int, default=None, help="Override candle count")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols override")
    parser.add_argument("--live", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Live loop interval seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = bootstrap()
    platform = result.platform
    if not isinstance(platform, SupremeZonePlatform):
        raise RuntimeError("Platform orchestrator is unavailable")

    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip()) if args.symbols else None
    strategy_path = Path(args.strategy) if args.strategy else None

    if args.live:
        platform.run_forever(interval_seconds=args.interval, strategy_path=strategy_path, bars=args.bars, symbols=symbols)
    else:
        platform.run_once(strategy_path=strategy_path, bars=args.bars, symbols=symbols)
    return 0
