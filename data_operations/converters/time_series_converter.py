import os
from typing import Dict, Any, List, Optional
from uuid import uuid4
import io

from typing import Dict, Any, List
from grisera import TimeSeriesIn
from grisera.clients.minio_client import MinIOClient
from grisera.file.file_service import FileService

from .base import BaseEntityConverter, DEBUG
from .measure_converter import MeasureConverter
from .observable_information_converter import ObservableInformationConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class TimeSeriesConverter(BaseEntityConverter[TimeSeriesIn]):
    JSON_KEY_CANDIDATES_MEASURE_ID = ["hasMeasure", "measure_id"]
    JSON_KEY_CANDIDATES_OBS_INFO_ID = ["hasObservableInformation", "observable_information_id"]
    JSON_KEY_CANDIDATES_SOURCE = ["timeSeriesSource", "hasSource", "source"]
    JSON_KEY_CANDIDATES_TYPE = ["hasType", "timeSeriesType", "type"]

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.measure_service = MeasureConverter(import_id)
        self.observable_information_service = ObservableInformationConverter(import_id)
        self.services = MongoServiceFactory()
        self._current_dataset_id = None  # Store dataset_id for use in convert()

        # Initialize file services for file operations
        self.file_service = self.services.get_file_service()
        self.files_minio_client = MinIOClient("files")      # For reading from files bucket
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
            text_content = f"Original time series source: {source}\n"
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
        Process source file for time series:
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

    def convert(self, json_entity: Dict[str, Any]) -> TimeSeriesIn:
        external_id = self._get_external_id(json_entity)
        # Użyj oryginalnego @id dla logowania (po usunięciu prefixu), jeśli istnieje
        raw_entity_id = json_entity.get("@id")
        clean_entity_id_for_log = remove_prefix(str(raw_entity_id)) if raw_entity_id else "unknown_timeseries_id"

        measure_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_MEASURE_ID)
        if measure_id is None:
            print(f"ℹ️ Optional field 'measure_id' not found for TimeSeries '{clean_entity_id_for_log}'.")

        observable_information_ids = self._get_observable_information_ids(json_entity)
        if observable_information_ids is None:
            print(f"ℹ️ Optional field 'observable_information_ids' not found for TimeSeries '{clean_entity_id_for_log}'.")

        source = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_SOURCE)
        if source is None:
            print(f"ℹ️ Optional field 'source' not found for TimeSeries '{clean_entity_id_for_log}'.")
        else:
            # Process source file if dataset_id is available
            if self._current_dataset_id:
                source = self._process_source_file(source, self._current_dataset_id)
            else:
                print(f"⚠️ dataset_id not available, cannot process source file for '{clean_entity_id_for_log}'")

        time_series_type = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_TYPE)
        if time_series_type is None:
            print(f"⚠️ Required field 'type' not found for TimeSeries '{clean_entity_id_for_log}'. Using fallback: 'Timestamp'")
            # Ustaw fallback na prawidłową wartość enum
            time_series_type = "Timestamp"

        time_series = TimeSeriesIn(
            measure_id=measure_id,
            observable_information_ids=observable_information_ids,
            observable_information_id=observable_information_ids[0] if observable_information_ids else None,
            source=source,
            type=time_series_type
        )

        additional_properties = self._set_common_properties(json_entity, time_series)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_MEASURE_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_OBS_INFO_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_SOURCE)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_TYPE)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        print(f"📝 Creating TimeSeriesIn for '{clean_entity_id_for_log}': measure_id='{measure_id}', obs_info_ids='{observable_information_ids}', type='{time_series_type}', source='{source}', external_id='{time_series.external_id}', import_job_id='{time_series.import_job_id}', properties={len(additional_properties)} (including common)")
        time_series.additional_properties = additional_properties
        return time_series


    def _get_observable_information_ids(self, json_entity: Dict[str, Any]) -> List[str]:
        """
        Pobiera ID-ki z co:hasObservableInformation (które jest listą obiektów).
        Zwraca listę ID-ków jako stringi.
        """
        observable_info_ids = []

        # Szukaj klucza co:hasObservableInformation
        for entity_key, entity_value in json_entity.items():
            if remove_prefix(entity_key) == "hasObservableInformation":
                # To powinna być lista obiektów
                if isinstance(entity_value, list):
                    for obs_info in entity_value:
                        if isinstance(obs_info, dict):
                            # Szukaj @id w obiekcie ObservableInformation
                            obs_id = obs_info.get("@id")
                            if obs_id and obs_id.strip():
                                observable_info_ids.append(obs_id)
                break

        return observable_info_ids

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> TimeSeriesIn:
        # Store dataset_id for use in convert()
        self._current_dataset_id = dataset_id
        return self._save_time_series_with_mapping(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.TIME_SERIES)

    def _save_time_series_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje TimeSeries z mapowaniem observable_information_id i measure_id na MongoDB IDs.
        """
        try:
            source_entity_ref = grisera_object.external_id
            print(f"🔍 TimeSeries source ID: {source_entity_ref}")

            # 1. Mapuj measure_id (opcjonalne)
            mapped_measure_id = None
            if grisera_object.measure_id:
                measure_source_id = str(grisera_object.measure_id)
                print(f"🔍 Looking for Measure with source ID: {measure_source_id}")
                measure_mongo_id = self.measure_service.find_by_source_id(measure_source_id, dataset_id)

                if measure_mongo_id:
                    mapped_measure_id = measure_mongo_id
                    print(f"🔗 Mapped measure_id: {grisera_object.measure_id} -> {mapped_measure_id}")
                else:
                    print(f"❌ Could not find Measure in MongoDB for source ID: {measure_source_id}")

            # 2. Mapuj observable_information_id (najważniejsze)
            mapped_observable_information_id = None
            mapped_observable_information_ids = []

            if grisera_object.observable_information_id:
                obs_info_source_id = str(grisera_object.observable_information_id)
                print(f"🔍 Looking for ObservableInformation with source ID: {obs_info_source_id}")

                # Znajdź ObservableInformation po external_id w embedded liście
                obs_info_mongo_id = self.observable_information_service.find_by_source_id(obs_info_source_id, dataset_id)

                if obs_info_mongo_id:
                    mapped_observable_information_id = obs_info_mongo_id
                    print(
                        f"🔗 Mapped observable_information_id: {grisera_object.observable_information_id} -> {mapped_observable_information_id}")
                else:
                    print(f"❌ Could not find ObservableInformation in MongoDB for source ID: {obs_info_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "OBSERVABLE_INFO_NOT_FOUND_FOR_TIME_SERIES",
                        f"ObservableInformation with source ID '{obs_info_source_id}' not found for TimeSeries",
                        source_entity_ref or "unknown"
                    )
                    # TimeSeries może istnieć bez ObservableInformation

            # 3. Mapuj observable_information_ids (lista)
            if grisera_object.observable_information_ids:
                for obs_id in grisera_object.observable_information_ids:
                    obs_source_id = str(obs_id)
                    obs_mongo_id = self.observable_information_service.find_by_source_id(obs_source_id, dataset_id)
                    if obs_mongo_id:
                        mapped_observable_information_ids.append(obs_mongo_id)
                        print(f"🔗 Mapped observable_information_ids: {obs_id} -> {obs_mongo_id}")

            # 4. Utwórz nowy TimeSeriesIn z zmapowanymi ID
            from grisera import TimeSeriesIn
            mapped_time_series = TimeSeriesIn(
                measure_id=mapped_measure_id,
                observable_information_id=mapped_observable_information_id,
                observable_information_ids=mapped_observable_information_ids if mapped_observable_information_ids else None,
                type=grisera_object.type,
                source=grisera_object.source,
                signal_values=grisera_object.signal_values,
                external_id=source_entity_ref,
                import_job_id=import_id,
                additional_properties=grisera_object.additional_properties
            )

            # 5. Zapisz przez TimeSeriesService
            print(f"✅ TimeSeries being saved with mapped data: {mapped_time_series.__dict__}")
            result = self.services.get_time_series_service().save_time_series(mapped_time_series, dataset_id)

            # Sprawdź czy nie ma błędów
            if hasattr(result, 'errors') and result.errors:
                print(f"❌ Error saving TimeSeries: {result.errors}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "TIME_SERIES_SAVE_ERROR",
                    f"Error saving TimeSeries: {result.errors}",
                    source_entity_ref or "unknown"
                )
                return None

            saved_time_series_id = str(getattr(result, 'id', 'unknown'))

            print(f"🔗 Final TimeSeries mappings:")
            print(f"   measure_id: {grisera_object.measure_id} -> {mapped_measure_id}")
            print(
                f"   observable_information_id: {grisera_object.observable_information_id} -> {mapped_observable_information_id}")
            print(
                f"   observable_information_ids: {grisera_object.observable_information_ids} -> {mapped_observable_information_ids}")
            print(f"   TimeSeries saved with ID: {saved_time_series_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving TimeSeries with mapping: {e}")
            raise e
