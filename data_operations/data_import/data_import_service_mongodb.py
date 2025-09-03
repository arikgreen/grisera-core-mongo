from typing import List, Optional
import threading

from data_operations.data_import.json_import_service import JsonImportService
from data_operations.data_import.owl_import_service import OwlImportService
from data_operations.file_operations_model import (
    FileOperationIn,
    FileOperationOut,
    OperationStatus
)
from data_operations.file_operations_model import OperationType
from data_operations.file_operations_service import FileOperationsStatusService
from mongo_service.service_mixins import GenericMongoServiceMixin


class DataImportServiceMongoDB(GenericMongoServiceMixin):
    """
    Serwis do obsługi importu danych ontologicznych
    """

    def __init__(self):
        super().__init__()
        self.file_ops_service = FileOperationsStatusService()
        self.json_import_service = JsonImportService()
        self.owl_import_service = OwlImportService()

    def _background_import_processor(self, import_data: FileOperationIn, import_id: str):
        """
        Processes the import data in a background thread.
        """
        try:
            print(f"🧵 Background task started for import ID: {import_id}")
            self._update_import_status(
                import_id,
                import_data.dataset_id,
                OperationStatus.PROCESSING,
                0,
                0
            )

            # Retrieve file content from MinIO if needed
            if not import_data.file_content:
                print(f"📁 Retrieving file content from MinIO for import ID: {import_id}")
                file_content = self.file_ops_service.get_file_content_from_minio(import_id, import_data.dataset_id)
                if file_content:
                    import_data.file_content = file_content
                    print(f"✅ File content retrieved from MinIO ({len(file_content)} bytes)")
                else:
                    raise ValueError("Could not retrieve file content from MinIO")

            imported_count = self._process_import_data(
                import_data,
                import_id
            )
            print(f"📊 Background task: Data processing completed. Imported {imported_count} records for import ID: {import_id}")

            error_count = self._get_error_count(import_id, import_data.dataset_id)
            print(f"⚠️ Background task: Found {error_count} errors during import ID: {import_id}")

            final_status = OperationStatus.COMPLETED
            print(f"📋 Background task: Updating final status to: {final_status} for import ID: {import_id}")
            self._update_import_status(
                import_id,
                import_data.dataset_id,
                final_status,
                imported_count,
                error_count
            )
            print(f"✅ Background task: Import completed for ID: {import_id}")

        except Exception as e:
            print(f"❌ Background task: Import failed with error for ID {import_id}: {str(e)}")
            self._update_import_status(
                import_id,
                import_data.dataset_id,
                OperationStatus.FAILED,
                0,  # Reset counts on critical failure
                0,  # Error count for this specific failure is captured in messages
                [f"Background processing error: {str(e)}"]
            )

    def start_import(self, import_data: FileOperationIn) -> FileOperationOut:
        """
        Rozpoczyna proces importu danych (asynchronicznie)
        Args:
            import_data: Dane do importu
        Returns:
            Status importu
        """
        print(
            f"🚀 Starting import for file: {import_data.file_name}, dataset: {import_data.dataset_id}")

        import_id = None
        try:
            print("📝 Creating import operation using FileOperationsStatusService...")
            import_id = self.create_import_operation(import_data)
            print(f"🚀 Launching background import process for ID: {import_id}...")
            thread = threading.Thread(
                target=self._background_import_processor,
                args=(import_data, import_id)
            )
            thread.daemon = True  # Ensure thread doesn't block program exit if main thread finishes
            thread.start()
            print(f"🧵 Background thread started for import ID: {import_id}")
            print(f"✅ Import initiated for ID: {import_id}. Returning PENDING status.")
            return self.file_ops_service.get_operation_status(import_id, import_data.dataset_id)

        except Exception as e:
            print(f"❌ Critical error during import initiation: {str(e)}")
            if import_id:  # Jeśli ID zostało utworzone, ale wątek nie ruszył
                print(f"🔄 Updating status to FAILED for import ID: {import_id} due to initiation error.")
                self.file_ops_service.fail_operation(
                    import_id,
                    import_data.dataset_id,
                    [f"Initiation error: {str(e)}"]
                )
            return self.file_ops_service.get_operation_status(import_id)

    def create_import_operation(self, import_data):
        # Create file operation with file_content - it will be uploaded to MinIO automatically
        file_operation = FileOperationIn(
            file_name=import_data.file_name,
            operation_type=OperationType.IMPORT,
            dataset_id=import_data.dataset_id,
            description=import_data.description,
            experiment_id=import_data.experiment_id,
            file_content=import_data.file_content,  # This will be uploaded to MinIO
            file_type=import_data.file_type,
            additional_data={
                "file_type": import_data.file_type
            }
        )
        import_id = self.file_ops_service.create_operation(file_operation)
        print(f"✅ Import operation created with UUID: {import_id}")
        return import_id

    def get_import_status(self, import_id: str, dataset_id: str) -> FileOperationOut:
        """
        Pobiera status importu używając FileOperation sStatusService
        """
        print(f"🔍 Getting import status for ID: {import_id}, dataset: {dataset_id}")
        return self.file_ops_service.get_operation_status(import_id, dataset_id)

    def get_imports_by_dataset_id(self, dataset_id: str, operation_type: Optional[OperationType] = None) -> List[FileOperationOut]:
        """
        Pobiera importy dla danego ID datasetu.

        Args:
            dataset_id: ID datasetu
            operation_type: Opcjonalny typ operacji (domyślnie IMPORT)
        """
        if operation_type is None:
            operation_type = OperationType.IMPORT

        print(f"🔍 Fetching {operation_type.value} operations for dataset ID: {dataset_id}")
        try:
            file_operations = self.file_ops_service.get_operations_by_dataset_id(dataset_id, operation_type)

            if not file_operations:
                print(f"ℹ️ No {operation_type.value} operations found for dataset ID: {dataset_id}")
                return []

            print(f"✅ Found {len(file_operations)} {operation_type.value} operations for dataset ID: {dataset_id}")
            return file_operations

        except Exception as e:
            print(f"❌ Error fetching {operation_type.value} operations for dataset {dataset_id}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []

    def _process_import_data(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Przetwarza i importuje dane do MongoDB
        Returns: liczba zaimportowanych rekordów
        """
        print(f"⚙️ Processing import data for type: {import_data.file_type} (Import ID: {import_id})")
        if import_data.file_type.lower() == "json":
            print(f"📄 Processing JSON data for import ID: {import_id}...")
            return self.json_import_service.import_json_data(import_data, import_id)
        elif import_data.file_type.lower() == "owl":
            return self.owl_import_service.import_owl_data(import_data, import_id)
        else:
            error_msg = f"Unsupported import type: {import_data.file_type}"
            print(f"❌ {error_msg} (Import ID: {import_id})")
            raise ValueError(error_msg)

    def _get_error_count(self, import_id: str, dataset_id: str) -> int:
        """
        Pobiera liczbę błędów dla danego importu używając FileOperationsStatusService
        """
        return self.file_ops_service.get_error_count(import_id, dataset_id)

    def _update_import_status(
            self,
            import_id: str,
            dataset_id: str,
            status: OperationStatus,
            imported_records: int,
            error_count: int,
            error_messages: List[str] = None
    ):
        """
        Aktualizuje status importu używając FileOperationsStatusService
        """
        print(f"🔄 Updating import status for ID: {import_id}, dataset: {dataset_id}, status: {status.value}")
        try:
            # Mapuj OperationStatus na odpowiednie metody FileOperationsStatusService
            if status == OperationStatus.PROCESSING:
                success = self.file_ops_service.start_processing(import_id, dataset_id)
            elif status == OperationStatus.COMPLETED:
                success = self.file_ops_service.end_processing(
                    import_id,
                    dataset_id,
                    processed_records=imported_records,
                    error_count=error_count
                )
            elif status == OperationStatus.FAILED:
                success = self.file_ops_service.fail_operation(
                    import_id,
                    dataset_id,
                    error_messages=error_messages or []
                )
            else:
                print(f"⚠️ Unsupported status update: {status}")
                return

            if success:
                print("✅ Import status updated successfully")
            else:
                print("❌ Failed to update import status")

        except Exception as e:
            print(f"❌ Error updating import status: {str(e)}")
