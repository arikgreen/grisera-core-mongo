import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from data_operations.file_operations_service import FileOperationsStatusService
from data_operations.file_operations_model import FileOperationIn, FileOperationOut, OperationType, OperationStatus
from data_operations.data_export.data_export_model import ExportedFile, ExportFormat

from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.collection_mapping import Collections

# Import nowej architektury JSON-LD
from data_operations.data_export.jsonld_export import (
    JsonLdExportOrchestrator,
    get_export_service_factory
)

DEBUG = True


class DataExportService(GenericMongoServiceMixin):
    """
    Serwis do obsługi eksportu danych z systemu GRISERA
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = FileOperationOut
        self.file_ops_service = FileOperationsStatusService()

        # Inicjalizacja nowego systemu eksportu JSON
        self.export_factory = get_export_service_factory()
        self.jsonld_orchestrator = self.export_factory.create_orchestrator()

        print("🔧 DataExportService initialized:")
        print("   - FileOperationsStatusService for operation tracking")
        print("   - MongoDB service for data access")
        print("   - JSON export orchestrator ready")

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

    def get_exports_by_dataset_id(self, dataset_id: str, operation_type: Optional[OperationType] = None) -> List[FileOperationOut]:
        """
        Pobiera eksporty dla danego ID datasetu używając FileOperationsStatusService
        
        Args:
            dataset_id: ID datasetu
            operation_type: Opcjonalny typ operacji (domyślnie EXPORT)
            
        Returns:
            Lista eksportów (FileOperationOut)
        """
        if operation_type is None:
            operation_type = OperationType.EXPORT
            
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
            return []

    def _background_export_processor(self, export_data: FileOperationIn, export_id: str):
        """
        Implementacja procesora eksportu w tle - używa nowej architektury JSON
        
        Args:
            export_data: Dane konfiguracji eksportu (FileOperationIn)
            export_id: ID eksportu
        """
        try:
            print(f"🧵 Background export task started for export ID: {export_id}")

            self.file_ops_service.start_processing(export_id, export_data.dataset_id)

            print(f"🔄 Processing export for dataset {export_data.dataset_id}")
            print(f"   - File type: {export_data.file_type}")
            print(f"   - File name: {export_data.file_name}")

            if export_data.file_type.lower() in ['json']:
                result = self._process_json_export(export_data)
            else:
                # Fallback dla innych typów plików
                print(f"<UNK> Processing export for dataset {export_data.dataset_id} failed. Unknown file type: {export_data.file_type}")
                pass

            if result["success"]:
                exported_count = result.get("statistics", {}).get("total_entities", 0)
                error_count = len(result.get("errors", []))
                
                # Zapisz eksportowany plik do kolekcji EXPORT_FILES
                self._save_exported_file(export_id, export_data, result)

                print(f"📁 Export data saved to collection: {export_data.file_name}")

                self.file_ops_service.end_processing(
                    export_id,
                    export_data.dataset_id,
                    processed_records=exported_count,
                    error_count=error_count
                )

                print(f"✅ Export completed for ID: {export_id} (exported {exported_count} entities)")
            else:
                # Export się nie udał
                error_messages = result.get("errors", ["Unknown export error"])
                self.file_ops_service.fail_operation(
                    export_id,
                    export_data.dataset_id,
                    error_messages=error_messages
                )
                print(f"❌ Export failed for ID: {export_id}")

        except Exception as e:
            print(f"❌ Background export task failed for ID {export_id}: {str(e)}")
            self.file_ops_service.fail_operation(
                export_id,
                export_data.dataset_id,
                error_messages=[f"Background export error: {str(e)}"]
            )

    def _process_json_export(self, export_data: FileOperationIn) -> Dict[str, Any]:
        """
        Przetwarza eksport do formatu JSON używając nowej architektury.
        
        Args:
            export_data: Dane konfiguracji eksportu
            
        Returns:
            Wynik eksportu
        """
        print(f"🔄 Processing JSON export for dataset: {export_data.dataset_id}")

        try:
            result = self.jsonld_orchestrator.export_dataset_to_jsonld(export_data)



                # print(f"🔍 DEBUG: Full orchestrator result JSON:")
                # try:
                #     import json
                #     from datetime import datetime
                #
                #     # Custom JSON encoder dla datetime obiektów
                #     class DateTimeEncoder(json.JSONEncoder):
                #         def default(self, obj):
                #             if isinstance(obj, datetime):
                #                 return obj.isoformat()
                #             return super().default(obj)
                #
                #     # Konwertuj na JSON z wcięciami dla czytelności, używając custom encoder
                #     json_str = json.dumps(result, indent=2, cls=DateTimeEncoder)
                #     print(json_str)
                # except Exception as e:
                #     print(f"❌ Error serializing orchestrator result to JSON: {str(e)}")
                #     # Fallback - print jako dict
                #     print(result)

            if result["success"]:
                print(f"✅ JSON export successful:")
                print(f"   - Total entities: {result.get('statistics', {}).get('total_entities', 0)}")
                print(f"   - Entity sections: {len(result.get('statistics', {}).get('entity_sections', []))}")
            else:
                print(f"❌ JSON export failed: {result.get('errors', [])}")

            return result

        except Exception as e:
            print(f"❌ JSON export processing error: {str(e)}")
            return {
                "success": False,
                "errors": [f"JSON export error: {str(e)}"]
            }

    def _process_generic_export(self, export_data: FileOperationIn) -> Dict[str, Any]:
        """
        Fallback processor dla innych typów eksportu (CSV, JSON itp.)
        Na razie dummy implementacja.

        Args:
            export_data: Dane konfiguracji eksportu

        Returns:
            Wynik eksportu
        """
        print(f"🔄 Processing generic export (type: {export_data.file_type})")

        # TODO: Implement other export formats
        import time
        time.sleep(1)  # Symulacja pracy

        return {
            "success": True,
            "export_type": export_data.file_type,
            "message": f"Generic export for {export_data.file_type} completed (dummy)",
            "statistics": {"total_entities": 50},  # Dummy liczba
            "errors": [],
            "warnings": ["Generic export is not fully implemented yet"]
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Health check dla serwisu eksportu
        
        Returns:
            Status serwisu
        """
        try:
            # Sprawdź status JSON-LD orchestratora
            jsonld_health = self.jsonld_orchestrator.health_check()

            return {
                "status": "healthy",
                "service": "data_export",
                "message": "Export service is running",
                "file_operations_service": "available",
                "jsonld_orchestrator": jsonld_health["status"],
                "supported_export_formats": ["json", "csv", "json-ld"]  # Lista obsługiwanych formatów
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "data_export",
                "error": str(e)
            }

    def _save_exported_file(self, export_id: str, export_data: FileOperationIn, result: Dict[str, Any]) -> None:
        """
        Zapisuje eksportowany plik do kolekcji EXPORT_FILES.
        
        Args:
            export_id: ID operacji eksportu
            export_data: Dane konfiguracji eksportu
            result: Wynik eksportu z danymi
        """
        try:
            # Zapisuj tylko export_id + czysty JSON-LD
            exported_file_data = {
                "export_id": export_id,  # Do wyszukiwania
                "content": result.get("data", {})  # Czysty JSON-LD (jak w json1_20250531_231044.json)
            }
            
            # Zapisz do kolekcji EXPORT_FILES w bazie datasetu
            self.mongo_api_service.client[export_data.dataset_id][Collections.EXPORT_FILES.value].insert_one(exported_file_data)
            
            print(f"💾 Exported file saved to collection: {Collections.EXPORT_FILES.value}")
            
        except Exception as e:
            print(f"❌ Error saving exported file: {str(e)}")
            raise

    def _convert_datetime_to_iso(self, obj):
        """
        Rekurencyjnie konwertuje datetime obiekty na ISO stringi.
        
        Args:
            obj: Obiekt do konwersji (może być dict, list, lub primitive)
            
        Returns:
            Obiekt z przekonwertowanymi datetime
        """
        if isinstance(obj, dict):
            return {key: self._convert_datetime_to_iso(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetime_to_iso(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    def get_exported_file(self, export_id: str) -> Optional[Dict[str, Any]]:
        """
        Pobiera eksportowany plik z kolekcji EXPORT_FILES.
        
        Args:
            export_id: ID operacji eksportu
            
        Returns:
            Zawartość pliku (JSON-LD) lub None jeśli nie znaleziono
        """
        try:
            # Znajdź plik w kolekcji EXPORT_FILES w bazie datasetu
            # Musimy znaleźć dataset_id dla tego export_id
            # Na razie szukamy we wszystkich datasetach (można to zoptymalizować później)
            file_doc = None
            for dataset_name in self.mongo_api_service.client.list_database_names():
                if dataset_name not in ['admin', 'local', 'config']:  # Pomijamy systemowe bazy
                    try:
                        file_doc = self.mongo_api_service.client[dataset_name][Collections.EXPORT_FILES.value].find_one(
                            {"export_id": export_id}
                        )
                        if file_doc:
                            break
                    except Exception:
                        continue
            
            if not file_doc:
                print(f"⚠️ No exported file found for export ID: {export_id}")
                return None
            
            # Zwróć tylko content (JSON-LD) bez metadanych eksportu
            content = file_doc.get("content", {})
            
            # Konwertuj datetime obiekty na ISO stringi w content przed zwróceniem
            content = self._convert_datetime_to_iso(content)
            
            print(f"✅ Exported file content retrieved for ID: {export_id}")
            
            return content
            
        except Exception as e:
            print(f"❌ Error retrieving exported file: {str(e)}")
            return None

    def get_export_preview(self, dataset_id: str, export_format: str = "json") -> Dict[str, Any]:
        """
        Tworzy podgląd eksportu bez zapisywania do pliku.
        
        Args:
            dataset_id: ID datasetu
            export_format: Format eksportu (domyślnie json)
            
        Returns:
            Podgląd eksportu
        """
        print(f"👀 Creating export preview for dataset: {dataset_id}, format: {export_format}")

        try:
            if export_format.lower() in ['json', 'json-ld', 'jsonld', 'json_ld']:
                return self.jsonld_orchestrator.get_export_preview(dataset_id)
            else:
                return {
                    "success": False,
                    "error": f"Preview not supported for format: {export_format}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Preview generation error: {str(e)}"
            }
