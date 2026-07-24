from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

try:  # pragma: no cover - optional runtime dependency
    from docx import Document  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    Document = None  # type: ignore[assignment]

DEFAULT_HIERARCHY: tuple[str, ...] = ("D1", "H4", "H1", "M15")
CORE_TERM_ALIASES: tuple[tuple[str, str], ...] = (
    ("ORIGIN", "Origin"),
    ("DISPLACEMENT", "Displacement"),
    ("ORDER BLOCK", "Order Block"),
    ("OB", "Order Block"),
    ("FAIR VALUE GAP", "Fair Value Gap"),
    ("FVG", "Fair Value Gap"),
    ("PREMIUM", "Premium"),
    ("DISCOUNT", "Discount"),
    ("BOS", "BOS"),
    ("CHOCH", "CHoCH"),
    ("ICT", "ICT"),
    ("POL", "POL"),
    ("MML", "MML"),
    ("WYCKOFF", "Wyckoff"),
    ("MOMENTUM", "Momentum"),
    ("LIQUIDITY", "Liquidity"),
    ("REPRICING", "Repricing"),
    ("AMIR", "AMIR"),
)


@dataclass(slots=True, frozen=True)
class StrategySection:
    heading: str
    kind: str
    lines: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class StrategyInterpretation:
    title: str
    version: str
    versions_found: tuple[str, ...]
    source_format: str
    source_path: str
    summary: str
    sections: tuple[StrategySection, ...]
    core_terms: tuple[str, ...]
    protocols: tuple[str, ...]
    laws: tuple[str, ...]
    definitions: tuple[str, ...]
    timeframes: tuple[str, ...]
    official_outputs: tuple[str, ...]
    is_supreme_zone_engine: bool
    analysis: dict[str, Any] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)
    document: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyInterpreter:
    def interpret(
        self,
        path: str | Path,
        source_text: str | None = None,
        structured_payload: dict[str, Any] | None = None,
    ) -> StrategyInterpretation:
        strategy_path = Path(path)
        raw_text = source_text if source_text is not None else self._read_source_text(strategy_path)
        normalized = self._normalize_text(raw_text)
        structured_payload = structured_payload or {}

        title = self._extract_title(normalized, structured_payload, strategy_path)
        versions_found = self._extract_versions(normalized)
        version = self._select_version(versions_found)
        timeframes = self._extract_timeframes(normalized)
        sections = self._extract_sections(raw_text)
        core_terms = self._extract_core_terms(normalized)
        protocols = self._filter_sections(sections, ("PROTOCOL", "LAYER", "ENGINE", "FILTER"))
        laws = self._filter_sections(sections, ("LAW", "RULE", "CONFLICT", "OUTPUT"))
        definitions = self._filter_sections(sections, ("DEFINITION", "TERM", "GLOSSARY"))
        outputs = self._extract_official_outputs(normalized)
        analysis = self._analysis_payload(timeframes, structured_payload)
        rules = self._rules_payload(core_terms, outputs, timeframes)
        document = {
            "title": title,
            "version": version,
            "versions_found": list(versions_found),
            "source_format": strategy_path.suffix.lower().lstrip(".") or "txt",
            "source_path": str(strategy_path),
            "summary": self._summary(title, version, timeframes, core_terms, outputs),
            "sections_count": len(sections),
            "sections": [asdict(section) for section in sections],
            "core_terms": list(core_terms),
            "protocols": list(protocols),
            "laws": list(laws),
            "definitions": list(definitions),
            "timeframes": list(timeframes),
            "official_outputs": list(outputs),
            "analysis": analysis,
            "rules": rules,
            "is_supreme_zone_engine": self._is_supreme_zone_engine(title, core_terms, outputs, timeframes),
        }
        return StrategyInterpretation(
            title=title,
            version=version,
            versions_found=versions_found,
            source_format=document["source_format"],
            source_path=document["source_path"],
            summary=document["summary"],
            sections=sections,
            core_terms=core_terms,
            protocols=protocols,
            laws=laws,
            definitions=definitions,
            timeframes=timeframes,
            official_outputs=outputs,
            is_supreme_zone_engine=document["is_supreme_zone_engine"],
            analysis=analysis,
            rules=rules,
            document=document,
        )

    def _read_source_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        if suffix == ".docx":
            if Document is None:  # pragma: no cover - dependency guard
                raise RuntimeError("python-docx is required to read .docx strategy files")
            doc = Document(str(path))
            parts: list[str] = []
            for paragraph in doc.paragraphs:
                text = self._normalize_line(paragraph.text)
                if text:
                    parts.append(text)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text = self._normalize_line(cell.text)
                        if text:
                            parts.append(text)
            return "\n".join(parts)
        return path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return "\n".join(line.strip() for line in text.replace("\r", "\n").splitlines())

    @staticmethod
    def _normalize_line(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _extract_title(self, text: str, payload: dict[str, Any], path: Path) -> str:
        top = payload.get("name") or payload.get("title")
        if isinstance(top, str) and top.strip():
            return top.strip()
        match = re.search(r"SUPREME\s+ZONE\s+ENGINE", text, flags=re.IGNORECASE)
        if match:
            return "SUPREME ZONE ENGINE"
        return path.stem.replace("_", " ").strip() or "SUPREME ZONE ENGINE"

    def _extract_versions(self, text: str) -> tuple[str, ...]:
        versions: list[str] = []
        for found in re.findall(r"v\d+(?:\.\d+)?", text, flags=re.IGNORECASE):
            version = found.lower()
            if version not in versions:
                versions.append(version)
        return tuple(versions)

    def _select_version(self, versions: tuple[str, ...]) -> str:
        if not versions:
            return "v1.0"
        def sort_key(item: str) -> tuple[int, int]:
            match = re.search(r"v(\d+)(?:\.(\d+))?", item)
            return (int(match.group(1)) if match else 0, int(match.group(2) or 0) if match else 0)
        return sorted(versions, key=sort_key)[-1]

    def _extract_timeframes(self, text: str) -> tuple[str, ...]:
        aliases = [
            (r"\bD1\b|\b1D\b|\b1\s*D\b", "D1"),
            (r"\bH4\b|\b4H\b|\b4\s*H\b", "H4"),
            (r"\bH1\b|\b1H\b|\b1\s*H\b", "H1"),
            (r"\bM15\b|\b15M\b|\b15\s*M\b", "M15"),
        ]
        found: list[str] = []
        for pattern, label in aliases:
            if re.search(pattern, text, flags=re.IGNORECASE):
                found.append(label)
        ordered = [item for item in DEFAULT_HIERARCHY if item in found]
        for item in found:
            if item not in ordered:
                ordered.append(item)
        return tuple(ordered or DEFAULT_HIERARCHY)

    def _extract_sections(self, raw_text: str) -> tuple[StrategySection, ...]:
        sections: list[StrategySection] = []
        current_heading = "DOCUMENT"
        current_kind = "section"
        lines: list[str] = []
        for raw_line in self._normalize_text(raw_text).splitlines():
            line = self._normalize_line(raw_line)
            if not line:
                continue
            if self._looks_like_heading(line):
                if lines:
                    sections.append(StrategySection(current_heading, current_kind, tuple(lines)))
                current_heading = line
                current_kind = self._classify_heading(line)
                lines = []
            else:
                lines.append(line)
        if lines:
            sections.append(StrategySection(current_heading, current_kind, tuple(lines)))
        return tuple(sections)

    @staticmethod
    def _looks_like_heading(text: str) -> bool:
        stripped = text.strip()
        if not stripped or stripped.startswith("-"):
            return False
        if re.fullmatch(r"PART\s+\d+(?:\s*[—-]\s*.*)?", stripped, flags=re.IGNORECASE):
            return True
        keywords = ("LAYER", "ENGINE", "FILTER", "PROTOCOL", "OUTPUT", "SYSTEM", "STEP", "RULE", "LAW")
        return any(keyword in stripped.upper() for keyword in keywords)

    @staticmethod
    def _classify_heading(text: str) -> str:
        upper = text.upper()
        if "DEFINITION" in upper or "TERM" in upper:
            return "definition"
        if "PROTOCOL" in upper or "LAYER" in upper:
            return "protocol"
        if "LAW" in upper or "RULE" in upper:
            return "law"
        return "section"

    def _extract_core_terms(self, text: str) -> tuple[str, ...]:
        found: list[str] = []
        upper = text.upper()
        for alias, canonical in CORE_TERM_ALIASES:
            if alias in upper and canonical not in found:
                found.append(canonical)
        return tuple(found)

    @staticmethod
    def _filter_sections(sections: tuple[StrategySection, ...], markers: tuple[str, ...]) -> tuple[str, ...]:
        results: list[str] = []
        for section in sections:
            if any(marker in section.heading.upper() for marker in markers) and section.heading not in results:
                results.append(section.heading)
        return tuple(results)

    def _extract_official_outputs(self, text: str) -> tuple[str, ...]:
        upper = text.upper()
        outputs: list[str] = []
        buy_labels = ("OFFICIAL BUY ZONE", "BUY ZONE", "ZONE BUY")
        sell_labels = ("OFFICIAL SELL ZONE", "SELL ZONE", "ZONE SELL")
        if any(label in upper for label in buy_labels):
            outputs.append("BUY ZONE")
        if any(label in upper for label in sell_labels):
            outputs.append("SELL ZONE")
        return tuple(outputs)

    def _analysis_payload(self, timeframes: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any]:
        analysis = payload.get("analysis", {}) if isinstance(payload.get("analysis", {}), dict) else {}
        rules = payload.get("rules", {}) if isinstance(payload.get("rules", {}), dict) else {}
        return {
            "timeframes": list(analysis.get("timeframes") or rules.get("timeframes") or timeframes),
            "minimum_candles": int(analysis.get("minimum_candles", rules.get("minimum_candles", 500))),
            "lookback_bars": int(analysis.get("lookback_bars", rules.get("lookback_bars", 120))),
            "zone_width_ratio": float(analysis.get("zone_width_ratio", rules.get("zone_width_ratio", 0.35))),
            "prefer_recent": bool(analysis.get("prefer_recent", rules.get("prefer_recent", True))),
            "bias": str(analysis.get("bias", rules.get("bias", "neutral"))).lower(),
            "strict_mode": True,
            "source": "strategy-interpreter",
        }

    def _rules_payload(self, core_terms: tuple[str, ...], official_outputs: tuple[str, ...], timeframes: tuple[str, ...]) -> dict[str, Any]:
        return {
            "timeframe_hierarchy": list(timeframes or DEFAULT_HIERARCHY),
            "core_terms": list(core_terms),
            "official_outputs": list(official_outputs),
            "requires_single_buy_zone": True,
            "requires_single_sell_zone": True,
            "requires_binary_validation": True,
            "requires_geometric_intersection": True,
            "requires_mtf_alignment": True,
            "requires_freshness": True,
            "requires_unconsumed": True,
            "requires_deterministic_reproducibility": True,
        }

    def _summary(self, title: str, version: str, timeframes: tuple[str, ...], core_terms: tuple[str, ...], outputs: tuple[str, ...]) -> str:
        parts = [title, version]
        if timeframes:
            parts.append("MTF:" + ",".join(timeframes))
        if core_terms:
            parts.append(f"terms={len(core_terms)}")
        if outputs:
            parts.append("outputs=" + ",".join(outputs))
        return " | ".join(parts)

    def _is_supreme_zone_engine(self, title: str, core_terms: tuple[str, ...], outputs: tuple[str, ...], timeframes: tuple[str, ...]) -> bool:
        required = {"ORIGIN", "DISPLACEMENT", "ORDER BLOCK", "FVG", "PREMIUM", "DISCOUNT", "BOS", "CHOCH"}
        return bool(
            re.search(r"SUPREME\s+ZONE\s+ENGINE", title, flags=re.IGNORECASE)
            and len(required.intersection(set(core_terms))) >= 4
            and {"BUY ZONE", "SELL ZONE"}.issubset(set(outputs))
            and set(DEFAULT_HIERARCHY).intersection(set(timeframes))
        )
