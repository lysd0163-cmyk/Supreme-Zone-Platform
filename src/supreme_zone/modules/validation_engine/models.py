from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..analysis_engine.models import ZoneCandidate


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MITIGATED = "MITIGATED"
    CONSUMED = "CONSUMED"
    FRESH = "FRESH"


@dataclass(slots=True, frozen=True)
class ZoneValidationResult:
    candidate: ZoneCandidate
    status: ValidationStatus
    is_valid: bool
    touched: bool
    consumed: bool
    invalid_reason: str | None = None
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
