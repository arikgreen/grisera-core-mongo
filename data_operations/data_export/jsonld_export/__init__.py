"""
JSON-LD Export Module - modularny system eksportu danych do formatu JSON-LD.

Architektura oparta na Single Responsibility Principle:
- BaseJsonLdHelper: Abstrakcyjna klasa bazowa dla helperów (pobieranie + mapowanie)
- Entity Helpers: Osobne klasy dla każdego typu encji z fetch_entities()
- JsonLdHelperRegistry: Centralne zarządzanie helperami
- DataFetchService: Deleguje pobieranie do helperów
- JsonLdStructureBuilder: Składanie finalnej struktury JSON-LD
- JsonLdExportOrchestrator: Koordynacja całego procesu
- ExportServiceFactory: Factory do tworzenia skonfigurowanych instancji
"""

# Import helpers from helpers folder (wszystkie dostępne)
from .helpers import (
    BaseJsonLdHelper,
    TimeSeriesJsonLdHelper,
    ParticipantJsonLdHelper,
    ParticipantStateJsonLdHelper,
    ObservableInformationJsonLdHelper,
    RecordingJsonLdHelper,
    MeasureJsonLdHelper,
    ActivityJsonLdHelper,
    ActivityExecutionJsonLdHelper,
    ParticipationJsonLdHelper,
    RegisteredChannelJsonLdHelper,
    RegisteredDataJsonLdHelper,
    ChannelJsonLdHelper,
    ModalityJsonLdHelper,
    LifeActivityJsonLdHelper,
    ArrangementJsonLdHelper,
    AppearanceJsonLdHelper,
    ExperimentJsonLdHelper,
)
from .mapper_registry import JsonLdHelperRegistry, get_helper_registry
from .data_fetch_service import DataFetchService
from .structure_builder import JsonLdStructureBuilder
from .export_orchestrator import JsonLdExportOrchestrator
from .service_factory import ExportServiceFactory, get_export_service_factory

__all__ = [
    # Base classes
    "BaseJsonLdHelper",
    
    # Entity helpers (wszystkie dostępne)
    "TimeSeriesJsonLdHelper",
    "ParticipantJsonLdHelper", 
    "ParticipantStateJsonLdHelper",
    "ObservableInformationJsonLdHelper",
    "RecordingJsonLdHelper",
    "MeasureJsonLdHelper",
    "ActivityJsonLdHelper",
    "ActivityExecutionJsonLdHelper",
    "ParticipationJsonLdHelper",
    "RegisteredChannelJsonLdHelper",
    "RegisteredDataJsonLdHelper",
    "ChannelJsonLdHelper",
    "ModalityJsonLdHelper",
    "LifeActivityJsonLdHelper",
    "ArrangementJsonLdHelper",
    "AppearanceJsonLdHelper",
    "ExperimentJsonLdHelper",
    
    # Core services
    "JsonLdHelperRegistry",
    "get_helper_registry",
    "DataFetchService",
    "JsonLdStructureBuilder",
    "JsonLdExportOrchestrator",
    
    # Factory
    "ExportServiceFactory",
    "get_export_service_factory",
]

# Version info
__version__ = "1.0.0"
__author__ = "GRISERA Team"
__description__ = "Modular JSON-LD export system for GRISERA data"
