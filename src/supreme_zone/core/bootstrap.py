from __future__ import annotations

from pathlib import Path

from .container import ServiceContainer
from .error_handler import ErrorHandler
from .events import EventBus
from .health import HealthMonitor
from .injector import DependencyInjector
from .logger import configure_logging
from .platform import SupremeZonePlatform
from .runtime import BootstrapResult
from .settings import Settings, SettingsManager
from ..modules.analysis_engine.service import AnalysisEngine
from ..modules.backtest_engine.service import BacktestEngine
from ..modules.dashboard.service import DashboardService
from ..modules.data_engine.accounts import MT5AccountManager
from ..modules.data_engine.cache import MarketCache
from ..modules.data_engine.database import MarketDatabase
from ..modules.data_engine.scheduler import UpdateScheduler
from ..modules.data_engine.service import DataEngine
from ..modules.entry_engine.service import EntryEngine
from ..modules.execution_engine.service import ExecutionEngine
from ..modules.monitoring_engine.service import MonitoringEngine
from ..modules.report_engine.service import ReportEngine
from ..modules.search_engine.service import SearchEngine
from ..modules.strategy_manager.service import StrategyManager
from ..modules.validation_engine.service import ValidationEngine


_REQUIRED_STORAGE_DIRS = (
    "storage/charts",
    "storage/ohlc",
    "storage/reports",
    "storage/logs",
    "storage/cache",
    "storage/database",
)


def bootstrap() -> BootstrapResult:
    settings_manager = SettingsManager()
    settings = settings_manager.load()
    logger = configure_logging(level=settings.log_level, log_dir=settings.storage.logs)

    logger.info("Bootstrapping %s", settings.app_name)
    for folder in _REQUIRED_STORAGE_DIRS:
        Path(folder).mkdir(parents=True, exist_ok=True)

    container = ServiceContainer()
    event_bus = EventBus()
    health_monitor = HealthMonitor()
    injector = DependencyInjector(container)
    error_handler = ErrorHandler(logger, error_log_path=settings.storage.logs / "errors.jsonl")
    error_handler.install_global_hook()

    cache = MarketCache(ttl_seconds=max(settings.market.live_poll_interval_seconds, 1))
    database = MarketDatabase(path=settings.storage.database / "market.sqlite3")
    scheduler = UpdateScheduler(interval_seconds=settings.market.live_poll_interval_seconds)
    account_manager = MT5AccountManager()
    strategy_manager = StrategyManager()
    data_engine = DataEngine(
        settings,
        cache=cache,
        database=database,
        account_manager=account_manager,
        scheduler=scheduler,
        error_handler=error_handler,
    )
    analysis_engine = AnalysisEngine(settings, data_engine=data_engine, strategy_manager=strategy_manager)
    validation_engine = ValidationEngine()
    search_engine = SearchEngine(analysis_engine=analysis_engine, validation_engine=validation_engine)
    entry_engine = EntryEngine()
    execution_engine = ExecutionEngine(data_engine=data_engine, default_volume=settings.execution.lot_size, magic=10101)
    monitoring_engine = MonitoringEngine(
        data_engine=data_engine,
        analysis_engine=analysis_engine,
        validation_engine=validation_engine,
        search_engine=search_engine,
        entry_engine=entry_engine,
        interval_seconds=settings.monitoring.refresh_interval_seconds,
    )
    report_engine = ReportEngine(output_dir=settings.storage.reports)
    backtest_engine = BacktestEngine(
        analysis_engine=analysis_engine,
        validation_engine=validation_engine,
        entry_engine=entry_engine,
        report_engine=report_engine,
    )
    dashboard_service = DashboardService(output_dir=settings.storage.reports / "dashboard")
    platform = SupremeZonePlatform(
        data_engine=data_engine,
        analysis_engine=analysis_engine,
        validation_engine=validation_engine,
        search_engine=search_engine,
        entry_engine=entry_engine,
        execution_engine=execution_engine,
        monitoring_engine=monitoring_engine,
        report_engine=report_engine,
        backtest_engine=backtest_engine,
        dashboard_service=dashboard_service,
    )

    container.register_instance(SettingsManager, settings_manager)
    container.register_instance(Settings, settings)
    container.register_instance(type(settings), settings)
    container.register_instance(type(logger), logger)
    container.register_instance(ServiceContainer, container)
    container.register_instance(EventBus, event_bus)
    container.register_instance(HealthMonitor, health_monitor)
    container.register_instance(DependencyInjector, injector)
    container.register_instance(ErrorHandler, error_handler)
    container.register_instance(MarketCache, cache)
    container.register_instance(MarketDatabase, database)
    container.register_instance(UpdateScheduler, scheduler)
    container.register_instance(MT5AccountManager, account_manager)
    container.register_instance(StrategyManager, strategy_manager)
    container.register_instance(DataEngine, data_engine)
    container.register_instance(AnalysisEngine, analysis_engine)
    container.register_instance(ValidationEngine, validation_engine)
    container.register_instance(SearchEngine, search_engine)
    container.register_instance(EntryEngine, entry_engine)
    container.register_instance(ExecutionEngine, execution_engine)
    container.register_instance(MonitoringEngine, monitoring_engine)
    container.register_instance(ReportEngine, report_engine)
    container.register_instance(BacktestEngine, backtest_engine)
    container.register_instance(DashboardService, dashboard_service)
    container.register_instance(SupremeZonePlatform, platform)

    event_bus.publish("system.bootstrap.started", {"app_name": settings.app_name})

    result = BootstrapResult(
        ready=True,
        app_name=settings.app_name,
        config_path=settings_manager.config_path,
        storage_root=Path("storage"),
        services_registered=(
            "SettingsManager",
            "Settings",
            "Logger",
            "ServiceContainer",
            "EventBus",
            "HealthMonitor",
            "DependencyInjector",
            "ErrorHandler",
            "MarketCache",
            "MarketDatabase",
            "UpdateScheduler",
            "MT5AccountManager",
            "StrategyManager",
            "DataEngine",
            "AnalysisEngine",
            "ValidationEngine",
            "SearchEngine",
            "EntryEngine",
            "ExecutionEngine",
            "MonitoringEngine",
            "ReportEngine",
            "BacktestEngine",
            "DashboardService",
            "SupremeZonePlatform",
        ),
        platform=platform,
    )

    event_bus.publish("system.bootstrap.ready", result)
    logger.info("Bootstrap complete: ready=%s", result.ready)
    return result
