import threading
from typing import List, Dict, Any
from datetime import datetime

from data_operations.file_operations_service import FileOperationsStatusService
from data_operations.file_operations_model import FileOperationIn, FileOperationOut, OperationType, OperationStatus

from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin


class DataExportService(GenericMongoServiceMixin):
    """
    Serwis do obsługi eksportu danych z systemu GRISERA
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = FileOperationOut
        self.file_ops_service = FileOperationsStatusService()

        print("🔧 DataExportService initialized:")
        print("   - FileOperationsStatusService for operation tracking")
        print("   - MongoDB service for data access")

    def start_export(self, export_data: FileOperationIn) -> FileOperationOut:
        """
        Rozpoczyna proces eksportu danych (asynchronicznie)
        
        Args:
            export_data: Dane konfiguracji eksportu (FileOperationIn)
            
        Returns:
            Status eksportu (FileOperationOut)
        """
        print(f"🚀 Starting export for dataset: {export_data.dataset_id}, file_type: {export_data.file_type}")

        export_id = None
        try:
            print("📝 Creating export operation using FileOperationsStatusService...")
            
            # Utwórz operację przez FileOperationsStatusService
            export_id = self.file_ops_service.create_operation(export_data)
            print(f"✅ Export operation created with ID: {export_id}")

            print(f"🚀 Launching background export process for ID: {export_id}...")
            thread = threading.Thread(
                target=self._background_export_processor,
                args=(export_data, export_id)
            )
            thread.daemon = True
            thread.start()
            print(f"🧵 Background thread started for export ID: {export_id}")

            # Pobierz utworzoną operację i zwróć
            result = self.file_ops_service.get_operation_status(export_id, export_data.dataset_id)
            print(f"✅ Export initiated for ID: {export_id}. Returning PENDING status.")
            return result

        except Exception as e:
            print(f"❌ Critical error during export initiation: {str(e)}")
            if export_id:
                print(f"🔄 Using fail_and_get_operation for export ID: {export_id} due to initiation error.")
                result = self.file_ops_service.fail_and_get_operation(
                    export_id,
                    export_data.dataset_id,
                    f"Export initiation error: {str(e)}"
                )
                return result

            # Jeśli nie mamy export_id, zwróć dummy failed operation
            print("💥 Returning failed export result: unknown_initiation_failure")
            return FileOperationOut(
                id="unknown_initiation_failure",
                file_name=export_data.file_name or "unknown",
                operation_type=OperationType.EXPORT,
                dataset_id=export_data.dataset_id,
                status=OperationStatus.FAILED,
                error_messages=[f"Export initiation error: {str(e)}"]
            )

    def get_export_status(self, export_id: str, dataset_id: str) -> FileOperationOut:
        """
        Pobiera status eksportu używając FileOperationsStatusService
        
        Args:
            export_id: ID eksportu
            dataset_id: ID datasetu
            
        Returns:
            Status eksportu (FileOperationOut)
        """
        print(f"🔍 Getting export status for ID: {export_id}, dataset: {dataset_id}")
        return self.file_ops_service.get_operation_status(export_id, dataset_id)

    def get_exports_by_dataset_id(self, dataset_id: str) -> List[FileOperationOut]:
        """
        Pobiera wszystkie eksporty dla danego ID datasetu używając FileOperationsStatusService
        
        Args:
            dataset_id: ID datasetu
            
        Returns:
            Lista eksportów (FileOperationOut)
        """
        print(f"🔍 Fetching all exports for dataset ID: {dataset_id}")
        try:
            file_operations = self.file_ops_service.get_operations_by_dataset_id(dataset_id)

            if not file_operations:
                print(f"ℹ️ No export operations found for dataset ID: {dataset_id}")
                return []

            # Filtruj tylko operacje eksportu
            exports_list = [
                file_op for file_op in file_operations 
                if file_op.operation_type == OperationType.EXPORT
            ]
                    
            print(f"✅ Found {len(exports_list)} export operations for dataset ID: {dataset_id}")
            return exports_list

        except Exception as e:
            print(f"❌ Error fetching exports for dataset {dataset_id}: {str(e)}")
            return []

    def _background_export_processor(self, export_data: FileOperationIn, export_id: str):
        """
        Dummy implementacja procesora eksportu w tle - na razie nic nie robi
        
        Args:
            export_data: Dane konfiguracji eksportu (FileOperationIn)
            export_id: ID eksportu
        """
        try:
            print(f"🧵 Background export task started for export ID: {export_id}")
            
            # Ustaw status na PROCESSING
            self.file_ops_service.start_processing(export_id, export_data.dataset_id)

            # DUMMY IMPLEMENTATION - na razie nie robimy nic
            print(f"🔄 DUMMY: Processing export for dataset {export_data.dataset_id}")
            print(f"   - File type: {export_data.file_type}")
            print(f"   - File name: {export_data.file_name}")
            
            # Symulacja długotrwałego procesu
            import time
            time.sleep(2)  # Symulacja 2 sekund pracy
            
            # Na razie zwracamy sukces z dummy danymi
            dummy_exported_count = 100  # Symulacja 100 wyeksportowanych rekordów
            error_count = 0

            # Ustaw status na COMPLETED
            self.file_ops_service.end_processing(
                export_id,
                export_data.dataset_id,
                processed_records=dummy_exported_count,
                error_count=error_count
            )
            
            print(f"✅ DUMMY: Export completed for ID: {export_id} (exported {dummy_exported_count} records)")

        except Exception as e:
            print(f"❌ Background export task failed for ID {export_id}: {str(e)}")
            self.file_ops_service.fail_operation(
                export_id,
                export_data.dataset_id,
                error_messages=[f"Background export error: {str(e)}"]
            )

    def health_check(self) -> Dict[str, Any]:
        """
        Health check dla serwisu eksportu
        
        Returns:
            Status serwisu
        """
        try:
            return {
                "status": "healthy",
                "service": "data_export",
                "message": "Export service is running",
                "file_operations_service": "available"
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "service": "data_export",
                "error": str(e)
            }

