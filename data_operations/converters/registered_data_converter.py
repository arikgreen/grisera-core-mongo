from typing import Dict, Any, Optional
from uuid import uuid4

from grisera import RegisteredDataIn
from grisera.clients.minio_client import MinIOClient

from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from .base import BaseEntityConverter


class RegisteredDataConverter(BaseEntityConverter[RegisteredDataIn]):
    JSON_KEY_CANDIDATES_FOR_SOURCE = ["registeredDataSource", "source", "hasSource"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "RegisteredData"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self._current_dataset_id = None  # Store dataset_id for use in convert()

        # Initialize file services for file operations
        self.file_service = self.services.get_file_service()
        self.files_minio_client = MinIOClient("files")  # For reading from files bucket
        self.recordings_minio_client = MinIOClient("recordings")  # For storing copies in recordings bucket

    def _extract_source_filename(self, source: str) -> str:
        """
        Extract filename from full URL or path
        """
        if not source:
            return None
        return source.split('/')[-1]

    def _find_file_in_dataset(self, filename: str, dataset_id: str) -> Optional[str]:
        """
        Find file by filename and dataset_id using direct file service
        Searches by original_filename, name (display name), and filename fields
        Returns object_name (MinIO storage path) if found, None otherwise
        """
        try:
            files = self.file_service.get_files_by_dataset(dataset_id)

            for file_data in files:
                # Check original_filename first
                if file_data.original_filename and file_data.original_filename == filename:
                    print(f"✅ Found file '{filename}' by original_filename in dataset {dataset_id}: {file_data.filename}")
                    return file_data.filename  # This is the object_name in MinIO

                # Check custom name (display name) 
                if file_data.name and file_data.name == filename:
                    print(f"✅ Found file '{filename}' by display name in dataset {dataset_id}: {file_data.filename}")
                    return file_data.filename

                # Check filename (storage name) - extract just the filename part
                if file_data.filename and file_data.filename.split('/')[-1] == filename:
                    print(f"✅ Found file '{filename}' by storage filename in dataset {dataset_id}: {file_data.filename}")
                    return file_data.filename

            print(f"❌ File '{filename}' not found in dataset {dataset_id} (searched original_filename, name, and filename)")
            return None

        except Exception as e:
            print(f"❌ Error searching for file '{filename}' in dataset {dataset_id}: {e}")
            return None

    def _create_default_file(self, source: str, filename: str, dataset_id: str) -> str:
        """
        Create a default text file with original source content in recordings bucket
        Returns object_name if successful, original source if failed
        """
        try:
            # Create text content with original source
            text_content = f"Original registered data source: {source}\n"
            text_content += f"This is a placeholder file created during import because the original file was not found in the dataset.\n"

            # Generate object name for storage in recordings bucket
            new_uuid = str(uuid4())
            object_name = f"{new_uuid}/{filename}.txt"

            # Upload to recordings bucket
            self.recordings_minio_client.upload_file(object_name, text_content.encode('utf-8'), 'text/plain')

            print(f"✅ Created default file for '{filename}' in recordings bucket: {object_name}")
            return object_name

        except Exception as e:
            print(f"❌ Error creating default file for '{filename}': {e}")
            return source

    def _copy_existing_file(self, existing_object_name: str, filename: str, dataset_id: str) -> str:
        """
        Copy existing file from files bucket to recordings bucket with new UUID
        Uses original filename with proper extension, not the searched filename
        Returns new object_name if successful, existing_object_name if failed
        """
        try:
            # Get the file from files bucket
            file_response = self.files_minio_client.get_file(existing_object_name)
            file_content = file_response.read()

            # Find the file metadata to get content type and original filename
            files = self.file_service.get_files_by_dataset(dataset_id)
            original_file_data = None
            for file_data in files:
                if file_data.filename == existing_object_name:
                    original_file_data = file_data
                    break

            if not original_file_data:
                print(f"❌ Could not find metadata for file '{existing_object_name}'")
                return existing_object_name

            content_type = original_file_data.content_type or 'application/octet-stream'
            # Use the original filename with proper extension, not the searched filename
            actual_filename = original_file_data.original_filename or filename

            # Generate new object name for recordings bucket using actual filename
            new_uuid = str(uuid4())
            new_object_name = f"{new_uuid}/{actual_filename}"

            # Upload to recordings bucket with new UUID
            self.recordings_minio_client.upload_file(new_object_name, file_content, content_type)

            print(f"✅ Copied file '{actual_filename}' (searched as '{filename}') from files bucket to recordings bucket: {new_object_name}")
            print(f"   Content-Type: {content_type}, Size: {len(file_content)} bytes")
            return new_object_name

        except Exception as e:
            print(f"❌ Error copying file '{filename}': {e}")
            return existing_object_name

    def _process_source_file(self, source: str, dataset_id: str) -> str:
        """
        Process source file for registered data:
        - Extract filename from full path/URL
        - Try to find and copy file in the system
        - If not found, create a default text file with original source
        """
        if not source:
            return source

        filename = self._extract_source_filename(source)
        if not filename:
            return source

        print(f"🔍 Processing source file: '{filename}' from '{source}'")

        # Try to find existing file
        existing_object_name = self._find_file_in_dataset(filename, dataset_id)

        if existing_object_name:
            # File found - copy it to new location
            new_object_name = self._copy_existing_file(existing_object_name, filename, dataset_id)
            return new_object_name
        else:
            # File not found - create default placeholder
            default_object_name = self._create_default_file(source, filename, dataset_id)
            return default_object_name

    def convert(self, json_entity: Dict[str, Any]) -> RegisteredDataIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij source - opcjonalny
        source = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_SOURCE)
        clean_name_for_log = remove_prefix(external_id) if external_id else "unknown_registereddata_id"

        if source is None:
            print(f"ℹ️ Optional field 'source' not found for RegisteredData '{clean_name_for_log}'.")
        else:
            # Process source file if dataset_id is available
            if self._current_dataset_id:
                source = self._process_source_file(source, self._current_dataset_id)
            else:
                print(f"⚠️ dataset_id not available, cannot process source file for RegisteredData '{clean_name_for_log}'")

        registered_data = RegisteredDataIn(source=source)

        additional_properties = self._set_common_properties(json_entity, registered_data)

        if not any(prop.key in ["name", "description"] for prop in additional_properties if hasattr(prop, 'key')):
            from grisera import PropertyIn
            clean_id = remove_prefix(external_id) if external_id else "unknown"
            additional_properties.extend([
                PropertyIn(key="name", value=clean_id),  # Nazwa na podstawie ID
                PropertyIn(key="description", value=f"Auto-generated registered data for {clean_id}")
            ])

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_SOURCE)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        print(
            f"📝 Creating RegisteredDataIn: name='{clean_name_for_log}', source='{source}', external_id='{registered_data.external_id}', import_job_id='{registered_data.import_job_id}', properties={len(additional_properties)} (including common)")
        registered_data.additional_properties = additional_properties
        return registered_data

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> RegisteredDataIn:
        # Store dataset_id for use in convert()
        self._current_dataset_id = dataset_id
        return self.services.get_registered_data_service().save_registered_data(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.REGISTERED_DATA)
