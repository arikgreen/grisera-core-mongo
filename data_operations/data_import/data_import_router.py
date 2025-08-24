from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Optional, List
from data_operations.file_operations_model import (
    FileOperationIn,
    FileOperationOut,
    FileOperationError,
    OperationStatus
)
from data_operations.data_import.data_import_service_mongodb import DataImportServiceMongoDB

router = APIRouter(
    prefix="/api/v1/import",
    tags=["data-import"],
    responses={404: {"description": "Not found"}},
)


def get_import_service() -> DataImportServiceMongoDB:
    return DataImportServiceMongoDB()


@router.post("/upload", response_model=FileOperationOut)
async def upload_data(
        import_request: FileOperationIn,
        import_service: DataImportServiceMongoDB = Depends(get_import_service)
):
    """
    Endpoint do importu danych - odpowiednik @PostMapping w Spring
    
    Args:
        import_request: Dane do importu
        import_service: Serwis importu (dependency injection)
    
    Returns:
        Status importu
    """
    try:
        result = import_service.start_import(import_request)

        if result.status == "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Import failed: {result.error_messages}"
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/upload-file", response_model=FileOperationOut)
async def upload_file(
        file: UploadFile = File(...),
        dataset_id: str = Form(...),
        file_type: str = Form(...),
        description: Optional[str] = Form(None),
        experiment_id: Optional[str] = Form(None),
        import_service: DataImportServiceMongoDB = Depends(get_import_service)
):
    """
    Endpoint do uploadowania pliku - alternatywny sposób importu
    
    Podobny do @PostMapping z MultipartFile w Spring Boot
    """
    try:
        # Odczytaj zawartość pliku
        file_content = await file.read()
        file_content_str = file_content.decode('utf-8')

        # Stwórz request object
        import_request = FileOperationIn(
            file_name=file.filename,
            file_content=file_content_str,
            file_type=file_type,
            dataset_id=dataset_id,
            description=description,
            experiment_id=experiment_id
        )

        result = import_service.start_import(import_request)

        if result.status == "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Import failed: {result.error_messages}"
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status/{import_id}", response_model=FileOperationOut)
async def get_import_status(
        import_id: str,
        dataset_id: str,
        import_service: DataImportServiceMongoDB = Depends(get_import_service)
):
    """
    Endpoint do sprawdzenia statusu importu - odpowiednik @GetMapping w Spring
    
    Args:
        import_id: ID importu
        dataset_id: ID dataset'u
        import_service: Serwis importu
    
    Returns:
        Status importu
    """
    try:
        result = import_service.get_import_status(import_id, dataset_id)

        if result.status == "failed" and "not found" in str(result.error_messages):
            raise HTTPException(
                status_code=404,
                detail=f"Import with ID {import_id} not found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/dataset/{dataset_id}", response_model=List[FileOperationOut])
async def get_imports_by_dataset(
        dataset_id: str,
        import_service: DataImportServiceMongoDB = Depends(get_import_service)
):
    """
    Endpoint do pobierania wszystkich importów dla danego datasetu.

    Args:
        dataset_id: ID datasetu.
        import_service: Serwis importu (dependency injection).

    Returns:
        Lista importów.
    """
    try:
        imports = import_service.get_imports_by_dataset_id(dataset_id)
        if not imports:
            return []
        return imports
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching imports for dataset {dataset_id}: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Prosty health check endpoint
    """
    return {"status": "ok", "service": "data-import"}


data_import_router = router
