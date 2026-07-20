class SupremeZoneError(Exception):
    """Base exception for the platform."""


class ConfigurationError(SupremeZoneError):
    pass


class StrategyError(SupremeZoneError):
    pass


class PluginError(SupremeZoneError):
    pass


class ServiceResolutionError(SupremeZoneError):
    pass


class DependencyInjectionError(SupremeZoneError):
    pass


class EventBusError(SupremeZoneError):
    pass
