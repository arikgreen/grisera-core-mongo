from typing import List
from datetime import datetime
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


def _convert_datetime_to_iso(value):
    """Konwertuje datetime na ISO string lub zwraca string bez zmian"""
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value) if value else None


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
        
        # Automatycznie ustaw typ operacji na EXPORT
        from data_operations.file_operations_model import OperationType
        export_data.operation_type = OperationType.EXPORT
        
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
        
        # Użyj nowej metody z filtracją po typie EXPORT
        from data_operations.file_operations_model import OperationType
        exports = export_service.get_exports_by_dataset_id(dataset_id, OperationType.EXPORT)
        
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


@router.get("/files/{dataset_id}")
async def list_exported_files(
    dataset_id: str = Path(..., description="ID datasetu")
):
    """
    Pobiera listę wszystkich wyeksportowanych plików dla datasetu
    
    Args:
        dataset_id: ID datasetu
        
    Returns:
        Lista wyeksportowanych plików
    """
    try:
        print(f"📋 API: Getting exported files list for dataset: {dataset_id}")
        
        # Pobierz wszystkie pliki z kolekcji EXPORT_FILES dla danego datasetu
        from mongo_service.collection_mapping import Collections
        
        exported_files = export_service.mongo_api_service.find(
            collection_name=Collections.EXPORT_FILES.value,
            query_filter={"dataset_id": dataset_id}
        )
        
        files_list = []
        for file_doc in exported_files:
            # Pobierz status operacji eksportu
            export_status = export_service.get_export_status(file_doc["export_id"], dataset_id)
            
            file_info = {
                "file_id": file_doc["id"],
                "export_id": file_doc["export_id"],
                "file_name": file_doc["file_name"],
                "file_type": file_doc["file_type"],
                "content_type": file_doc["content_type"],
                "size": file_doc.get("size"),
                "total_entities": file_doc["total_entities"],
                "entity_types": file_doc["entity_types"],
                "export_format": file_doc["export_format"],
                "created_at": file_doc["created_at"],
                "description": file_doc.get("description"),
                "export_status": export_status.status.value if export_status else "unknown"
            }
            files_list.append(file_info)
        
        print(f"✅ API: Found {len(files_list)} exported files for dataset: {dataset_id}")
        return JSONResponse(content={
            "dataset_id": dataset_id,
            "total_files": len(files_list),
            "files": files_list
        })
        
    except Exception as e:
        print(f"❌ API: Error getting exported files list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while getting exported files list",
                "error": str(e)
            }
        )


@router.get("/download/{export_id}")
async def download_export(
    export_id: str = Path(..., description="ID eksportu"),
    dataset_id: str = Query(..., description="ID datasetu")
):
    """
    Pobiera wyeksportowany plik z kolekcji EXPORT_FILES
    
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
        
        # Pobierz eksportowany plik z kolekcji EXPORT_FILES
        exported_file_content = export_service.get_exported_file(export_id)
        
        if not exported_file_content:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Exported file not found in database",
                    "export_id": export_id
                }
            )
        
        # Zwróć tylko zawartość pliku (czysty JSON-LD)
        print(f"✅ API: Returning exported file content for ID: {export_id}")
        return JSONResponse(content=exported_file_content)
        
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


@router.delete("/file/{export_id}")
async def delete_exported_file(
    export_id: str = Path(..., description="ID eksportu"),
    dataset_id: str = Query(..., description="ID datasetu")
):
    """
    Usuwa wyeksportowany plik z kolekcji EXPORT_FILES
    
    Args:
        export_id: ID eksportu
        dataset_id: ID datasetu
        
    Returns:
        Status usunięcia pliku
    """
    try:
        print(f"🗑️ API: Delete request for exported file ID: {export_id}")
        
        # Sprawdź czy plik istnieje
        exported_file = export_service.get_exported_file(export_id)
        
        if not exported_file:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Exported file not found",
                    "export_id": export_id
                }
            )
        
        # Usuń plik z kolekcji EXPORT_FILES
        from mongo_service.collection_mapping import Collections
        
        delete_result = export_service.mongo_api_service.delete_one(
            collection_name=Collections.EXPORT_FILES.value,
            query_filter={"export_id": export_id}
        )
        
        if delete_result.deleted_count == 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Failed to delete exported file",
                    "export_id": export_id
                }
            )
        
        print(f"✅ API: Exported file deleted for ID: {export_id}")
        return JSONResponse(content={
            "message": "Exported file deleted successfully",
            "export_id": export_id,
            "deleted_count": delete_result.deleted_count
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API: Error deleting exported file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while deleting exported file",
                "error": str(e)
            }
        )


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
