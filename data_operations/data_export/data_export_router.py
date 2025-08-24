from typing import List
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from data_operations.data_export.data_export_model import (
    ExportFormat
)

from data_operations.file_operations_model import (
    FileOperationIn,
    FileOperationOut,
    FileOperationError,
    OperationStatus
)
from data_operations.data_export.data_export_service import DataExportService

router = APIRouter(prefix="/export", tags=["Data Export"])

export_service = DataExportService()


@router.post("/start", response_model=FileOperationOut)
async def start_export(export_data: FileOperationIn):
    """
    Rozpoczyna eksport danych z datasetu
    
    Args:
        export_data: Konfiguracja eksportu
        
    Returns:
        Status rozpoczętego eksportu
        
    Raises:
        HTTPException: W przypadku błędu podczas inicjalizacji eksportu
    """
    try:
        print(f"🚀 API: Starting export for dataset: {export_data.dataset_id}")
        result = export_service.start_export(export_data)
        
        if result.status.value == "failed":
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to start export",
                    "export_id": result.id,
                    "errors": result.error_messages
                }
            )
        
        print(f"✅ API: Export started successfully with ID: {result.id}")
        return result
        
    except Exception as e:
        print(f"❌ API: Error starting export: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error during export start",
                "error": str(e)
            }
        )


@router.get("/status/{export_id}", response_model=FileOperationOut)
async def get_export_status(
    export_id: str = Path(..., description="ID eksportu"),
    dataset_id: str = Query(..., description="ID datasetu")
):
    """
    Pobiera status eksportu
    
    Args:
        export_id: ID eksportu
        dataset_id: ID datasetu
        
    Returns:
        Aktualny status eksportu
        
    Raises:
        HTTPException: W przypadku gdy eksport nie zostanie znaleziony
    """
    try:
        print(f"🔍 API: Getting export status for ID: {export_id}")
        result = export_service.get_export_status(export_id, dataset_id)
        
        if not result or result.id == "unknown_initiation_failure":
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Export not found",
                    "export_id": export_id,
                    "dataset_id": dataset_id
                }
            )
        
        print(f"✅ API: Export status retrieved: {result.status}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API: Error getting export status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while getting export status",
                "error": str(e)
            }
        )


@router.get("/list", response_model=List[FileOperationOut])
async def list_exports(
    dataset_id: str = Query(..., description="ID datasetu")
):
    """
    Pobiera listę wszystkich eksportów dla datasetu
    
    Args:
        dataset_id: ID datasetu
        
    Returns:
        Lista eksportów dla datasetu
    """
    try:
        print(f"📋 API: Getting exports list for dataset: {dataset_id}")
        exports = export_service.get_exports_by_dataset_id(dataset_id)
        
        print(f"✅ API: Found {len(exports)} exports for dataset: {dataset_id}")
        return exports
        
    except Exception as e:
        print(f"❌ API: Error getting exports list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while getting exports list",
                "error": str(e)
            }
        )


@router.get("/download/{export_id}")
async def download_export(
    export_id: str = Path(..., description="ID eksportu"),
    dataset_id: str = Query(..., description="ID datasetu")
):
    """
    Pobiera wyeksportowany plik (DUMMY IMPLEMENTATION)
    
    Args:
        export_id: ID eksportu
        dataset_id: ID datasetu
        
    Returns:
        Plik do pobrania lub informacja o błędzie
    """
    try:
        print(f"📥 API: Download request for export ID: {export_id}")
        
        # Sprawdź status eksportu
        export_status = export_service.get_export_status(export_id, dataset_id)
        
        if not export_status or export_status.id == "unknown_initiation_failure":
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Export not found",
                    "export_id": export_id
                }
            )
        
        if export_status.status.value != "completed":
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Export is not ready for download. Current status: {export_status.status.value}",
                    "export_id": export_id,
                    "status": export_status.status.value
                }
            )
        
        # DUMMY IMPLEMENTATION - zwróć JSON z informacją o eksporcie
        # Używamy tylko pól dostępnych w FileOperationOut
        dummy_export_data = {
            "export_id": export_id,
            "dataset_id": dataset_id,
            "file_type": export_status.file_type,
            "operation_type": export_status.operation_type.value,
            "status": export_status.status.value,
            "processed_records": export_status.processed_records,
            "created_at": export_status.created_at,
            "description": export_status.description,
            "file_info": {
                "file_name": export_status.file_name,
                "file_type": export_status.file_type
            },
            "dummy_data": {
                "message": "This is a dummy export response",
                "note": "Real implementation will return actual exported data",
                "sample_records": [
                    {"id": 1, "name": "Sample Export Record 1", "type": "dummy"},
                    {"id": 2, "name": "Sample Export Record 2", "type": "dummy"},
                    {"id": 3, "name": "Sample Export Record 3", "type": "dummy"}
                ]
            }
        }
        
        print(f"✅ API: Returning dummy export data for ID: {export_id}")
        return JSONResponse(content=dummy_export_data)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API: Error downloading export: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while downloading export",
                "error": str(e)
            }
        )


@router.get("/formats", response_model=List[str])
async def get_supported_formats():
    """
    Zwraca listę obsługiwanych formatów eksportu
    
    Returns:
        Lista dostępnych formatów eksportu
    """
    formats = [format.value for format in ExportFormat]
    print(f"📋 API: Returning supported export formats: {formats}")
    return formats


@router.get("/scopes", response_model=List[str])
async def get_supported_scopes():
    """
    Zwraca listę obsługiwanych zakresów eksportu
    
    Returns:
        Lista dostępnych zakresów eksportu
    """
    # scopes = [scope.value for scope in ExportScope]
    # print(f"📋 API: Returning supported export scopes: {scopes}")
    # return scopes
    return None


@router.get("/health")
async def export_health_check():
    """
    Health check endpointu eksportu
    
    Returns:
        Status serwisu eksportu
    """
    try:
        # Prosta kontrola - sprawdź czy serwis się inicjalizuje
        test_service = DataExportService()
        
        return {
            "status": "healthy",
            "service": "data_export",
            "message": "Export service is running",
            "timestamp": "2024-12-19T10:00:00Z"
        }
        
    except Exception as e:
        print(f"❌ API: Export health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "service": "data_export",
                "error": str(e)
            }
        )


# Eksport routera dla importu w main.py
data_export_router = router
