from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class OperationType(str, Enum):
    """Typ operacji na pliku"""
    IMPORT = "import"
    EXPORT = "export"


class OperationStatus(str, Enum):
    """Status operacji"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileOperationIn(BaseModel):
    """Model wejściowy dla operacji na plikach"""
    file_name: str
    file_type: Optional[str]
    file_content: Optional[str]
    operation_type: Optional[OperationType]
    dataset_id: str
    description: Optional[str] = None
    experiment_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class FileOperationOut(BaseModel):
    """Model wyjściowy dla operacji na plikach"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_name: Optional[str]
    file_type: Optional[str]
    operation_type: OperationType
    dataset_id: str
    status: OperationStatus = OperationStatus.PENDING
    description: Optional[str] = None
    experiment_id: Optional[str] = None
    
    # Liczniki
    processed_records: int = 0
    failed_records: int = 0
    error_count: int = 0
    
    # Timestampy
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    # Błędy i komunikaty
    error_messages: List[str] = []
    
    # Dodatkowe dane specyficzne dla operacji
    additional_data: Optional[Dict[str, Any]] = None


class FileOperationError(BaseModel):
    """Model dla błędów operacji na plikach"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operation_id: str  # UUID operacji
    dataset_id: str
    error_type: str
    error_message: str
    entity_str: Optional[str] = None  # Encja której dotyczy błąd
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Dodatkowy kontekst błędu
    context: Optional[Dict[str, Any]] = None