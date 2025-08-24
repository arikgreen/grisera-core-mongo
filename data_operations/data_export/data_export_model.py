from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from enum import Enum


class ExportFormat(str, Enum):
    """Format eksportu"""
    JSON = "json"
    CSV = "csv"
    XML = "xml"


class ExportStatus(str, Enum):
    """Status eksportu - kompatybilny z OperationStatus"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportScope(str, Enum):
    """Zakres eksportu danych"""
    ALL = "all"                    # Wszystkie dane
    EXPERIMENT = "experiment"      # Tylko określony eksperyment
    DATE_RANGE = "date_range"      # Określony zakres dat
    ENTITY_TYPE = "entity_type"    # Określony typ encji


class DataExportIn(BaseModel):
    """Model wejściowy dla eksportu danych"""
    dataset_id: str
    export_format: ExportFormat = ExportFormat.JSON
    export_scope: ExportScope = ExportScope.ALL
    description: Optional[str] = None

    # Filtry eksportu
    experiment_id: Optional[str] = None  # Dla scope=experiment
    entity_types: Optional[List[str]] = None  # Dla scope=entity_type, np. ["Activity", "Participant"]
    date_from: Optional[str] = None  # Dla scope=date_range (ISO format)
    date_to: Optional[str] = None    # Dla scope=date_range (ISO format)

    # Opcje eksportu
    include_metadata: bool = True
    include_relationships: bool = True
    max_records: Optional[int] = None  # Limit rekordów (dla testów)

    # Dodatkowe opcje
    additional_options: Optional[Dict[str, Any]] = None


class DataExportOut(BaseModel):
    """Model wyjściowy dla eksportu danych"""
    id: str  # MongoDB ObjectId jako string
    dataset_id: str
    export_format: ExportFormat
    export_scope: ExportScope
    status: ExportStatus
    description: Optional[str] = None

    # Liczniki
    exported_records: int = 0
    failed_records: int = 0
    error_count: int = 0

    # Timestampy
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Wyniki eksportu
    file_path: Optional[str] = None  # Ścieżka do wygenerowanego pliku
    file_size: Optional[int] = None  # Rozmiar pliku w bajtach
    download_url: Optional[str] = None  # URL do pobrania pliku

    # Błędy i komunikaty
    error_messages: List[str] = []

    # Dodatkowe dane
    export_filters: Optional[Dict[str, Any]] = None
    export_summary: Optional[Dict[str, Any]] = None  # Podsumowanie co zostało wyeksportowane


class ExportProgressOut(BaseModel):
    """Model dla śledzenia postępu eksportu"""
    id: str
    status: ExportStatus
    progress_percentage: Optional[float] = None  # 0-100
    current_stage: Optional[str] = None  # "fetching_data", "processing", "generating_file"
    estimated_time_remaining: Optional[int] = None  # w sekundach
    exported_records: int = 0
    total_records: Optional[int] = None
    error_count: int = 0
    last_updated: Optional[str] = None

