from __future__ import annotations

from ...core.exceptions import SupremeZoneError


class DataEngineError(SupremeZoneError):
    pass


class DataConnectionError(DataEngineError):
    pass


class DataSyncError(DataEngineError):
    pass
