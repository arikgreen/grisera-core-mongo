import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from grisera.clients.minio_client import MinIOClient

from data_operations.file_operations_model import (
    FileOperationIn,
    FileOperationOut,
    FileOperationError,
    OperationStatus,
    OperationType
)
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin


class FileOperationsStatusService(GenericMongoServiceMixin):
    """
    Serwis do zarządzania statusem operacji na plikach (import/eksport)
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = FileOperationOut
        self.file_operations_minio_client = MinIOClient("file-operations")

    def _upload_file_to_minio(self, file_content: str, operation_id: str, file_name: str, file_type: str) -> str:
        """
        Upload file content to MinIO and return the object path

        Args:
            file_content: File content to upload
            operation_id: Operation ID for unique naming
            file_name: Original file name
            file_type: File type/mime type

        Returns:
            MinIO object path
        """
        try:
            # Generate unique object name: operation_id/original_filename
            object_name = f"{operation_id}/{file_name}"

            # Convert string content to bytes
            file_data = file_content.encode('utf-8') if isinstance(file_content, str) else file_content

            # Determine content type
            content_type = file_type if file_type else "application/octet-stream"
            if file_name.lower().endswith('.json'):
                content_type = "application/json"
            elif file_name.lower().endswith('.owl') or file_name.lower().endswith('.xml'):
                content_type = "application/xml"

            # Upload to MinIO
            self.file_operations_minio_client.upload_file(object_name, file_data, content_type)
            print(f"✅ File uploaded to MinIO: {object_name} ({len(file_data)} bytes)")

            return object_name

        except Exception as e:
            print(f"❌ Error uploading file to MinIO: {str(e)}")
            raise e

    def get_file_content_from_minio(self, operation_id: str, dataset_id: str) -> Optional[str]:
        """
        Retrieve file content from MinIO for a given operation
        """
        try:
            operation = self.get_operation_status(operation_id, dataset_id)
            minio_object_path = operation.additional_data.get("minio_object_path")

            if not minio_object_path:
                return None

            file_response = self.file_operations_minio_client.get_file(minio_object_path)
            return file_response.read().decode('utf-8')

        except Exception as e:
            print(f"❌ Error retrieving file from MinIO: {str(e)}")
            return None

    def create_operation(self, operation_data: FileOperationIn) -> str:
        """
        Tworzy nową operację z statusem PENDING i zwraca ID
        
        Args:
            operation_data: Dane operacji do utworzenia
            
        Returns:
            ID utworzonej operacji (MongoDB ObjectId jako string)
        """
        print(f"🆕 Creating new file operation: {operation_data.operation_type.value} - {operation_data.file_name}")

        try:
            current_time = datetime.utcnow().isoformat()
            additional_data = operation_data.additional_data or {}

            # Upload file to MinIO
            if operation_data.file_content:
                # Create temporary ID for MinIO upload
                temp_id = str(uuid.uuid4())
                minio_object_path = self._upload_file_to_minio(
                    operation_data.file_content,
                    temp_id,
                    operation_data.file_name,
                    operation_data.file_type
                )
                additional_data["minio_object_path"] = minio_object_path
                additional_data["file_content_size"] = len(operation_data.file_content)

            operation_record_data = {
                "file_name": operation_data.file_name,
                "operation_type": operation_data.operation_type.value,
                "dataset_id": operation_data.dataset_id,
                "status": OperationStatus.PENDING.value,
                "description": operation_data.description,
                "experiment_id": operation_data.experiment_id,
                "processed_records": 0,
                "failed_records": 0,
                "error_count": 0,
                "created_at": current_time,
                "updated_at": current_time,
                "error_messages": [],
                "additional_data": additional_data
            }

            created_id = self.mongo_api_service.create_document_from_dict(
                operation_record_data,
                Collections.FILE_OPERATIONS.value,
                operation_data.dataset_id
            )

            print(f"✅ File operation created with ID: {created_id}")
            return created_id
        except Exception as e:
            print(f"❌ Error creating file operation: {str(e)}")
            raise e

    def start_processing(self, operation_uuid: str, dataset_id: str) -> bool:
        """
        Zmienia status operacji na PROCESSING
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            
        Returns:
            True jeśli aktualizacja się powiodła
        """
        print(f"🚀 Starting processing for operation: {operation_uuid}")

        return self._update_operation_status(
            operation_uuid=operation_uuid,
            dataset_id=dataset_id,
            status=OperationStatus.PROCESSING,
            additional_fields={
                "start_time": datetime.utcnow().isoformat()
            }
        )

    def end_processing(self, operation_uuid: str, dataset_id: str,
                       processed_records: int = 0, error_count: int = 0) -> bool:
        """
        Zmienia status operacji na COMPLETED
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            processed_records: Liczba przetworzonych rekordów
            error_count: Liczba błędów
            
        Returns:
            True jeśli aktualizacja się powiodła
        """
        print(f"✅ Ending processing for operation: {operation_uuid} - {processed_records} records processed, {error_count} errors")

        return self._update_operation_status(
            operation_uuid=operation_uuid,
            dataset_id=dataset_id,
            status=OperationStatus.COMPLETED,
            additional_fields={
                "processed_records": processed_records,
                "error_count": error_count,
                "failed_records": error_count,  # Zakładamy że error_count = failed_records
                "end_time": datetime.utcnow().isoformat()
            }
        )

    def fail_operation(self, operation_uuid: str, dataset_id: str,
                       error_messages: List[str] = None) -> bool:
        """
        Zmienia status operacji na FAILED
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            error_messages: Lista komunikatów błędów
            
        Returns:
            True jeśli aktualizacja się powiodła
        """
        error_messages = error_messages or []
        print(f"❌ Failing operation: {operation_uuid} - {len(error_messages)} error messages")

        return self._update_operation_status(
            operation_uuid=operation_uuid,
            dataset_id=dataset_id,
            status=OperationStatus.FAILED,
            additional_fields={
                "error_messages": error_messages,
                "end_time": datetime.utcnow().isoformat()
            }
        )

    def get_operation_status(self, operation_uuid: str, dataset_id: str) -> FileOperationOut:
        """
        Pobiera status operacji
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            
        Returns:
            Obiekt FileOperationOut z danymi operacji
        """
        print(f"🔍 Getting status for operation: {operation_uuid}")

        try:
            # Szukaj bezpośrednio po MongoDB _id (ObjectId jako string)
            operation_doc = self.mongo_api_service.get_document(
                operation_uuid,  # operation_uuid to teraz ObjectId jako string
                Collections.FILE_OPERATIONS.value,
                dataset_id
            )

            if not operation_doc:
                print(f"❌ Operation not found: {operation_uuid}")
                return FileOperationOut(
                    id=operation_uuid,
                    file_name="unknown",
                    operation_type="unknown",
                    dataset_id=dataset_id,
                    status=OperationStatus.FAILED,
                    error_messages=[f"Operation not found: {operation_uuid}"]
                )

            result = FileOperationOut(**operation_doc)
            print(f"✅ Operation status retrieved: {result.status}")
            return result

        except Exception as e:
            print(f"❌ Error getting operation status for {operation_uuid}: {str(e)}")
            return FileOperationOut(
                id=operation_uuid,
                file_name="unknown",
                operation_type="unknown",
                dataset_id=dataset_id,
                status=OperationStatus.FAILED,
                error_messages=[f"Error retrieving status: {str(e)}"]
            )

    def get_operations_by_dataset_id(self, dataset_id: str, operation_type: Optional[OperationType] = None) -> List[FileOperationOut]:
        """
        Pobiera operacje dla danego ID datasetu z opcjonalną filtracją po typie
        
        Args:
            dataset_id: ID datasetu
            operation_type: Opcjonalny typ operacji do filtrowania (import/export)

        Returns:
            Lista operacji
        """
        print(f"📋 Fetching operations for dataset: {dataset_id}" + (f" (type: {operation_type.value})" if operation_type else ""))
        try:
            query = {"dataset_id": dataset_id}
            if operation_type:
                query["operation_type"] = operation_type.value

            operation_docs = self.mongo_api_service.get_documents(
                collection_name=Collections.FILE_OPERATIONS.value,
                dataset_id=dataset_id,
                query=query
            )

            if not operation_docs:
                print(f"ℹ️ No operations found for dataset: {dataset_id}" + (f" with type: {operation_type.value}" if operation_type else ""))
                return []

            operations_list = [FileOperationOut(**doc) for doc in operation_docs]
            print(f"✅ Found {len(operations_list)} operations for dataset: {dataset_id}" + (f" with type: {operation_type.value}" if operation_type else ""))
            return operations_list

        except Exception as e:
            print(f"❌ Error fetching operations for dataset {dataset_id}: {str(e)}")
            return []

    def increment_progress_counter(self, operation_uuid: str, dataset_id: str, counter_name: str) -> bool:
        """
        Zwiększa licznik postępu dla określonego typu encji
        """
        try:
            existing_doc = self.mongo_api_service.get_document(
                operation_uuid,
                Collections.FILE_OPERATIONS.value,
                dataset_id
            )

            if not existing_doc:
                return False

            # Pobierz obecną wartość licznika lub ustaw na 0
            current_count = existing_doc.get("additional_data", {}).get(counter_name, 0)
            new_count = current_count + 1

            # Zaktualizuj licznik
            existing_doc["additional_data"][counter_name] = new_count
            existing_doc["updated_at"] = datetime.utcnow().isoformat()

            self.mongo_api_service.update_document_with_dict(
                collection_name=Collections.FILE_OPERATIONS.value,
                id=operation_uuid,
                new_document=existing_doc,
                dataset_id=dataset_id
            )

            return True

        except Exception as e:
            print(f"❌ Error incrementing progress counter: {str(e)}")
            return False

    def set_total_count(self, operation_uuid: str, dataset_id: str, counter_name: str, total_count: int) -> bool:
        """
        Ustawia total count dla określonego typu encji
        """
        try:
            existing_doc = self.mongo_api_service.get_document(
                operation_uuid,
                Collections.FILE_OPERATIONS.value,
                dataset_id
            )

            if not existing_doc:
                return False

            existing_doc["additional_data"][counter_name] = total_count
            existing_doc["updated_at"] = datetime.utcnow().isoformat()

            self.mongo_api_service.update_document_with_dict(
                collection_name=Collections.FILE_OPERATIONS.value,
                id=operation_uuid,
                new_document=existing_doc,
                dataset_id=dataset_id
            )

            return True

        except Exception as e:
            print(f"❌ Error setting total count: {str(e)}")
            return False

    def get_operations_by_dataset_id_and_type(self, dataset_id: str, operation_type: OperationType) -> List[FileOperationOut]:
        """
        Pobiera operacje dla danego ID datasetu i typu operacji

        Args:
            dataset_id: ID datasetu
            operation_type: Typ operacji do filtrowania (import/export)

        Returns:
            Lista operacji danego typu
        """
        return self.get_operations_by_dataset_id(dataset_id, operation_type)

    def log_error(self, operation_uuid: str, dataset_id: str, error_type: str,
                  error_message: str, entity_str: str = None, context: Dict[str, Any] = None) -> bool:
        """
        Loguje błąd operacji do bazy danych
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            error_type: Typ błędu
            error_message: Komunikat błędu
            entity_str: Encja której dotyczy błąd
            context: Dodatkowy kontekst błędu
            
        Returns:
            True jeśli logowanie się powiodło
        """
        print(f"📝 Logging error for operation {operation_uuid}: {error_type} - {error_message}")

        try:
            error_data = {
                "id": str(uuid.uuid4()),
                "operation_id": operation_uuid,
                "dataset_id": dataset_id,
                "error_type": error_type,
                "error_message": error_message,
                "entity_str": entity_str,
                "timestamp": datetime.utcnow().isoformat(),
                "context": context or {}
            }

            self.mongo_api_service.create_document_from_dict(
                error_data,
                Collections.FILE_OPERATION_ERRORS.value,
                dataset_id
            )

            print("✅ Error logged successfully")
            return True

        except Exception as e:
            print(f"❌ Error logging error: {str(e)}")
            return False

    def get_error_count(self, operation_uuid: str, dataset_id: str) -> int:
        """
        Pobiera liczbę błędów dla danej operacji
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            
        Returns:
            Liczba błędów
        """
        print(f"🔍 Getting error count for operation: {operation_uuid}")

        try:
            query_filter = {"operation_id": operation_uuid}
            error_documents = self.mongo_api_service.get_documents(
                collection_name=Collections.FILE_OPERATION_ERRORS.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            error_count = len(error_documents) if error_documents else 0
            print(f"📊 Found {error_count} errors for operation {operation_uuid}")
            return error_count

        except Exception as e:
            print(f"❌ Error getting error count: {e}")
            return 0

    def fail_and_get_operation(self, operation_id: str, dataset_id: str,
                               error_message: str) -> FileOperationOut:
        """
        Ustawia istniejącą operację na status FAILED i zwraca zaktualizowany obiekt
        
        Args:
            operation_id: ID operacji (MongoDB ObjectId jako string)
            dataset_id: ID datasetu
            error_message: Komunikat błędu
            
        Returns:
            Zaktualizowany obiekt FileOperationOut ze statusem FAILED
        """
        print(f"❌ Setting operation {operation_id} to FAILED status")

        # Ustaw status na FAILED
        success = self.fail_operation(
            operation_uuid=operation_id,
            dataset_id=dataset_id,
            error_messages=[error_message]
        )

        if success:
            print(f"✅ Operation {operation_id} successfully set to FAILED")
        else:
            print(f"⚠️ Warning: Failed to update operation {operation_id} status in database")

        # Pobierz i zwróć zaktualizowaną operację
        updated_operation = self.get_operation_status(operation_id, dataset_id)
        return updated_operation

    def _update_operation_status(self, operation_uuid: str, dataset_id: str,
                                 status: OperationStatus, additional_fields: Dict[str, Any] = None) -> bool:
        """
        Prywatna metoda do aktualizacji statusu operacji
        
        Args:
            operation_uuid: UUID operacji
            dataset_id: ID datasetu
            status: Nowy status
            additional_fields: Dodatkowe pola do aktualizacji
            
        Returns:
            True jeśli aktualizacja się powiodła
        """
        try:
            print(f"🔄 Updating operation {operation_uuid} status to: {status.value}")

            # Pobierz istniejący dokument bezpośrednio po ID
            existing_doc = self.mongo_api_service.get_document(
                operation_uuid,  # operation_uuid to ObjectId jako string
                Collections.FILE_OPERATIONS.value,
                dataset_id
            )

            if not existing_doc:
                print(f"❌ Cannot update status. Operation {operation_uuid} not found.")
                return False

            # Przygotuj pola do aktualizacji
            fields_to_update = {
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat()
            }

            if additional_fields:
                fields_to_update.update(additional_fields)

            # Scalaj z istniejącym dokumentem
            updated_document = {**existing_doc, **fields_to_update}

            # Zaktualizuj dokument
            self.mongo_api_service.update_document_with_dict(
                collection_name=Collections.FILE_OPERATIONS.value,
                id=operation_uuid,
                new_document=updated_document,
                dataset_id=dataset_id
            )

            print(f"✅ Operation status updated successfully to: {status.value}")
            return True

        except Exception as e:
            print(f"❌ Error updating operation status: {str(e)}")
            return False
