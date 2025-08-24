import uuid
from typing import Union, List, Dict, Any, Set
import json
from datetime import datetime
import threading

from data_import.utils import decode_file_content, remove_prefix
from data_import.converters import ENTITY_CONVERTERS, BaseEntityConverter
from data_import.entity_type_mapping import EntityTypeMapping
from data_import.file_operations_service import FileOperationsStatusService
from data_import.file_operations_model import FileOperationIn, OperationType

from data_import.file_operations_model import (
    FileOperationIn,
    FileOperationOut,
    FileOperationError,
    OperationStatus
)
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.collection_mapping import Collections

# Import GRISERA serwisów i modeli
from services.mongo_services import MongoServiceFactory
from grisera import (
    ActivityIn, ActivityService,
    ChannelIn, ChannelService,
    MeasureNameIn, MeasureNameService,
    ModalityIn, ModalityService,
    LifeActivityIn, LifeActivityService,
    ArrangementIn, ArrangementService,
    ParticipantIn, ParticipantService,
    TimeSeriesIn, TimeSeriesService,
    PropertyIn,
    ExperimentIn, ExperimentService,
    ActivityExecutionIn, ActivityExecutionService,
    ScenarioIn, ScenarioService,
    ParticipationIn, ParticipationService,
    RecordingIn, RecordingService,
    RegisteredDataIn,
    RegisteredChannelIn
)


class DataImportServiceMongoDB(GenericMongoServiceMixin):
    """
    Serwis do obsługi importu danych ontologicznych
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = FileOperationOut
        self.services = MongoServiceFactory()
        self.file_ops_service = FileOperationsStatusService()

        # self.property_mapper = OntologyPropertyMapper()

        # Globalny licznik dla nazw Scenario Execution
        self.scenario_execution_counter = 1

        print("🔧 DataImportServiceMongoDB initialized with refactored components:")
        print("   - Entity converters for GRISERA object creation")
        print("   - ScenarioBuilderService for scenario construction")
        print("   - Utils module for helper functions")

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

            imported_count = self._process_import_data(
                import_data,
                import_id
            )
            print(
                f"📊 Background task: Data processing completed. Imported {imported_count} records for import ID: {import_id}")

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
            f"🚀 Starting import for file: {import_data.file_name}, type: {import_data.import_type}, dataset: {import_data.dataset_id}")

        import_id = None
        try:
            print("📝 Creating import operation using FileOperationsStatusService...")

            # Przygotuj dane operacji do FileOperationsStatusService
            file_operation = FileOperationIn(
                file_name=import_data.file_name,
                operation_type=OperationType.IMPORT,
                dataset_id=import_data.dataset_id,
                description=import_data.description,
                experiment_id=import_data.experiment_id,
                additional_data={
                    "import_type": import_data.import_type,
                    "file_content": import_data.file_content if hasattr(import_data, 'file_content') else None
                }
            )

            import_id = self.file_ops_service.create_operation(file_operation)
            print(f"✅ Import operation created with UUID: {import_id}")

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

    def get_import_status(self, import_id: str, dataset_id: str) -> FileOperationOut:
        """
        Pobiera status importu używając FileOperation sStatusService
        """
        print(f"🔍 Getting import status for ID: {import_id}, dataset: {dataset_id}")
        return self.file_ops_service.get_operation_status(import_id, dataset_id)


    def get_imports_by_dataset_id(self, dataset_id: str) -> List[FileOperationOut]:
        """
        Pobiera wszystkie importy dla danego ID datasetu.
        """
        print(f"🔍 Fetching all imports for dataset ID: {dataset_id}")
        try:
            file_operations = self.file_ops_service.get_operations_by_dataset_id(dataset_id)

            if not file_operations:
                print(f"ℹ️ No import operations found for dataset ID: {dataset_id}")
                return []

            return file_operations

        except Exception as e:
            print(f"❌ Error fetching imports for dataset {dataset_id}: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []

    def _process_import_data(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Przetwarza i importuje dane do MongoDB
        Returns: liczba zaimportowanych rekordów
        """
        print(f"⚙️ Processing import data for type: {import_data.import_type} (Import ID: {import_id})")

        if import_data.import_type.lower() == "json":
            print(f"📄 Processing JSON data for import ID: {import_id}...")
            return self._import_json_data(import_data, import_id)
        else:
            error_msg = f"Unsupported import type: {import_data.import_type}"
            print(f"❌ {error_msg} (Import ID: {import_id})")
            # Ten błąd zostanie przechwycony przez _background_import_processor
            # i zaktualizuje status na FAILED.
            raise ValueError(error_msg)

    def _import_json_data(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Importuje dane JSON zgodnie z instrukcją ontologiczną
        Zrefaktoryzowane aby korzystać z nowych komponentów
        Returns: liczba zaimportowanych rekordów
        """
        print(f"📄 Starting JSON data import for import ID: {import_id}")
        processed_ids: Set[str] = set()
        nested_entities_queue: List[Dict[str, Any]] = []
        total_imported = 0

        try:
            print("🔓 Decoding file content using utils...")
            decoded_content = decode_file_content(import_data.file_content)
            print(f"📏 File content size: {len(decoded_content)} characters")

            print("🔍 Parsing JSON data...")
            json_data = json.loads(decoded_content)

            if not isinstance(json_data, dict):
                error_msg = "Expected JSON object at root level"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)

            print(f"📊 JSON contains {len(json_data.keys())} top-level entity types")
            print(f"🗂️ Entity types found: {list(json_data.keys())}")

            experiment_id = self._handle_experiment_creation(import_data, json_data, import_id)
            if experiment_id:
                print(f"🧪 Using experiment ID: {experiment_id}")
                if not import_data.experiment_id:
                    import_data.experiment_id = experiment_id

            entity_order = EntityTypeMapping.get_import_order()
            print(f"📋 Processing {len(entity_order)} entity types in dependency order...")

            for i, entity_type in enumerate(entity_order, 1):
                print(
                    f"🔄 [{i}/{len(entity_order)}] Looking for {entity_type.json_name} -> {entity_type.collection_name}")

                # Pomiń eksperyment jeśli został już zaimportowany wcześniej
                if entity_type.json_name == "Experiment" and experiment_id:
                    print(f"⏭️ Skipping Experiment processing - already imported with ID: {experiment_id}")
                    continue

                # Szukaj klucza w JSON, który po usunięciu prefiksu pasuje do entity_type.json_name
                matched_json_key = None
                for json_key in json_data.keys():
                    normalized_key = remove_prefix(json_key)
                    if normalized_key == entity_type.json_name:
                        matched_json_key = json_key
                        print(f"✅ Found match: {json_key} (normalized: {normalized_key})")
                        break

                if matched_json_key and matched_json_key in json_data:
                    entity_list = json_data[matched_json_key]
                    if not isinstance(entity_list, list):
                        print(f"❌ Expected list for {matched_json_key}, got {type(entity_list).__name__}")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "INVALID_ENTITY_LIST_TYPE",
                            f"Expected list for {matched_json_key}, got {type(entity_list).__name__}",
                            matched_json_key
                        )
                        continue

                    print(f"✅ Found {len(entity_list)} entities of type {entity_type.json_name}")
                    try:
                        imported_count = self._process_entity_list(
                            entity_list,
                            entity_type.collection_name,
                            import_data.dataset_id,
                            import_id,
                            processed_ids,
                            nested_entities_queue
                        )
                        total_imported += imported_count
                        print(
                            f"📈 Imported {imported_count} entities of type {entity_type.json_name}. Total: {total_imported}")

                    except Exception as e:
                        print(f"❌ Error processing {matched_json_key}: {str(e)}")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "ENTITY_LIST_PROCESSING_ERROR",
                            f"Error processing {matched_json_key}: {str(e)}",
                            matched_json_key
                        )
                else:
                    print(f"⚠️ No data found for entity type: {entity_type.json_name}")

            # Sprawdź czy są nieprzetworzone klucze JSON
            unprocessed_keys = []
            for json_key in json_data.keys():
                normalized_key = remove_prefix(json_key)
                entity_mapping = EntityTypeMapping.find_mapping_by_normalized_name(normalized_key)
                if not entity_mapping:
                    unprocessed_keys.append(json_key)

            if unprocessed_keys:
                print(f"⚠️ Found {len(unprocessed_keys)} unrecognized entity types: {unprocessed_keys}")
                self._log_import_error(
                    import_id,
                    import_data.dataset_id,
                    "UNRECOGNIZED_ENTITY_TYPES",
                    f"Found unrecognized entity types: {unprocessed_keys}",
                    entity_str=str(unprocessed_keys)
                )

            # Przetwarzanie kolejki zagnieżdżonych encji
            print(f"🔄 Processing {len(nested_entities_queue)} nested entities from queue...")
            processed_nested = 0
            while nested_entities_queue:
                entity_data = nested_entities_queue.pop(0)
                entity_id = entity_data.get("@id", "unknown_nested")

                if self._process_nested_entity(entity_data, import_data.dataset_id, import_id, processed_ids):
                    processed_nested += 1

            print(f"📊 Queue processing completed. Processed {processed_nested} nested entities")

            print(f"✅ JSON import completed! Total imported: {total_imported} entities")
            print(f"🧠 Processed unique IDs: {len(processed_ids)}")

            # Budowanie scenariuszy na podstawie eksperymentów i ActivityExecution
            print("🎬 Building scenarios based on experiments and ActivityExecution...")
            scenarios_count = self._build_experiment_scenarios(import_data, import_id)
            print(f"🎭 Created {scenarios_count} scenarios from experiments")

            return total_imported

        except Exception as e:
            print(f"💥 Critical error in JSON import: {str(e)}")
            self._log_import_error(
                import_id,
                import_data.dataset_id,
                "CRITICAL_JSON_ERROR",
                f"Critical error in JSON import: {str(e)}"
            )
            raise ValueError(f"Critical error in JSON import: {str(e)}")

    def _process_entity_list(
            self,
            entity_list: List[Dict[str, Any]],
            collection_name: str,
            dataset_id: str,
            import_id: str,
            processed_ids: Set[str],
            nested_entities_queue: List[Dict[str, Any]]
    ) -> int:
        """
        Przetwarza listę encji danego typu używając serwisów GRISERA i nowych konwerterów
        """
        print(f"📋 Processing entity list for collection: {collection_name}")

        if not isinstance(entity_list, list):
            error_msg = f"Expected list of entities, got {type(entity_list)}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)

        print(f"📊 Found {len(entity_list)} entities to process with GRISERA services")
        imported_count = 0

        entity_type = self._get_entity_type_from_collection(collection_name)
        print(f"🏷️ Determined entity type: {entity_type} for collection: {collection_name}")

        for i, entity in enumerate(entity_list):
            entity_id = entity.get("@id", f"unknown_{i}")
            print(f"🔄 [{i + 1}/{len(entity_list)}] Processing entity: {entity_id}")

            if entity_id in processed_ids:
                print(f"⚠️ Entity already processed: {entity_id}")
                continue

            try:
                grisera_object = self._convert_json_to_grisera_object(
                    entity,
                    entity_type,
                    dataset_id,
                    import_id
                )

                if grisera_object:
                    saved_id = self._save_with_grisera_service(grisera_object, entity_type, dataset_id, import_id)
                    if saved_id is not None:
                        processed_ids.add(entity_id)
                        imported_count += 1
                        print(f"✅ Entity saved with GRISERA service, ID: {saved_id}")
                    else:
                        print(f"⚠️ Entity skipped (incomplete dependencies): {entity_id}")
                        processed_ids.add(entity_id)  # Dodaj do processed_ids żeby nie próbować ponownie
                else:
                    print(f"⚠️ Could not convert entity to GRISERA object: {entity_id}")

            except Exception as e:
                print(f"❌ Error processing entity {entity_id}: {str(e)}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "SINGLE_ENTITY_ERROR",
                    f"Error processing single entity: {str(e)}",
                    entity_id
                )

        print(f"📈 Entity list processing completed. Imported: {imported_count}/{len(entity_list)}")
        return imported_count

    def _convert_json_to_grisera_object(
            self,
            json_entity: Dict[str, Any],
            entity_type: str,
            dataset_id: str,
            import_id: str
    ):
        try:
            print(f"🔄 Converting {entity_type} from JSON to GRISERA object using converters")

            converter_class = ENTITY_CONVERTERS.get(entity_type)

            if not converter_class:
                print(f"⚠️ No converter found for entity type: {entity_type}")
                return None

            converter = converter_class(import_id)

            # Wywołaj konwersję
            grisera_object = converter.convert(json_entity)

            print(f"✅ Successfully converted {entity_type} using {converter_class.__name__}")
            return grisera_object

        except Exception as e:
            print(f"❌ Error converting {entity_type} to GRISERA object: {e}")
            entity_id = json_entity.get("@id", "unknown")
            self._log_import_error(
                import_id,
                dataset_id,
                "GRISERA_CONVERSION_ERROR",
                f"Error converting {entity_type} to GRISERA object: {str(e)}",
                entity_id
            )
            return None

    def _save_with_grisera_service(self, grisera_object, entity_type: str, dataset_id: str, import_id: str) -> str:
        """
        Zapisuje obiekt GRISERA używając odpowiedniego serwisu
        """
        try:
            print(f"💾 Saving {entity_type} using GRISERA service")

            if entity_type == "Activity":
                print(f"✅ Activity being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_activity_service().save_activity(grisera_object, dataset_id)
            elif entity_type == "Channel":
                print(f"✅ Channel being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_channel_service().save_channel(grisera_object, dataset_id)
            elif entity_type == "MeasureName":
                print(f"✅ MeasureName being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_measure_name_service().save_measure_name(grisera_object, dataset_id)
            elif entity_type == "Measure":
                # Specjalna logika dla Measure - mapuj measure_name_id z source ID na MongoDB ID
                result = self._save_measure_with_mapping(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "Modality":
                print(f"✅ Modality being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_modality_service().save_modality(grisera_object, dataset_id)
            elif entity_type == "LifeActivity":
                print(f"✅ LifeActivity being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_life_activity_service().save_life_activity(grisera_object, dataset_id)
            elif entity_type == "Arrangement":
                print(f"✅ Arrangement being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_arrangement_service().save_arrangement(grisera_object, dataset_id)
            elif entity_type == "Participant":
                print(f"✅ Participant being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_participant_service().save_participant(grisera_object, dataset_id)
            elif entity_type == "ParticipantState":
                # Specjalna logika dla ParticipantState - mapuj participant_id z source ID na MongoDB ID
                result = self._save_participant_state_with_participant_mapping(grisera_object, dataset_id, import_id)
                if result is None:
                    print(f"⚠️ ParticipantState skipped - incomplete mapping")
                    return None
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "TimeSeries":
                result = self._save_time_series_with_mapping(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "Experiment":
                print(f"✅ Experiment being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_experiment_service().save_experiment(grisera_object, dataset_id)
            elif entity_type == "ActivityExecution":
                # Specjalna logika dla ActivityExecution
                result = self._save_activity_execution_with_scenario_linking(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "Participation":
                # Specjalna logika dla Participation - mapuj source IDs na MongoDB IDs
                result = self._save_participation_with_mapping(grisera_object, dataset_id, import_id)
                if result is None:
                    return None  # Zwróć None żeby _process_entity_list nie liczył tego jako błąd
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "Recording":
                result = self._save_recording_with_mapping(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "RegisteredData":
                print(f"✅ RegisteredData being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_registered_data_service().save_registered_data(grisera_object, dataset_id)
            elif entity_type == "RegisteredChannel":
                result = self._save_registered_channel_with_mapping(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            elif entity_type == "ObservableInformation":
                result = self._save_observable_information_with_mapping(grisera_object, dataset_id, import_id)
                saved_id = getattr(result, 'id', 'unknown')
                print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
                return str(saved_id)
            else:
                raise ValueError(f"No service mapping for entity type: {entity_type}")

            # Wyciągnij ID z wyniku
            saved_id = getattr(result, 'id', 'unknown')
            print(f"✅ {entity_type} saved successfully with ID: {saved_id}")
            return str(saved_id)

        except Exception as e:
            print(f"❌ Error saving {entity_type} with GRISERA service: {e}")
            raise e

    def _get_entity_type_from_collection(self, collection_name: str) -> str:
        """Określa typ encji na podstawie nazwy kolekcji"""
        collection_to_type = {
            Collections.ACTIVITY.value: "Activity",
            Collections.CHANNEL.value: "Channel",
            Collections.MEASURE_NAME.value: "MeasureName",
            Collections.MEASURE.value: "Measure",
            Collections.MODALITY.value: "Modality",
            Collections.LIFE_ACTIVITY.value: "LifeActivity",
            Collections.ARRANGEMENT.value: "Arrangement",
            Collections.PARTICIPANT.value: "Participant",
            Collections.PARTICIPANT_STATE.value: "ParticipantState",
            Collections.TIME_SERIES.value: "TimeSeries",
            Collections.EXPERIMENT.value: "Experiment",
            Collections.ACTIVITY_EXECUTION.value: "ActivityExecution",
            Collections.PARTICIPATION.value: "Participation",
            Collections.RECORDING.value: "Recording",
            Collections.REGISTERED_DATA.value: "RegisteredData",
            Collections.REGISTERED_CHANNEL.value: "RegisteredChannel",
            Collections.OBSERVABLE_INFORMATION.value: "ObservableInformation",
        }
        return collection_to_type.get(collection_name, "Unknown")

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

    def _log_import_error(
            self,
            import_id: str,
            dataset_id: str,
            error_type: str,
            error_message: str,
            entity_str: str = None
    ):
        """
        Loguje błąd importu do bazy danych używając FileOperationsStatusService
        """
        self.file_ops_service.log_error(
            operation_uuid=import_id,
            dataset_id=dataset_id,
            error_type=error_type,
            error_message=error_message,
            entity_str=entity_str
        )

    def _handle_experiment_creation(self, import_data: FileOperationIn, json_data: Dict[str, Any], import_id: str) -> str:
        """
        Sprawdza czy potrzeba utworzyć eksperyment automatycznie.

        Args:
            import_data: Dane importu
            json_data: Przesłane dane JSON
            import_id: ID procesu importu

        Returns:
            ID eksperymentu (istniejący lub nowo utworzony) lub None
        """
        print("🧪 Checking experiment creation requirements...")

        if import_data.experiment_id:
            print(f"✅ Using provided experiment ID: {import_data.experiment_id}")
            return import_data.experiment_id

        # 🔍 KROK 1: Sprawdź czy w JSON-ie jest eksperyment do zaimportowania
        print("🔍 Checking if JSON contains experiment data...")
        experiment_from_json = self._find_and_import_experiment_from_json(json_data, import_data.dataset_id, import_id)
        if experiment_from_json:
            print(f"✅ Found and imported experiment from JSON: {experiment_from_json}")
            return experiment_from_json

        # 🔍 KROK 2: Sprawdź jakie typy encji są w JSON (poza activity i participant)
        print("🔍 Analyzing JSON entity types for auto-creation...")
        normalized_keys = []
        for json_key in json_data.keys():
            normalized_key = remove_prefix(json_key)
            normalized_keys.append(normalized_key)
            print(f"📋 Found entity type: {json_key} (normalized: {normalized_key})")

        # Podstawowe typy które nie wymagają eksperymentu
        basic_types = EntityTypeMapping.get_basic_types()
        other_types = set(normalized_keys) - basic_types

        print(f"🧩 Basic types found: {basic_types & set(normalized_keys)}")
        print(f"🔬 Advanced types found: {other_types}")

        # Jeśli są tylko activity i participant, nie tworzymy eksperymentu
        if not other_types:
            print("ℹ️ Only basic entity types (Activity, Participant) found. No experiment needed.")
            return None

        # 🔍 KROK 3: Mamy złożone dane - tworzymy eksperyment automatycznie
        print(f"🧪 Advanced entity types detected: {other_types}. Creating experiment...")

        try:
            # Stwórz nazwę eksperymentu na podstawie nazwy pliku
            experiment_name = f"Auto-generated from {import_data.file_name}"
            if len(experiment_name) > 100:  # Ogranicznie długości
                experiment_name = experiment_name[:97] + "..."

            experiment_in = ExperimentIn(
                experiment_name=experiment_name,
                import_job_id=import_id,
                description=f"Auto-generated experiment for import job {import_id}",
                additional_properties=[]
                # additional_properties=[
                #     PropertyIn(key="auto_generated", value="true"),
                #     PropertyIn(key="source_file", value=import_data.file_name),
                #     PropertyIn(key="import_job_id", value=import_id),
                #     PropertyIn(key="entity_types", value=", ".join(sorted(other_types)))
                # ]
            )

            print(f"📝 Creating experiment with name: {experiment_name}")
            experiment_service = self.services.get_experiment_service()
            experiment_result = experiment_service.save_experiment(experiment_in, import_data.dataset_id)

            if hasattr(experiment_result, 'errors') and experiment_result.errors:
                print(f"❌ Error creating experiment: {experiment_result.errors}")
                self._log_import_error(
                    import_id,
                    import_data.dataset_id,
                    "EXPERIMENT_CREATION_ERROR",
                    f"Failed to create experiment: {experiment_result.errors}",
                    experiment_name
                )
                return None

            experiment_id = str(experiment_result.id)
            print(f"✅ Experiment created successfully with ID: {experiment_id}")

            return experiment_id

        except Exception as e:
            print(f"❌ Exception while creating experiment: {str(e)}")
            self._log_import_error(
                import_id,
                import_data.dataset_id,
                "EXPERIMENT_CREATION_EXCEPTION",
                f"Exception while creating experiment: {str(e)}",
                experiment_name if 'experiment_name' in locals() else "unknown"
            )
            return None

    def _find_and_import_experiment_from_json(self, json_data: Dict[str, Any], dataset_id: str, import_id: str) -> str:
        """
        Znajduje i importuje eksperyment z danych JSON jeśli istnieje.

        Args:
            json_data: Dane JSON do przeszukania
            dataset_id: ID datasetu
            import_id: ID procesu importu

        Returns:
            ID zaimportowanego eksperymentu lub None jeśli nie znaleziono
        """
        print("🔍 Searching for experiment data in JSON...")

        # Szukaj klucza eksperymentu w JSON (z uwzględnieniem prefiksów)
        experiment_key = None
        experiment_data = None

        for json_key in json_data.keys():
            normalized_key = remove_prefix(json_key)
            if normalized_key == "Experiment":
                experiment_key = json_key
                experiment_data = json_data[json_key]
                print(f"✅ Found experiment data under key: {json_key}")
                break

        if not experiment_data:
            print("ℹ️ No experiment data found in JSON")
            return None

        if not isinstance(experiment_data, list):
            print(f"❌ Expected list for experiments, got {type(experiment_data).__name__}")
            self._log_import_error(
                import_id,
                dataset_id,
                "INVALID_EXPERIMENT_DATA_TYPE",
                f"Expected list for experiments, got {type(experiment_data).__name__}",
                experiment_key
            )
            return None

        if len(experiment_data) == 0:
            print("ℹ️ Experiment list is empty")
            return None

        # Bierzemy pierwszy eksperyment z listy
        experiment_json = experiment_data[0]
        print(f"📋 Processing first experiment from list of {len(experiment_data)} experiments")

        try:
            # Konwertuj JSON na obiekt GRISERA używając konwertera
            converter_class = ENTITY_CONVERTERS.get("Experiment")

            if not converter_class:
                print("❌ No converter found for Experiment entity type")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "NO_EXPERIMENT_CONVERTER",
                    "No converter found for Experiment entity type",
                    str(experiment_json.get("@id", "unknown"))
                )
                return None

            converter = converter_class(import_id)
            experiment_grisera = converter.convert(experiment_json)

            if not experiment_grisera:
                print("❌ Failed to convert experiment JSON to GRISERA object")
                return None

            # Zapisz eksperyment używając serwisu
            experiment_service = self.services.get_experiment_service()
            experiment_result = experiment_service.save_experiment(experiment_grisera, dataset_id)

            if hasattr(experiment_result, 'errors') and experiment_result.errors:
                print(f"❌ Error saving experiment from JSON: {experiment_result.errors}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "EXPERIMENT_IMPORT_ERROR",
                    f"Error saving experiment from JSON: {experiment_result.errors}",
                    str(experiment_json.get("@id", "unknown"))
                )
                return None

            experiment_id = str(experiment_result.id)
            print(f"✅ Successfully imported experiment from JSON with ID: {experiment_id}")

            return experiment_id

        except Exception as e:
            print(f"❌ Exception while importing experiment from JSON: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "EXPERIMENT_IMPORT_EXCEPTION",
                f"Exception while importing experiment from JSON: {str(e)}",
                str(experiment_json.get("@id", "unknown")) if 'experiment_json' in locals() else "unknown"
            )
            return None

    def _process_nested_entity(
            self,
            entity_data: Dict[str, Any],
            dataset_id: str,
            import_id: str,
            processed_ids: Set[str]
    ) -> bool:
        """
        Przetwarza zagnieżdżone encje które były w kolejce

        Args:
            entity_data: Dane encji do przetworzenia
            dataset_id: ID datasetu
            import_id: ID importu
            processed_ids: Zbiór już przetworzonych ID

        Returns:
            True jeśli encja została pomyślnie przetworzona, False w przeciwnym razie
        """
        entity_id = entity_data.get("@id", "unknown")
        print(f"🔄 Processing nested entity: {entity_id}")

        # Sprawdź czy już przetwarzana
        if entity_id in processed_ids:
            print(f"⚠️ Nested entity already processed: {entity_id}")
            return False

        try:
            # Zidentyfikuj typ nested entity z rdf:type
            entity_types = entity_data.get("rdf:type", [])
            if not isinstance(entity_types, list):
                entity_types = [entity_types]

            # Szukaj znanego typu
            target_entity_type = None
            for type_info in entity_types:
                type_id = type_info.get("@id", "") if isinstance(type_info, dict) else str(type_info)

                # Mapuj co:Type na nazwy encji
                if "co:Recording" in type_id:
                    target_entity_type = "Recording"
                    break
                elif "co:RegisteredChannel" in type_id:
                    target_entity_type = "RegisteredChannel"
                    break
                elif "co:RegisteredData" in type_id:
                    target_entity_type = "RegisteredData"
                    break
                elif "co:Participation" in type_id:
                    target_entity_type = "Participation"
                    break

            if not target_entity_type:
                print(f"⚠️ Unknown nested entity type for {entity_id}, skipping")
                return False

            print(f"🏷️ Identified nested entity type: {target_entity_type}")

            # Konwertuj za pomocą converterów
            grisera_object = self._convert_json_to_grisera_object(
                entity_data,
                target_entity_type,
                dataset_id,
                import_id
            )

            if not grisera_object:
                print(f"❌ Failed to convert nested entity {entity_id} to GRISERA object")
                return False

            # Zapisz używając GRISERA service
            saved_id = self._save_with_grisera_service(grisera_object, target_entity_type, dataset_id, import_id)

            if saved_id:
                processed_ids.add(entity_id)
                print(f"✅ Nested entity {entity_id} saved successfully with MongoDB ID: {saved_id}")
                return True
            else:
                print(f"❌ Failed to save nested entity {entity_id}")
                return False

        except Exception as e:
            print(f"❌ Error processing nested entity {entity_id}: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "NESTED_ENTITY_PROCESSING_ERROR",
                f"Error processing nested entity: {str(e)}",
                entity_id
            )
            return False

    def _build_experiment_scenarios(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Buduje scenariusze na podstawie zaimportowanych eksperymentów.

        NOWA LOGIKA:
        1. Scenariusz (Scenario) = szablon dla Activity (już mamy)
        2. Scenario Execution = konkretne wykonanie scenariusza - grupa Activity Executions z tym samym scenarioExecutionName
        """
        print(f"🎬 Building experiment-based scenarios for import ID: {import_id}")
        scenarios_created = 0
        scenario_executions_created = 0
        processed_activities = set()  # Deduplikacja scenariuszy dla tego samego Activity

        try:
            # KROK 1: Pobierz eksperymenty zaimportowane w tym import_id
            print("📋 Step 1: Fetching experiments imported in this job...")
            query_filter = {
                "import_job_id": import_id
            }

            imported_experiments = self.mongo_api_service.get_documents(
                collection_name=Collections.EXPERIMENT.value,
                dataset_id=import_data.dataset_id,
                query=query_filter
            )

            if not imported_experiments:
                print("ℹ️ No experiments found from this import job")
                return 0

            print(f"📊 Found {len(imported_experiments)} experiments imported in this job")

            # KROK 2: Dla każdego eksperymentu analizuj ActivityExecution w hasScenario
            for experiment_doc in imported_experiments:
                experiment_id = str(experiment_doc.get("id", "unknown"))
                experiment_name = experiment_doc.get("experiment_name", f"Experiment_{experiment_id}")
                print(f"\n🧪 Processing experiment: {experiment_name} (ID: {experiment_id})")

                # KROK 2.1: Pobierz ActivityExecution z has_scenario_data w additional_properties
                activity_executions = self._extract_activity_executions_from_experiment(experiment_doc)
                if not activity_executions:
                    print(f"ℹ️ No ActivityExecution found in experiment {experiment_id}")
                    continue

                print(f"📋 Found {len(activity_executions)} ActivityExecution in hasScenario")

                # KROK 2.2: Zbierz wszystkie unikalne Activities z tego eksperymentu (SZABLON SCENARIUSZA)
                experiment_activities = []
                for ae_data in activity_executions:
                    ae_id = ae_data.get("@id", "unknown")
                    print(f"🔍 Processing ActivityExecution: {ae_id}")

                    # Wyciągnij Activity ID z co:hasActivity
                    activity_source_id = self._extract_activity_id_from_ae(ae_data)
                    if not activity_source_id:
                        print(f"❌ No Activity found in ActivityExecution {ae_id}")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "MISSING_ACTIVITY_IN_AE",
                            f"No co:hasActivity found in ActivityExecution {ae_id}",
                            ae_id
                        )
                        continue

                    # KROK 2.3: Sprawdź czy Activity istnieje w MongoDB
                    activity_mongo_id = self._find_activity_by_source_id(activity_source_id, import_data.dataset_id)
                    if not activity_mongo_id:
                        print(f"❌ Activity with source ID '{activity_source_id}' not found in MongoDB")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "ACTIVITY_NOT_FOUND_IN_MONGO",
                            f"Activity with source ID '{activity_source_id}' not found in MongoDB",
                            activity_source_id
                        )
                        continue

                    # Dodaj do listy Activities dla tego eksperymentu (z deduplikacją)
                    if activity_mongo_id not in [a["mongo_id"] for a in experiment_activities]:
                        experiment_activities.append({
                            "source_id": activity_source_id,
                            "mongo_id": activity_mongo_id
                        })
                        print(f"✅ Added Activity {activity_source_id} (MongoDB ID: {activity_mongo_id})")
                    # else:
                        # print(f"⚠️ Activity {activity_source_id} already in list, skipping duplicate")

                # KROK 2.4: Stwórz jeden scenariusz-szablon dla wszystkich Activities z eksperymentu
                if experiment_activities:
                    scenario_name = f"Scenario Template for Experiment {experiment_name}"
                    scenario_description = f"Template scenario containing {len(experiment_activities)} activities from experiment '{experiment_name}'"

                    # Stwórz additional_properties z wszystkimi activity_id
                    additional_properties = [
                        PropertyIn(key="name", value=scenario_name),
                        PropertyIn(key="description", value=scenario_description),
                        PropertyIn(key="auto_generated", value="true"),
                        PropertyIn(key="scenario_type", value="template"),
                        PropertyIn(key="source_experiment_id", value=experiment_id),
                        PropertyIn(key="import_job_id", value=import_id),
                        PropertyIn(key="status", value="completed")
                    ]

                    # Dodaj wszystkie activity_id jako osobne PropertyIn
                    for activity in experiment_activities:
                        additional_properties.append(PropertyIn(
                            key="activity_id",
                            value=activity["mongo_id"]
                        ))
                        print(f"🎯 Added activity_id: {activity['mongo_id']} (source: {activity['source_id']})")

                    scenario_in = ScenarioIn(
                        experiment_id=experiment_id,
                        activity_executions=[],  # Pusta lista - activity_id będzie w additional_properties
                        additional_properties=additional_properties
                    )

                    # KROK 2.5: Zapisz scenariusz szablon
                    try:
                        scenario_service = self.services.get_scenario_service()
                        scenario_result = scenario_service.save_scenario(scenario_in, import_data.dataset_id)

                        # Debug: sprawdź co zwraca serwis
                        print(
                            f"🔍 Scenario service result: id={getattr(scenario_result, 'id', 'MISSING')}, errors={getattr(scenario_result, 'errors', 'NONE')}")

                        if hasattr(scenario_result, 'errors') and scenario_result.errors:
                            print(f"❌ Error creating template scenario: {scenario_result.errors}")
                            self._log_import_error(
                                import_id,
                                import_data.dataset_id,
                                "SCENARIO_TEMPLATE_CREATION_ERROR",
                                f"Failed to create template scenario: {scenario_result.errors}",
                                scenario_name
                            )
                        elif not hasattr(scenario_result, 'id') or scenario_result.id is None:
                            print(f"❌ Template scenario created but ID is missing or None")
                            self._log_import_error(
                                import_id,
                                import_data.dataset_id,
                                "SCENARIO_TEMPLATE_ID_MISSING",
                                f"Template scenario created but ID is missing or None",
                                scenario_name
                            )
                        else:
                            template_scenario_id = str(scenario_result.id)
                            scenarios_created += 1
                            print(
                                f"🎭 Created template scenario {scenarios_created}: {template_scenario_id} with {len(experiment_activities)} activities")

                            # KROK 3: Stwórz Scenario Executions na podstawie Activity Executions
                            executions_created = self._create_scenario_executions(
                                experiment_id,
                                template_scenario_id,
                                activity_executions,
                                import_data.dataset_id,
                                import_id
                            )
                            scenario_executions_created += executions_created
                            print(
                                f"🎯 Created {executions_created} scenario executions for template {template_scenario_id}")

                    except Exception as e:
                        print(f"❌ Exception creating template scenario: {str(e)}")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "SCENARIO_TEMPLATE_CREATION_EXCEPTION",
                            f"Exception creating template scenario: {str(e)}",
                            scenario_name
                        )
                else:
                    print(f"⚠️ No valid Activities found for experiment {experiment_id}")

            print(
                f"🎭 Scenario building completed. Created {scenarios_created} template scenarios and {scenario_executions_created} scenario executions")

            # NOWA LOGIKA: Dodaj participantów do eksperymentów
            print(f"\n👥 FAZA 2: Adding participants to experiments from import job: {import_id}")
            participants_processed = self._process_participants_for_experiments(imported_experiments, import_id,
                                                                                import_data.dataset_id)
            print(f"✅ Participant processing completed. Updated {participants_processed} experiments with participants")

            return scenarios_created + scenario_executions_created

        except Exception as e:
            print(f"❌ Error in scenario building: {str(e)}")
            self._log_import_error(
                import_id,
                import_data.dataset_id,
                "SCENARIO_BUILDING_ERROR",
                f"Error in scenario building: {str(e)}"
            )
            return scenarios_created

    def _extract_activity_executions_from_experiment(self, experiment_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Wyciąga pełne dane ActivityExecution z has_scenario_data w additional_properties
        """
        additional_properties = experiment_doc.get("additional_properties", [])
        if additional_properties is None:
            additional_properties = []
        for prop in additional_properties:
            if prop.get("key") == "has_scenario_data":
                scenario_data_str = prop.get("value", "")
                if scenario_data_str:
                    try:
                        import json
                        return json.loads(scenario_data_str)
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON in has_scenario_data: {scenario_data_str}")
                        return []

        print("ℹ️ No has_scenario_data found in experiment")
        return []

    def _extract_activity_id_from_ae(self, ae_data: Dict[str, Any]) -> str:
        """
        Wyciąga Activity ID z ActivityExecution data
        """
        has_activity = ae_data.get("co:hasActivity", [])
        if has_activity and len(has_activity) > 0:
            activity_ref = has_activity[0]
            return activity_ref.get("@id", "").replace(":", "")
        return ""

    def _find_activity_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Activity w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            query_filter = {
                "external_id": f":{source_id}"
            }

            activities = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if activities and len(activities) > 0:
                return str(activities[0].get("id", ""))
            return ""

        except Exception as e:
            print(f"❌ Error finding Activity by source_id {source_id}: {e}")
            return ""

    def _find_activity_execution_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ActivityExecution w MongoDB po source_id i zwraca jego MongoDB ID.

        POPRAWKA: ActivityExecution są embedded w Activity documents, nie w osobnej kolekcji!
        """
        try:
            print(f"🔍 Searching for ActivityExecution with source_id: {source_id}")

            query_filter = {
                "activity_executions": {
                    "$elemMatch": {
                        "external_id": f"{source_id}"
                    }
                }
            }

            activities_with_matching_executions = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,  # SZUKAJ W ACTIVITIES, NIE ACTIVITY_EXECUTIONS!
                dataset_id=dataset_id,
                query=query_filter
            )

            print(
                f"🔍 Found {len(activities_with_matching_executions) if activities_with_matching_executions else 0} activities with matching ActivityExecution")

            # Przeszukaj embedded activity_executions w znalezionych activities
            for activity_doc in activities_with_matching_executions:
                activity_executions = activity_doc.get("activity_executions", [])

                for ae_doc in activity_executions:
                    # Sprawdź czy ten ActivityExecution ma odpowiedni source_entity_ref
                    external_id = ae_doc.get("external_id")
                    if source_id == external_id or source_id == external_id.replace(":", ""):
                        ae_id = str(ae_doc.get("id", ""))
                        print(f"✅ Found ActivityExecution: {source_id} -> MongoDB ID: {ae_id}")
                        return ae_id
                    else:
                        print(f"🔍 Checking ActivityExecution with external_id: {external_id}")
                        print(f"🔍 Searching ActivityExecution with source_id: {source_id}")
                    # for prop in additional_properties:
                    #     if (prop.get("key") == "source_entity_ref" and
                    #         prop.get("value") == f":{source_id}"):
                    #         ae_id = str(ae_doc.get("id", ""))
                    #         print(f"✅ Found ActivityExecution: {source_id} -> MongoDB ID: {ae_id}")
                    #         return ae_id

            print(f"❌ ActivityExecution with source_id '{source_id}' not found in any activity")
            return ""

        except Exception as e:
            print(f"❌ Error finding ActivityExecution by source_id {source_id}: {e}")
            return ""

    def _find_participant_state_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ParticipantState w MongoDB po source_id i zwraca jego MongoDB ID.
        POPRAWKA: ParticipantState jest embedded w participants.participant_states[]
        """
        try:
            print(f"🔍 Searching for ParticipantState with source_id: {source_id}")

            # Szukaj w kolekcji participants w embedded participant_states array
            query_filter = {
                "participant_states": {
                    "$elemMatch": {
                        "external_id": f"{source_id}"
                    }
                }
            }

            print(f"🔍 Query filter for embedded ParticipantState: {query_filter}")

            participants_with_states = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,  # Szukamy w participants!
                dataset_id=dataset_id,
                query=query_filter
            )

            print(
                f"🔍 Found {len(participants_with_states) if participants_with_states else 0} participants with matching ParticipantState")

            if participants_with_states and len(participants_with_states) > 0:
                participant_doc = participants_with_states[0]

                # Znajdź konkretny ParticipantState w participant_states array
                for ps in participant_doc.get("participant_states", []):
                    if ps.get("external_id") == source_id:
                        ps_id = str(ps.get("id", ""))
                        print(f"✅ Found embedded ParticipantState: {source_id} -> MongoDB ID: {ps_id}")
                        return ps_id

                    # for prop in ps.get("additional_properties", []):
                    #     if prop.get("key") == "source_entity_ref" and prop.get("value") == f":{source_id}":
                    #         ps_id = str(ps.get("id", ""))
                    #         print(f"✅ Found embedded ParticipantState: {source_id} -> MongoDB ID: {ps_id}")
                    #         return ps_id

            print(f"❌ ParticipantState not found for source ID: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding ParticipantState by source_id {source_id}: {e}")
            return ""

    def _find_participant_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Participant w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            print(f"🔍 Searching for Participant with source_id: {source_id}")

            query_filter = {
                "external_id": f":{source_id}"
            }

            print(f"🔍 Query filter: {query_filter}")

            participants = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            print(f"🔍 Found {len(participants) if participants else 0} participants")

            if participants and len(participants) > 0:
                participant_id = str(participants[0].get("id", ""))
                print(f"✅ Found Participant: {source_id} -> MongoDB ID: {participant_id}")
                return participant_id

            # Jeśli nie znaleziono, spróbuj znaleźć wszystkie participants z import_job_id aby zobaczyć co mamy
            debug_query = {
                "additional_properties": {
                    "$elemMatch": {
                        "key": "source_entity_ref"
                    }
                }
            }

            all_participants = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,
                dataset_id=dataset_id,
                query=debug_query
            )

            print(
                f"🔍 DEBUG: Found {len(all_participants) if all_participants else 0} total participants with source_entity_ref")
            for i, participant in enumerate(all_participants[:3]):  # Pokaż pierwsze 3
                for prop in participant.get("additional_properties", []):
                    if prop.get("key") == "source_entity_ref":
                        print(f"🔍 DEBUG: Participant {i + 1} has source_entity_ref: '{prop.get('value')}'")
                        break

            return ""

        except Exception as e:
            print(f"❌ Error finding Participant by source_id {source_id}: {e}")
            return ""

    # def _find_participation_by_source_id(self, source_id: str, dataset_id: str) -> str:
    #     """
    #     Znajduje Participation w MongoDB po source_id i zwraca jego MongoDB ID
    #     """
    #     try:
    #         print(f"🔍 Searching for Participation with source_id: {source_id}")
    #
    #         query_filter = {
    #             "additional_properties": {
    #                 "$elemMatch": {
    #                     "key": "source_entity_ref",
    #                     "value": f":{source_id}"
    #                 }
    #             }
    #         }
    #
    #         participations = self.mongo_api_service.get_documents(
    #             collection_name=Collections.PARTICIPATION.value,
    #             dataset_id=dataset_id,
    #             query=query_filter
    #         )
    #
    #         if participations and len(participations) > 0:
    #             participation_id = str(participations[0].get("id", ""))
    #             print(f"✅ Found Participation: {source_id} -> MongoDB ID: {participation_id}")
    #             return participation_id
    #
    #         print(f"❌ Participation not found for source ID: {source_id}")
    #         return ""
    #
    #     except Exception as e:
    #         print(f"❌ Error finding Participation by source_id {source_id}: {e}")
    #         return ""
    #
    # def _find_registered_channel_by_source_id(self, source_id: str, dataset_id: str) -> str:
    #     """
    #     Znajduje RegisteredChannel w MongoDB po source_id i zwraca jego MongoDB ID
    #     """
    #     try:
    #         print(f"🔍 Searching for RegisteredChannel with source_id: {source_id}")
    #
    #         query_filter = {
    #             "additional_properties": {
    #                 "$elemMatch": {
    #                     "key": "source_entity_ref",
    #                     "value": f":{source_id}"
    #                 }
    #             }
    #         }
    #
    #         registered_channels = self.mongo_api_service.get_documents(
    #             collection_name=Collections.REGISTERED_CHANNEL.value,
    #             dataset_id=dataset_id,
    #             query=query_filter
    #         )
    #
    #         if registered_channels and len(registered_channels) > 0:
    #             rc_id = str(registered_channels[0].get("id", ""))
    #             print(f"✅ Found RegisteredChannel: {source_id} -> MongoDB ID: {rc_id}")
    #             return rc_id
    #
    #         print(f"❌ RegisteredChannel not found for source ID: {source_id}")
    #         return ""
    #
    #     except Exception as e:
    #         print(f"❌ Error finding RegisteredChannel by source_id {source_id}: {e}")
    #         return ""
    def _find_participation_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Participation w MongoDB po source_id i zwraca jego MongoDB ID
        NOWA WERSJA - external_id (dla Recording)
        """
        try:
            print(f"🔍 Searching for Participation with external_id: :{source_id}")

            # OPCJA 1: Szukaj po external_id (nowa metoda)
            query_filter = {
                "external_id": source_id
            }

            participations = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPATION.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if participations and len(participations) > 0:
                participation_id = str(participations[0].get("id", ""))
                print(f"✅ Found Participation (via external_id): {source_id} -> MongoDB ID: {participation_id}")
                return participation_id

            # OPCJA 2: Fallback - szukaj po additional_properties (stara metoda)
            print(f"🔄 Fallback: Searching via additional_properties for: {source_id}")
            query_filter_fallback = {
                "external_id": f":{source_id}"
            }

            participations_fallback = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPATION.value,
                dataset_id=dataset_id,
                query=query_filter_fallback
            )

            if participations_fallback and len(participations_fallback) > 0:
                participation_id = str(participations_fallback[0].get("id", ""))
                print(f"✅ Found Participation (via fallback): {source_id} -> MongoDB ID: {participation_id}")
                return participation_id

            print(f"❌ Participation not found for source ID: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding Participation by source_id {source_id}: {e}")
            return ""

    def _find_registered_channel_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje RegisteredChannel w MongoDB po source_id i zwraca jego MongoDB ID
        NOWA WERSJA - external_id (dla Recording)
        """
        try:
            print(f"🔍 Searching for RegisteredChannel with external_id: {source_id}")

            # OPCJA 1: Szukaj po external_id (nowa metoda)
            query_filter = {
                "external_id": source_id
            }

            registered_channels = self.mongo_api_service.get_documents(
                collection_name=Collections.REGISTERED_CHANNEL.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if registered_channels and len(registered_channels) > 0:
                rc_id = str(registered_channels[0].get("id", ""))
                print(f"✅ Found RegisteredChannel (via external_id): {source_id} -> MongoDB ID: {rc_id}")
                return rc_id

            # OPCJA 2: Fallback - szukaj po additional_properties (stara metoda)
            print(f"🔄 Fallback: Searching via additional_properties for: {source_id}")
            query_filter_fallback = {
                "external_id": f":{source_id}"
            }

            registered_channels_fallback = self.mongo_api_service.get_documents(
                collection_name=Collections.REGISTERED_CHANNEL.value,
                dataset_id=dataset_id,
                query=query_filter_fallback
            )

            if registered_channels_fallback and len(registered_channels_fallback) > 0:
                rc_id = str(registered_channels_fallback[0].get("id", ""))
                print(f"✅ Found RegisteredChannel (via fallback): {source_id} -> MongoDB ID: {rc_id}")
                return rc_id

            print(f"❌ RegisteredChannel not found for source ID: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding RegisteredChannel by source_id {source_id}: {e}")
            return ""

    def _save_participation_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje Participation z mapowaniem source IDs na MongoDB IDs.
        PROSTE MAPOWANIE: source_entity_ref -> MongoDB ID

        MAPOWANIE:
        - activity_execution_id: source_id -> MongoDB ID ActivityExecution (embedded w activities)
        - participant_state_id: source_id -> MongoDB ID ParticipantState (kolekcja participant_states)
        """
        try:
            print(f"💾 Saving Participation with simple ID mapping...")

            print(f"🔍 Original activity_execution_id: {grisera_object.activity_execution_id}")
            print(f"🔍 Original participant_state_id: {grisera_object.participant_state_id}")

            # KROK 1: Mapuj activity_execution_id przez source_entity_ref
            mapped_activity_execution_id = grisera_object.activity_execution_id

            ae_source_id = str(grisera_object.activity_execution_id)
            ae_mongo_id = self._find_activity_execution_by_source_id(ae_source_id, dataset_id)

            if ae_mongo_id:
                mapped_activity_execution_id = ae_mongo_id
                print(f"✅ Mapped activity_execution_id: {grisera_object.activity_execution_id} -> {ae_mongo_id}")
            else:
                print(f"❌ ActivityExecution not found for source ID: {ae_source_id}")
                return None

            # KROK 2: Mapuj participant_state_id przez source_entity_ref -> na ParticipantState ID!
            mapped_participant_state_id = grisera_object.participant_state_id
            if grisera_object.participant_state_id and str(grisera_object.participant_state_id).startswith(":"):
                # To jest source ID, znajdź MongoDB ID ParticipantState
                participant_state_source_id = str(grisera_object.participant_state_id)
                participant_state_mongo_id = self._find_participant_state_by_source_id(participant_state_source_id,
                                                                                       dataset_id)

                if participant_state_mongo_id:
                    mapped_participant_state_id = participant_state_mongo_id
                    print(
                        f"✅ Mapped participant_state_id: {grisera_object.participant_state_id} -> ParticipantState ID: {participant_state_mongo_id}")
                else:
                    print(f"❌ ParticipantState not found for source ID: {participant_state_source_id}")
                    return None

            if not mapped_activity_execution_id or not mapped_participant_state_id:
                print(f"❌ Missing required IDs after mapping")
                return None

            # KROK 4: Utwórz nowy obiekt Participation z mapowanymi MongoDB IDs
            grisera_object.activity_execution_id = mapped_activity_execution_id
            grisera_object.participant_state_id = mapped_participant_state_id

            # KROK 5: Zapisz Participation używając serwisu
            print(f"✅ Participation being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_participation_service().save_participation(grisera_object, dataset_id)
            saved_participation_id = str(getattr(result, 'id', 'unknown'))
            print(f"✅ Participation saved with MongoDB ID: {saved_participation_id}")

            print(
                f"🔗 Final mapping: ActivityExecution({grisera_object.activity_execution_id} -> {mapped_activity_execution_id}), ParticipantState({grisera_object.participant_state_id} -> {mapped_participant_state_id})")

            return result

        except Exception as e:
            print(f"❌ Error saving Participation with mapping: {e}")
            raise e

    def _save_activity_execution_with_scenario_linking(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje ActivityExecution z mapowaniem activity_id i linkiem do scenariusza
        """
        try:
            print(f"💾 Saving ActivityExecution with scenario linking...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                print("⚠️ No source_entity_ref found in ActivityExecution")
                # Zapisz bez mapowania
                return self.services.get_activity_execution_service().save_activity_execution(grisera_object,
                                                                                              dataset_id)

            print(f"🔍 ActivityExecution source ID: {source_entity_ref}")

            # KROK 2: Mapuj activity_id z source ID na MongoDB ID
            if grisera_object.activity_id and grisera_object.activity_id.startswith(":"):
                # To jest source ID, mapuj na MongoDB ID
                activity_source_id = grisera_object.activity_id.replace(":", "")
                activity_mongo_id = self._find_activity_by_source_id(activity_source_id, dataset_id)


                if activity_mongo_id:
                    grisera_object.activity_id = activity_mongo_id  # Zaktualizuj na MongoDB ID
                    # print(f"✅ Mapped activity_id: {grisera_object.activity_id} -> {activity_mongo_id}")
                    # from grisera import ActivityExecutionIn, PropertyIn
                    # new_ae = ActivityExecutionIn(
                    #     activity_id=activity_mongo_id,
                    #     arrangement_id=grisera_object.arrangement_id,
                    #     additional_properties=grisera_object.additional_properties,
                    #     external_id=grisera_object.external_id,
                    #     import_job_id=grisera_object.import_job_id
                    # )
                    # grisera_object = new_ae
                else:
                    print(f"❌ Could not find Activity in MongoDB for source ID: {activity_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "ACTIVITY_NOT_FOUND_FOR_AE",
                        f"Activity with source ID '{activity_source_id}' not found for ActivityExecution",
                        source_entity_ref
                    )

            # KROK 3: Zapisz ActivityExecution
            print(f"✅ ActivityExecution being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_activity_execution_service().save_activity_execution(grisera_object, dataset_id)
            saved_ae_id = str(getattr(result, 'id', 'unknown'))
            print(f"✅ ActivityExecution saved with ID: {saved_ae_id}. Activity : {grisera_object.__dict__}")

            # KROK 4: Znajdź i zaktualizuj scenariusz który miał to ActivityExecution w has_scenario_data
            updated_scenarios = self._update_scenarios_with_activity_execution(
                source_entity_ref, saved_ae_id, dataset_id
            )

            if updated_scenarios > 0:
                print(f"🎭 Updated {updated_scenarios} scenarios with ActivityExecution {saved_ae_id}")
            else:
                print(f"ℹ️ No scenarios found to update with ActivityExecution {saved_ae_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving ActivityExecution with scenario linking: {e}")
            raise e

    def _update_scenarios_with_activity_execution(self, ae_source_id: str, ae_mongo_id: str, dataset_id: str) -> int:
        """
        Znajduje scenariusze które mają to ActivityExecution w has_scenario_data i aktualizuje je
        """
        try:
            print(f"🔍 Looking for scenarios containing ActivityExecution {ae_source_id}")

            # Pobierz scenariusze które mają to ActivityExecution w scenario_data
            query_filter = {
                "additional_properties": {
                    "$elemMatch": {
                        "key": "has_scenario_data",
                        "value": {"$regex": f'"@id"\\s*:\\s*"{ae_source_id}"'}
                    }
                }
            }

            scenarios = self.mongo_api_service.get_documents(
                collection_name=Collections.SCENARIO.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            updated_count = 0
            for scenario in scenarios:
                scenario_id = str(scenario.get("id", "unknown"))
                print(f"🎭 Found matching scenario: {scenario_id}")

                # Sprawdź czy activity_executions jest puste i zaktualizuj
                current_ae_list = scenario.get("activity_executions", [])
                if not current_ae_list:
                    # Dodaj ActivityExecution do scenario
                    try:
                        # Aktualizuj scenario używając ScenarioService
                        from grisera import ScenarioIn, ActivityExecutionIn, PropertyIn

                        # Stwórz ActivityExecutionIn reference dla scenario
                        ae_ref = ActivityExecutionIn(
                            activity_id=None,  # Nie potrzebujemy activity_id w referencji
                            arrangement_id=None,
                            additional_properties=[
                                PropertyIn(key="activity_execution_ref", value=ae_mongo_id)
                            ]
                        )

                        scenario_update = ScenarioIn(
                            experiment_id=scenario.get("experiment_id"),
                            activity_executions=[ae_ref],  # Dodaj referencję do ActivityExecution
                            additional_properties=scenario.get("additional_properties", [])
                        )

                        # Zaktualizuj scenario
                        scenario_service = self.services.get_scenario_service()
                        print(f"🎭 Would update scenario {scenario_id} with ActivityExecution {ae_mongo_id}")
                        updated_count += 1

                    except Exception as e:
                        print(f"❌ Error updating scenario {scenario_id}: {e}")
                else:
                    print(f"ℹ️ Scenario {scenario_id} already has activity_executions, skipping")

            return updated_count

        except Exception as e:
            print(f"❌ Error updating scenarios with ActivityExecution: {e}")
            return 0

    def _create_scenario_executions(self, experiment_id: str, template_scenario_id: str,
                                    activity_executions: List[Dict[str, Any]], dataset_id: str, import_id: str) -> int:
        """
        Tworzy osobne Scenario Executions dla każdego ActivityExecution który pasuje do template scenario.

        NOWA LOGIKA:
        1. Pobierz template scenario i sprawdź jakie activity_id ma
        2. Dla każdego ActivityExecution sprawdź czy jego activity_id pasuje do template scenario
        3. Jeśli TAK → stwórz osobny "Scenario Execution X" z tym jednym ActivityExecution
        4. Każdy Scenario Execution = 1 ActivityExecution
        """
        try:
            print(f"🎬 Creating individual scenario executions for template scenario {template_scenario_id}")

            # KROK 1: Pobierz template scenario i wyciągnij activity_id z additional_properties
            try:
                scenario_dict = self.mongo_api_service.get_document(
                    template_scenario_id,
                    Collections.SCENARIO.value,
                    dataset_id
                )
                if not scenario_dict:
                    print(f"❌ Template scenario {template_scenario_id} not found")
                    return 0

                print(f"✅ Retrieved template scenario: {scenario_dict.get('id')}")

                # Wyciągnij activity_id z additional_properties template scenario
                template_activity_ids = []
                for prop in scenario_dict.get("additional_properties", []):
                    if prop.get("key") == "activity_id":
                        template_activity_ids.append(prop.get("value"))

                if not template_activity_ids:
                    print(f"⚠️ Template scenario has no activity_id in additional_properties")
                    return 0

                print(f"🎯 Template scenario activity_ids: {template_activity_ids}")

                # Upewnij się że activity_executions jest listą
                if "activity_executions" not in scenario_dict:
                    scenario_dict["activity_executions"] = []

            except Exception as e:
                print(f"❌ Error retrieving template scenario {template_scenario_id}: {e}")
                return 0

            # KROK 2: Pobierz Activity które zawierają Activity Executions z tego import job
            query_filter = {
                "import_job_id": import_id,
                "activity_executions": {"$exists": True, "$ne": []}  # Activity musi mieć activity_executions
            }

            activities_with_executions = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if not activities_with_executions:
                print("ℹ️ No Activities with Activity Executions found from this import job")
                return 0

            print(f"📋 Found {len(activities_with_executions)} Activities with Activity Executions from this import")

            # KROK 3: Przejdź przez wszystkie Activity Executions i sprawdź które pasują do template scenario
            matching_activity_executions = []
            total_ae_found = 0

            for activity_doc in activities_with_executions:
                activity_id = str(activity_doc.get("id"))
                activity_name = activity_doc.get("activity", "unknown")
                ae_list = activity_doc.get("activity_executions", [])

                print(
                    f"🔍 Processing Activity '{activity_name}' (ID: {activity_id}) with {len(ae_list)} Activity Executions")

                # Sprawdź czy to Activity pasuje do template scenario
                if activity_id in template_activity_ids:
                    print(f"✅ Activity {activity_name} (ID: {activity_id}) MATCHES template scenario!")

                    for ae_doc in ae_list:
                        total_ae_found += 1

                        # Znajdź source_entity_ref (oryginalną nazwę z JSON)
                        source_name = ae_doc.get("external_id", "Unknown")
                        if source_name and source_name.startswith(":"):
                            source_name = source_name[1:]

                        matching_activity_executions.append({
                            "ae_doc": ae_doc,
                            "source_name": source_name,
                            "activity_name": activity_name
                        })

                        print(f"📎 Added matching ActivityExecution: {source_name} (ID: {ae_doc.get('id')})")
                else:
                    print(f"⚠️ Activity {activity_name} (ID: {activity_id}) does NOT match template scenario")

            print(f"📊 Total matching Activity Executions found: {len(matching_activity_executions)}")

            if not matching_activity_executions:
                print("ℹ️ No matching Activity Executions found for template scenario")
                return 0

            # KROK 4: Stwórz osobny Scenario Execution dla każdego pasującego ActivityExecution
            scenario_executions_created = 0

            for ae_info in matching_activity_executions:
                ae_doc = ae_info["ae_doc"]
                source_name = ae_info["source_name"]
                activity_name = ae_info["activity_name"]
                ae_id = str(ae_doc.get("id"))

                # Globalny licznik dla nazw Scenario Execution
                scenario_execution_name = f"Scenario Execution {self.scenario_execution_counter}"
                self.scenario_execution_counter += 1
                print(f"\n🎯 Creating {scenario_execution_name} for ActivityExecution '{source_name}'")

                # Stwórz listę z jednym ActivityExecution ID
                single_ae_list = [ae_id]

                # Dodaj jako osobną listę do activity_executions template scenario
                scenario_dict["activity_executions"].append(single_ae_list)
                scenario_executions_created += 1

                print(f"✅ Created {scenario_execution_name}: [{source_name}] (ID: {ae_id})")

            # KROK 5: Zapisz zaktualizowany template scenario do MongoDB
            try:
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.SCENARIO.value,
                    id=template_scenario_id,
                    new_document=scenario_dict,
                    dataset_id=dataset_id
                )

                print(
                    f"🎭 Successfully updated template scenario {template_scenario_id} with {scenario_executions_created} individual scenario executions")

                # Loguj finalną strukturę
                print(
                    f"📊 Final activity_executions structure: {len(scenario_dict['activity_executions'])} scenario executions")
                for i, execution in enumerate(scenario_dict["activity_executions"]):
                    print(
                        f"   Scenario Execution {i + 1}: {len(execution)} Activity Execution (ID: {execution[0] if execution else 'empty'})")

                return scenario_executions_created

            except Exception as e:
                print(f"❌ Error updating template scenario {template_scenario_id}: {e}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "SCENARIO_UPDATE_ERROR",
                    f"Error updating template scenario with individual executions: {str(e)}",
                    template_scenario_id
                )
                return 0

        except Exception as e:
            print(f"❌ Error creating individual scenario executions: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "SCENARIO_EXECUTION_CREATION_ERROR",
                f"Error creating individual scenario executions: {str(e)}"
            )
            return 0

    def _find_imported_participants(self, import_id: str, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Znajduje participantów zaimportowanych w tym import job.

        Args:
            import_id: ID procesu importu
            dataset_id: ID datasetu

        Returns:
            Lista słowników z danymi participantów (id, name, source_id)
        """
        try:
            print(f"👥 Searching for participants imported in job: {import_id}")

            query_filter = {
                "import_job_id": import_id
            }

            imported_participants = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if not imported_participants:
                print(f"ℹ️ No participants found for import job: {import_id}")
                return []

            participants_data = []
            for participant_doc in imported_participants:
                participant_id = str(participant_doc.get("id", "unknown"))
                participant_name = participant_doc.get("name", "Unknown Participant")

                source_id = participant_doc.get("external_id", "Unknown")
                if source_id and source_id.startswith(":"):
                    source_id = source_id[1:]

                participants_data.append({
                    "mongo_id": participant_id,
                    "name": participant_name,
                    "source_id": source_id
                })

                print(f"✅ Found participant: {participant_name} (MongoDB ID: {participant_id}, Source: {source_id})")

            print(f"📊 Total participants found: {len(participants_data)}")
            return participants_data

        except Exception as e:
            print(f"❌ Error finding imported participants: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "PARTICIPANT_SEARCH_ERROR",
                f"Error finding imported participants: {str(e)}"
            )
            return []

    def _add_participants_to_experiment(self, experiment_id: str, participants: List[Dict[str, Any]],
                                        dataset_id: str) -> bool:
        """
        Dodaje participantów do eksperymentu przez aktualizację additional_properties.
        Wykorzystuje wzorzec z frontend UI (participant_id w additional_properties).

        Args:
            experiment_id: MongoDB ID eksperymentu
            participants: Lista participantów (z mongo_id, name, source_id)
            dataset_id: ID datasetu

        Returns:
            True jeśli operacja zakończona sukcesem, False w przeciwnym razie
        """
        try:
            print(f"👥 Adding {len(participants)} participants to experiment: {experiment_id}")

            # KROK 1: Pobierz istniejący dokument eksperymentu
            experiment_doc = self.mongo_api_service.get_document(
                experiment_id,
                Collections.EXPERIMENT.value,
                dataset_id
            )

            if not experiment_doc:
                print(f"❌ Experiment {experiment_id} not found")
                return False

            experiment_name = experiment_doc.get("experiment_name", f"Experiment_{experiment_id}")
            print(f"✅ Retrieved experiment: {experiment_name}")

            # KROK 2: Przygotuj additional_properties z participant_id (wzorzec frontend)
            current_additional_properties = experiment_doc.get("additional_properties", [])
            if current_additional_properties is None:
                current_additional_properties = []
            # Sprawdź czy już są participanci w additional_properties
            existing_participant_ids = set()
            for prop in current_additional_properties:
                if prop.get("key") == "participant_id":
                    existing_participant_ids.add(prop.get("value"))

            print(f"📋 Existing participants in experiment: {len(existing_participant_ids)}")

            # KROK 3: Dodaj nowych participantów (unikaj duplikatów)
            new_participants_added = 0
            for participant in participants:
                participant_mongo_id = participant["mongo_id"]
                participant_name = participant["name"]

                if participant_mongo_id not in existing_participant_ids:
                    # Dodaj participant_id do additional_properties (wzorzec frontend)
                    current_additional_properties.append({
                        "key": "participant_id",
                        "value": participant_mongo_id
                    })
                    new_participants_added += 1
                    print(f"✅ Added participant to experiment: {participant_name} (ID: {participant_mongo_id})")
                else:
                    print(f"⚠️ Participant already in experiment: {participant_name} (ID: {participant_mongo_id})")

            if new_participants_added == 0:
                print(f"ℹ️ No new participants to add to experiment {experiment_name}")
                return True

            # KROK 4: Zaktualizuj dokument eksperymentu (replace całego dokumentu)
            experiment_doc["additional_properties"] = current_additional_properties

            self.mongo_api_service.update_document_with_dict(
                collection_name=Collections.EXPERIMENT.value,
                id=experiment_id,
                new_document=experiment_doc,
                dataset_id=dataset_id
            )

            print(f"🎉 Successfully added {new_participants_added} participants to experiment '{experiment_name}'")
            print(
                f"📊 Total participants in experiment: {len([p for p in current_additional_properties if p.get('key') == 'participant_id'])}")

            return True

        except Exception as e:
            print(f"❌ Error adding participants to experiment {experiment_id}: {str(e)}")
            return False

    def _process_participants_for_experiments(self, experiments: List[Dict[str, Any]], import_id: str,
                                              dataset_id: str) -> int:
        """
        Przetwarza i dodaje participantów do eksperymentów zaimportowanych w tym import job.

        Args:
            experiments: Lista słowników z danymi eksperymentów
            import_id: ID procesu importu
            dataset_id: ID datasetu

        Returns:
            Liczba zaktualizowanych eksperymentów
        """
        try:
            print(f"👥 Starting participant processing for {len(experiments)} experiments")

            # KROK 1: Znajdź wszystkich participantów z tego import job (raz dla wszystkich eksperymentów)
            participants = self._find_imported_participants(import_id, dataset_id)

            if not participants:
                print(f"ℹ️ No participants found for import job: {import_id}")
                return 0

            print(f"📊 Found {len(participants)} participants to add to experiments")

            # KROK 2: Dla każdego eksperymentu dodaj participantów
            updated_count = 0
            for experiment_doc in experiments:
                experiment_id = str(experiment_doc.get("id", "unknown"))
                print(f"🧪 Processing experiment: {experiment_id}")

                if self._add_participants_to_experiment(experiment_id, participants, dataset_id):
                    updated_count += 1
                    print(f"✅ Experiment '{experiment_id}' updated successfully with participants")
                else:
                    print(f"❌ Error updating experiment {experiment_id} with participants")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "EXPERIMENT_PARTICIPANT_UPDATE_FAILED",
                        f"Failed to add participants to experiment {experiment_id}",
                        experiment_id
                    )

            print(f"📈 Participant processing summary: {updated_count}/{len(experiments)} experiments updated")
            return updated_count

        except Exception as e:
            print(f"❌ Error processing participants for experiments: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "PARTICIPANT_PROCESSING_ERROR",
                f"Error processing participants for experiments: {str(e)}"
            )
            return 0

    def _create_participations_direct_insert(self, import_id: str, dataset_id: str) -> int:
        """
        PROSTY DIRECT INSERT do kolekcji participations - bez skomplikowanej logiki konwerterów.

        Algorytm:
        1. Pobierz wszystkich participantów i activity_executions z tego import job
        2. Dla każdego participanta stwórz participant_state (jeśli nie istnieje)
        3. Dla każdego participanta znajdź jego activity_execution przez source mapping
        4. Zrób prosty insert_one do kolekcji 'participations' z participant_state_id

        Args:
            import_id: ID procesu importu
            dataset_id: ID datasetu

        Returns:
            Liczba utworzonych participation rekordów
        """
        try:
            print(f"🤝 Starting direct participation insert for import: {import_id}")

            # KROK 1: Pobierz wszystkich participantów z tego import job
            participants = self._find_imported_participants(import_id, dataset_id)
            if not participants:
                print("ℹ️ No participants found for participation creation")
                return 0

            # KROK 2: Pobierz wszystkie activity_executions z tego import job
            activity_executions = self._find_imported_activity_executions(import_id, dataset_id)
            if not activity_executions:
                print("ℹ️ No activity executions found for participation creation")
                return 0

            print(f"📊 Found {len(participants)} participants and {len(activity_executions)} activity executions")

            # KROK 3: Stwórz participant_states dla każdego participant
            db = self.mongo_api_service.client[dataset_id]
            participant_states_collection = db["participant_states"]
            participations_collection = db["participations"]

            from bson import ObjectId

            participant_state_mapping = {}  # participant_id -> participant_state_id

            for participant in participants:
                participant_mongo_id = participant["mongo_id"]

                # Sprawdź czy participant_state już istnieje dla tego participant
                existing_ps = participant_states_collection.find_one({
                    "participant_id": ObjectId(participant_mongo_id)
                })

                if existing_ps:
                    participant_state_id = str(existing_ps["_id"])
                    print(f"✅ Found existing participant_state for {participant['source_id']}: {participant_state_id}")
                else:
                    # Stwórz nowy participant_state
                    participant_state_doc = {
                        "_id": ObjectId(),
                        "participant_id": ObjectId(participant_mongo_id),
                        "personality_ids": None,
                        "appearance_ids": None,
                        "age": None,
                        "additional_properties": []
                    }

                    result = participant_states_collection.insert_one(participant_state_doc)
                    participant_state_id = str(result.inserted_id)
                    print(f"✅ Created new participant_state for {participant['source_id']}: {participant_state_id}")

                participant_state_mapping[participant_mongo_id] = participant_state_id

            # KROK 4: Stwórz mapowanie source_id -> mongo_id dla activity_executions
            ae_mapping = {ae["source_id"]: ae["mongo_id"] for ae in activity_executions}

            # KROK 5: Direct insert participations według wzorca source ID
            participations_created = 0

            # Mapowanie z przykładu: P09 -> actExecP09, P06 -> actExecP06, etc.
            for participant in participants:
                participant_source_id = participant["source_id"]  # np. "P09"
                participant_mongo_id = participant["mongo_id"]
                participant_state_id = participant_state_mapping[participant_mongo_id]

                # Znajdź pasujący ActivityExecution (np. "actExecP09")
                matching_ae_source_id = f"actExec{participant_source_id}"

                if matching_ae_source_id in ae_mapping:
                    activity_execution_mongo_id = ae_mapping[matching_ae_source_id]

                    # PROSTY INSERT do kolekcji participations
                    participation_doc = {
                        "_id": ObjectId(),
                        "activity_execution_id": ObjectId(activity_execution_mongo_id),
                        "participant_state_id": ObjectId(participant_state_id)  # TERAZ używamy participant_state_id!
                    }

                    # Direct MongoDB insert
                    result = participations_collection.insert_one(participation_doc)
                    participations_created += 1

                    print(
                        f"✅ Created participation: Participant {participant_source_id} -> ActivityExecution {matching_ae_source_id}")
                    print(
                        f"   📊 MongoDB IDs: participant_state_id={participant_state_id}, activity_execution_id={activity_execution_mongo_id}")
                else:
                    print(
                        f"⚠️ No matching ActivityExecution found for participant {participant_source_id} (looking for {matching_ae_source_id})")

            print(f"🎉 Successfully created {participations_created} participation records using direct MongoDB insert")
            return participations_created

        except Exception as e:
            print(f"❌ Error in direct participation insert: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "DIRECT_PARTICIPATION_INSERT_ERROR",
                f"Error in direct participation insert: {str(e)}"
            )
            return 0

    def _find_imported_activity_executions(self, import_id: str, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Znajduje activity_executions zaimportowane w tym import job.

        POPRAWKA: ActivityExecutions są embedded w Activity documents, nie w osobnej kolekcji!

        Returns:
            Lista słowników z danymi activity_executions (mongo_id, source_id)
        """
        try:
            # POPRAWIONE QUERY: Szukaj w kolekcji Activities które mają activity_executions
            query_filter = {
                "import_job_id": import_id,
                "activity_executions": {"$exists": True, "$ne": []}  # Activity musi mieć activity_executions
            }

            activities_with_executions = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,  # SZUKAJ W ACTIVITIES, NIE ACTIVITY_EXECUTIONS!
                dataset_id=dataset_id,
                query=query_filter
            )

            ae_data = []
            for activity_doc in activities_with_executions:
                activity_executions = activity_doc.get("activity_executions", [])

                # Wyciągnij każdy ActivityExecution z embedded array
                for ae_doc in activity_executions:
                    ae_id = str(ae_doc.get("id", "unknown"))

                    # Znajdź source_entity_ref w ActivityExecution
                    source_id = ae_doc.get("external_id", "Unknown")
                    if source_id and source_id.startswith(":"):
                        source_id = source_id[1:]

                    ae_data.append({
                        "mongo_id": ae_id,
                        "source_id": source_id
                    })
                    print(f"🔍 Found embedded ActivityExecution: {source_id} (ID: {ae_id})")

            print(f"📊 Found {len(ae_data)} activity executions for participation creation")
            return ae_data

        except Exception as e:
            print(f"❌ Error finding imported activity executions: {str(e)}")
            return []

    def _save_recording_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje Recording z mapowaniem source IDs na MongoDB IDs dla participation_id i registered_channel_id.
        """
        try:
            print(f"💾 Saving Recording with ID mapping...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                print("⚠️ No source_entity_ref found in Recording")
            else:
                print(f"🔍 Recording source ID: {source_entity_ref}")

            # KROK 2: Mapuj participation_id z source ID na MongoDB ID
            mapped_participation_id = grisera_object.participation_id
            additional_properties = list(
                grisera_object.additional_properties) if grisera_object.additional_properties else []
            participation_source_id = grisera_object.participation_id
            participation_mongo_id = self._find_participation_by_source_id(participation_source_id, dataset_id)

            if participation_mongo_id:
                mapped_participation_id = participation_mongo_id
                print(f"✅ Mapped participation_id: {grisera_object.participation_id} -> {participation_mongo_id}")
            else:
                print(f"❌ Could not find Participation in MongoDB for source ID: {participation_source_id}")
                additional_properties.append(PropertyIn(
                    key="original_participation_id",
                    value=grisera_object.participation_id
                ))
                self._log_import_error(
                        import_id,
                        dataset_id,
                        "PARTICIPATION_NOT_FOUND_FOR_RECORDING",
                        f"Participation with source ID '{participation_source_id}' not found for Recording",
                        source_entity_ref or "unknown"
                    )


            print(f"🔍 Looking fot RegisteredChannel in MongoDB for source ID: {grisera_object.registered_channel_id}")

            # KROK 3: Mapuj registered_channel_id z source ID na MongoDB ID
            registered_channel_source_id = grisera_object.registered_channel_id
            registered_channel_mongo_id = self._find_registered_channel_by_source_id(registered_channel_source_id,
                                                                                        dataset_id)

            if registered_channel_mongo_id:
                mapped_registered_channel_id = registered_channel_mongo_id
                print(f"✅ Mapped registered_channel_id: {grisera_object.registered_channel_id} -> {registered_channel_mongo_id}")
            else:
                print(f"❌ Could not find RegisteredChannel in MongoDB for source ID: {registered_channel_source_id}")
                self._log_import_error(
                        import_id,
                        dataset_id,
                        "REGISTERED_CHANNEL_NOT_FOUND_FOR_RECORDING",
                        f"RegisteredChannel with source ID '{registered_channel_source_id}' not found for Recording",
                        source_entity_ref or "unknown"
                )
                additional_properties.append(PropertyIn(
                        key="original_registered_channel_id",
                        value=grisera_object.registered_channel_id
                    ))
                mapped_registered_channel_id = None
                print(
                        f"➕ Added original registered_channel_id to additional_properties: {grisera_object.registered_channel_id}")

            # KROK 4: Sprawdź czy mapped_participation_id jest prawidłowym MongoDB ObjectId
            if mapped_participation_id and mapped_participation_id.startswith(":"):
                print(f"❌ Invalid participation_id format: {mapped_participation_id} - skipping Recording")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "INVALID_PARTICIPATION_ID_FOR_RECORDING",
                    f"Invalid participation_id format: {mapped_participation_id}",
                    source_entity_ref or "unknown"
                )
                return None

            # KROK 5: Utwórz nowy obiekt Recording z mapowanymi IDs
            # from grisera import RecordingIn
            grisera_object.participation_id = mapped_participation_id
            grisera_object.registered_channel_id = mapped_registered_channel_id

            # KROK 5: Zapisz Recording używając serwisu
            print(f"✅ Recording being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_recording_service().save_recording(grisera_object, dataset_id)
            saved_recording_id = str(getattr(result, 'id', 'unknown'))
            print(f"✅ Recording saved with ID: {saved_recording_id}")

            # KROK 6: Loguj mapowanie dla debugowania
            if mapped_participation_id != grisera_object.participation_id:
                print(
                    f"🔗 Final participation_id mapping: {grisera_object.participation_id} -> {mapped_participation_id}")
            if mapped_registered_channel_id != grisera_object.registered_channel_id:
                print(
                    f"🔗 Final registered_channel_id mapping: {grisera_object.registered_channel_id} -> {mapped_registered_channel_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving Recording with mapping: {e}")
            raise e

    # def _find_registered_channel_by_source_id(self, source_id: str, dataset_id: str) -> str:
    #     """
    #     Znajduje RegisteredChannel w MongoDB po source_id i zwraca jego MongoDB ID
    #     """
    #     try:
    #         query_filter = {
    #             "additional_properties": {
    #                 "$elemMatch": {
    #                     "key": "source_entity_ref",
    #                     "value": f":{source_id}"
    #                 }
    #             }
    #         }
    #
    #         registered_channels = self.mongo_api_service.get_documents(
    #             collection_name=Collections.REGISTERED_CHANNEL.value,
    #             dataset_id=dataset_id,
    #             query=query_filter
    #         )
    #
    #         if registered_channels and len(registered_channels) > 0:
    #             return str(registered_channels[0].get("id", ""))
    #         return ""
    #
    #     except Exception as e:
    #         print(f"❌ Error finding RegisteredChannel by source_id {source_id}: {e}")
    #         return ""

    def _save_registered_channel_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje RegisteredChannel z mapowaniem source IDs na MongoDB IDs dla registered_data_id i channel_id.
        """

        try:
            print(f"💾 Saving RegisteredChannel with ID mapping...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                print("⚠️ No source_entity_ref found in RegisteredChannel")
            else:
                print(f"🔍 RegisteredChannel source ID: {source_entity_ref}")

            # KROK 2: Mapuj registered_data_id z source ID na MongoDB ID
            mapped_registered_data_id = grisera_object.registered_data_id
            if grisera_object.registered_data_id and grisera_object.registered_data_id.startswith(":"):
                # To jest source ID, mapuj na MongoDB ID
                registered_data_source_id = grisera_object.registered_data_id
                registered_data_mongo_id = self._find_registered_data_by_source_id(registered_data_source_id,
                                                                                   dataset_id)

                if registered_data_mongo_id:
                    mapped_registered_data_id = registered_data_mongo_id
                    print(
                        f"✅ Mapped registered_data_id: {grisera_object.registered_data_id} -> {registered_data_mongo_id}")
                else:
                    print(f"❌ Could not find RegisteredData in MongoDB for source ID: {registered_data_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "REGISTERED_DATA_NOT_FOUND_FOR_REGISTERED_CHANNEL",
                        f"RegisteredData with source ID '{registered_data_source_id}' not found for RegisteredChannel",
                        source_entity_ref or "unknown"
                    )

            mapped_channel_id = grisera_object.channel_id
            # if not self.is_uuid(grisera_object.channel_id):
                # To jest source ID, mapuj na MongoDB ID
            channel_source_id = grisera_object.channel_id
            channel_mongo_id = self._find_channel_by_source_id(channel_source_id, dataset_id)

            if channel_mongo_id:
                mapped_channel_id = channel_mongo_id
                print(f"✅ Mapped channel_id: {grisera_object.channel_id} -> {channel_mongo_id}")
            else:
                print(f"⚠️ Could not find Channel in MongoDB for source ID: {channel_source_id}")
                mapped_channel_id = self._find_or_create_channel_by_type_string(
                    channel_source_id,
                    dataset_id,
                    import_id
                )

            # KROK 4: Utwórz nowy obiekt RegisteredChannel z mapowanymi IDs
            grisera_object.registered_data_id = mapped_registered_data_id
            grisera_object.channel_id = mapped_channel_id

            print(f"✅ RegisteredChannel grisera_object: {grisera_object.__dict__}")
            result = self.services.get_registered_channel_service().save_registered_channel(grisera_object, dataset_id)

            saved_registered_channel_id = str(getattr(result, 'id', 'unknown'))
            print(f"✅ RegisteredChannel saved with ID: {saved_registered_channel_id}")

            # KROK 6: Loguj mapowanie dla debugowania
            if mapped_registered_data_id != grisera_object.registered_data_id:
                print(
                    f"🔗 Final registered_data_id mapping: {grisera_object.registered_data_id} -> {mapped_registered_data_id}")
            if mapped_channel_id != grisera_object.channel_id:
                print(f"🔗 Final channel_id mapping: {grisera_object.channel_id} -> {mapped_channel_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving RegisteredChannel with mapping: {e}")
            raise e

    def _find_or_create_channel_by_type_string(self, channel_type_string: str, dataset_id: str,
                                               import_id: str = None) -> str:
        """
        Dopasowuje typ kanału z JSON-a (np. 'co:channelAudio') do istniejącego kanału w MongoDB
        i aktualizuje jego external_id. Jeśli nie znajdzie dopasowania, zwraca UUID kanału 'Unknown'.

        Args:
            channel_type_string (str): String z JSON-a (np. 'co:channelAudio')
            dataset_id (str): ID datasetu
            import_id (str): ID importu (opcjonalne, do logowania)

        Returns:
            str: UUID kanału z MongoDB
        """
        from grisera.channel.channel_model import Types

        try:
            # Wyciągnięcie nazwy typu z stringa (np. 'co:channelAudio' -> 'audio')
            if ':' in channel_type_string:
                type_part = channel_type_string.split(':')[-1]  # Bierzemy część po ':'
                if type_part.startswith('channel'):
                    type_name = type_part[7:].lower()  # Usuwamy 'channel' i robimy lowercase
                else:
                    type_name = type_part.lower()
            else:
                type_name = channel_type_string.lower()

            print(f"🔍 Szukam kanału dla typu: '{type_name}' (z: '{channel_type_string}')")

            # Sprawdzamy czy typ pasuje do któregoś z enum Types
            matching_type = None
            for channel_type in Types:
                channel_type_value = channel_type.value[0]  # Pierwszy element tuple to nazwa typu
                if type_name == channel_type_value.lower() or type_name in channel_type_value.lower():
                    matching_type = channel_type_value
                    break

            if matching_type:
                print(f"✅ Znaleziono dopasowanie: '{matching_type}'")

                # Szukamy kanału w MongoDB po typie
                query_filter = {"type": matching_type}
                channels = self.mongo_api_service.get_documents(
                    collection_name=Collections.CHANNEL.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if channels and len(channels) > 0:
                    channel = channels[0]
                    channel_id = str(channel.get("id", ""))

                    # Aktualizujemy external_id
                    if channel_id:
                        print(f"🔄 Aktualizuję external_id dla kanału {channel_id}")

                        # Użyjemy bezpośredniego zapytania MongoDB do częściowej aktualizacji
                        from bson import ObjectId
                        db = self.mongo_api_service.client[dataset_id]

                        update_result = db[Collections.CHANNEL.value].update_one(
                            {"_id": ObjectId(channel_id)},
                            {"$set": {"external_id": channel_type_string}}
                        )

                        if update_result.modified_count > 0:
                            print(f"✅ Zaktualizowano external_id dla kanału {matching_type}")
                        else:
                            print(f"⚠️ Nie udało się zaktualizować external_id dla kanału {matching_type}")

                    return channel_id
                else:
                    print(f"❌ Nie znaleziono kanału typu '{matching_type}' w MongoDB")
            else:
                print(f"❌ Nie udało się dopasować typu '{type_name}' do żadnego z dostępnych typów kanałów")

            # Jeśli nie znaleźliśmy dopasowania, szukamy/tworzymy kanał 'Unknown'
            print("🔍 Szukam kanału 'Unknown'...")

            unknown_query = {"type": "Unknown"}
            unknown_channels = self.mongo_api_service.get_documents(
                collection_name=Collections.CHANNEL.value,
                dataset_id=dataset_id,
                query=unknown_query
            )

            if unknown_channels and len(unknown_channels) > 0:
                unknown_channel_id = str(unknown_channels[0].get("id", ""))
                print(f"✅ Znaleziono istniejący kanał 'Unknown': {unknown_channel_id}")
                return unknown_channel_id
            else:
                print("➕ Tworzę nowy kanał 'Unknown'...")
                from grisera import ChannelIn

                unknown_channel = ChannelIn(
                    type="Unknown",
                    description="Unknown channel type",
                    import_job_id=import_id,
                    import_timestamp=datetime.now(),
                )

                unknown_channel_id = self.services.get_channel_service().save_channel(unknown_channel, dataset_id)

                if hasattr(unknown_channel_id, 'id'):
                    unknown_channel_id = str(unknown_channel_id.id)
                else:
                    unknown_channel_id = str(unknown_channel_id)

                print(f"✅ Utworzono nowy kanał 'Unknown': {unknown_channel_id}")
                return unknown_channel_id

        except Exception as e:
            print(f"❌ Błąd podczas dopasowywania kanału dla '{channel_type_string}': {e}")

            try:
                fallback_channels = self.mongo_api_service.get_documents(
                    collection_name=Collections.CHANNEL.value,
                    dataset_id=dataset_id,
                    query={}
                )

                if fallback_channels and len(fallback_channels) > 0:
                    fallback_id = str(fallback_channels[0].get("id", ""))
                    print(f"🔄 Używam fallback kanału: {fallback_id}")
                    return fallback_id
            except:
                pass

            # Ostatnia deska ratunku - zwróć pusty string
            if import_id:
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "CHANNEL_TYPE_MAPPING_FAILED",
                    f"Nie udało się dopasować ani utworzyć kanału dla typu '{channel_type_string}': {e}",
                    channel_type_string
                )

            return ""


    def is_uuid(value: str) -> bool:
        try:
            uuid.UUID(value)
            return True
        except (ValueError, TypeError):
            return False

    def _find_registered_data_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje RegisteredData w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            query_filter = {
                "external_id": source_id
            }

            registered_data = self.mongo_api_service.get_documents(
                collection_name=Collections.REGISTERED_DATA.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if registered_data and len(registered_data) > 0:
                return str(registered_data[0].get("id", ""))
            return ""

        except Exception as e:
            print(f"❌ Error finding RegisteredData by source_id {source_id}: {e}")
            return ""

    def _find_channel_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Channel w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            query_filter = {
                "external_id": source_id
            }

            channels = self.mongo_api_service.get_documents(
                collection_name=Collections.CHANNEL.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if channels and len(channels) > 0:
                return str(channels[0].get("id", ""))
            return ""

        except Exception as e:
            print(f"❌ Error finding Channel by source_id {source_id}: {e}")
            return ""

    # def _find_activity_execution_document_by_source_id(self, source_id: str, dataset_id: str) -> dict:
    #     """
    #     Znajduje pełny dokument ActivityExecution w MongoDB po source_id
    #     """
    #     try:
    #         query_filter = {
    #             "additional_properties": {
    #                 "$elemMatch": {
    #                     "key": "source_entity_ref",
    #                     "value": f":{source_id}"
    #                 }
    #             }
    #         }
    #
    #         activity_executions = self.mongo_api_service.get_documents(
    #             collection_name=Collections.ACTIVITY_EXECUTION.value,
    #             dataset_id=dataset_id,
    #             query=query_filter
    #         )
    #
    #         if activity_executions and len(activity_executions) > 0:
    #             return activity_executions[0]
    #         return {}
    #
    #     except Exception as e:
    #         print(f"❌ Error finding ActivityExecution document by source_id {source_id}: {e}")
    #         return {}

    def _find_participant_state_document_by_source_id(self, source_id: str, dataset_id: str) -> dict:
        """
        Znajduje pełny dokument ParticipantState w MongoDB po source_id
        """
        try:
            query_filter = {
                "additional_properties": {
                    "$elemMatch": {
                        "key": "source_entity_ref",
                        "value": f":{source_id}"
                    }
                }
            }

            participant_states = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT_STATE.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if participant_states and len(participant_states) > 0:
                return participant_states[0]
            return {}

        except Exception as e:
            print(f"❌ Error finding ParticipantState document by source_id {source_id}: {e}")
            return {}

    def _process_participations_from_json(self, json_data: Dict[str, Any], dataset_id: str, import_id: str,
                                          processed_ids: Set[str]) -> int:
        """
        Wyszukuje i przetwarza wszystkie encje Participation z zagnieżdżonych struktur JSON.
        Participation nie jest zwykle na głównym poziomie JSON, ale zagnieżdżone w innych encjach.
        """
        participations_found = []

        def extract_participations_recursive(data, path=""):
            """Rekurencyjnie szuka Participation w zagnieżdżonych strukturach"""
            if isinstance(data, dict):
                # Sprawdź czy to Participation
                if "@id" in data and "rdf:type" in data:
                    rdf_types = data.get("rdf:type", [])
                    if not isinstance(rdf_types, list):
                        rdf_types = [rdf_types]

                    for type_info in rdf_types:
                        type_id = type_info.get("@id", "") if isinstance(type_info, dict) else str(type_info)
                        if "co:Participation" in type_id:
                            entity_id = data.get("@id")
                            if entity_id and entity_id not in processed_ids:
                                participations_found.append(data)
                                print(f"🔍 Found Participation in path: {path} -> {entity_id}")
                            break

                # Rekurencyjnie przeszukaj wszystkie zagnieżdżone obiekty
                for key, value in data.items():
                    new_path = f"{path}.{key}" if path else key
                    extract_participations_recursive(value, new_path)

            elif isinstance(data, list):
                for i, item in enumerate(data):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    extract_participations_recursive(item, new_path)

        print(f"🔍 Searching for Participation entities in JSON structure...")
        extract_participations_recursive(json_data)

        if not participations_found:
            print("ℹ️ No Participation entities found in nested structures")
            return 0

        print(f"📊 Found {len(participations_found)} Participation entities to process")

        # Przetwarzaj znalezione Participation
        processed_count = 0
        for participation_data in participations_found:
            entity_id = participation_data.get("@id", "unknown_participation")

            try:
                print(f"🤝 Processing Participation: {entity_id}")

                # Konwertuj na GRISERA object
                grisera_object = self._convert_json_to_grisera_object(
                    participation_data,
                    "Participation",
                    dataset_id,
                    import_id
                )

                if grisera_object:
                    saved_id = self._save_with_grisera_service(grisera_object, "Participation", dataset_id, import_id)
                    if saved_id:
                        processed_ids.add(entity_id)
                        processed_count += 1
                        print(f"✅ Participation saved: {entity_id} -> MongoDB ID: {saved_id}")
                    else:
                        print(f"❌ Failed to save Participation: {entity_id}")
                else:
                    print(f"❌ Failed to convert Participation to GRISERA object: {entity_id}")

            except Exception as e:
                print(f"❌ Error processing Participation {entity_id}: {str(e)}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "PARTICIPATION_PROCESSING_ERROR",
                    f"Error processing Participation: {str(e)}",
                    entity_id
                )

        return processed_count

    def _save_measure_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje Measure z mapowaniem measure_name_id z source ID na MongoDB ID.
        """
        try:
            print(f"💾 Saving Measure with measure_name_id mapping...")

            # KROK 1: Mapuj measure_name_id z source ID na MongoDB ID
            mapped_measure_name_id = grisera_object.measure_name_id
            measure_name_source_id = str(grisera_object.measure_name_id)
            measure_name_mongo_id = self._find_measure_name_by_source_id(measure_name_source_id, dataset_id)

            if measure_name_mongo_id:
                mapped_measure_name_id = measure_name_mongo_id
                print(f"✅ Mapped measure_name_id: {grisera_object.measure_name_id} -> {measure_name_mongo_id}")
            else:
                # print(f"❌ Could not find MeasureName in MongoDB for source ID: {measure_name_source_id}")
                # self._log_import_error(
                #         import_id,
                #         dataset_id,
                #         "MEASURE_NAME_NOT_FOUND_FOR_MEASURE",
                #         f"MeasureName with source ID '{measure_name_source_id}' not found for Measure",
                #         str(grisera_object.measure_name_id)
                #     )
                # mapped_measure_name_id = None
                measure_name_mongo_id = self._find_or_create_measure_name_by_name(
                    measure_name_source_id, dataset_id, import_id
                )

                if measure_name_mongo_id:
                    mapped_measure_name_id = measure_name_mongo_id
                    print(f"✅ Found/created MeasureName by name: {measure_name_source_id} -> {measure_name_mongo_id}")
                else:
                    print(f"❌ Could not find or create MeasureName for: {measure_name_source_id}")
                    print(f"❌ Cannot save Measure without valid measure_name_id")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "MEASURE_NAME_REQUIRED",
                        f"Cannot save Measure without valid measure_name_id",
                        str(grisera_object.measure_name_id)
                    )
                    return None

            grisera_object.measure_name_id = mapped_measure_name_id


            # KROK 3: Zapisz Measure używając serwisu
            print(f"✅ Measure being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_measure_service().save_measure(grisera_object, dataset_id)
            saved_measure_id = str(getattr(result, 'id', 'unknown'))
            print(f"✅ Measure saved with MongoDB ID: {saved_measure_id}")

            # KROK 4: Loguj mapowanie dla debugowania
            if mapped_measure_name_id != grisera_object.measure_name_id:
                print(f"🔗 Final measure_name_id mapping: {grisera_object.measure_name_id} -> {mapped_measure_name_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving Measure with mapping: {e}")
            raise e

    def _find_or_create_measure_name_by_name(self, measure_name_source_id: str, dataset_id: str, import_id: str) -> str:
        """
        Znajduje MeasureName po nazwie (case-insensitive) lub tworzy nowy.

        Args:
            measure_name_source_id: ID z JSON (np. "fear", "http://...#fear")
            dataset_id: ID datasetu
            import_id: ID procesu importu

        Returns:
            MongoDB ID dla MeasureName lub None jeśli nie udało się utworzyć
        """
        try:
            # Wyciągnij czystą nazwę z różnych formatów
            clean_name = self._extract_clean_measure_name(measure_name_source_id)
            print(
                f"🔍 Searching for MeasureName with clean name: '{clean_name}' (from source: '{measure_name_source_id}')")

            # 1. Najpierw sprawdź czy istnieje MeasureName z podobną nazwą (case-insensitive)
            existing_measure_name_id = self._find_existing_measure_name_by_name(clean_name, dataset_id)
            if existing_measure_name_id:
                # Zaktualizuj external_id w istniejącym MeasureName
                self._update_measure_name_external_id(existing_measure_name_id, measure_name_source_id, dataset_id)
                return existing_measure_name_id

            # 2. Jeśli nie znaleziono, utwórz nowy MeasureName
            print(f"📝 Creating new MeasureName for: '{clean_name}'")
            return self._create_new_measure_name_and_measure(clean_name, measure_name_source_id, dataset_id, import_id)

        except Exception as e:
            print(f"❌ Error in _find_or_create_measure_name_by_name: {e}")
            return ""

    def _extract_clean_measure_name(self, source_id: str) -> str:
        """
        Wyciąga czystą nazwę measure z różnych formatów source_id.

        Przykłady:
        - "fear" -> "fear"
        - "http://www.semanticweb.org/GRISERA/contextualOntology/models/emotionalMeasures/ekman#fear" -> "fear"
        - "ekman:fear" -> "fear"
        """
        if not source_id:
            return "unknown"

        # Usuń prefix ":"
        clean_id = source_id.replace(":", "") if source_id.startswith(":") else source_id

        # Jeśli to URL, wyciągnij część po ostatnim # lub /
        if "http" in clean_id or "/" in clean_id:
            if "#" in clean_id:
                clean_id = clean_id.split("#")[-1]
            elif "/" in clean_id:
                clean_id = clean_id.split("/")[-1]

        # Usuń namespace prefixes (np. "ekman:fear" -> "fear")
        if ":" in clean_id:
            clean_id = clean_id.split(":")[-1]

        return clean_id.strip().lower()

    def _find_existing_measure_name_by_name(self, clean_name: str, dataset_id: str) -> str:
        """
        Znajduje istniejący MeasureName po nazwie (case-insensitive, zawieranie).
        """
        try:
            # Sprawdź czy nazwa jest zawarta w istniejących measure_names
            query_filter = {
                "name": {"$regex": f".*{clean_name}.*", "$options": "i"}
            }

            measure_names = self.mongo_api_service.get_documents(
                collection_name=Collections.MEASURE_NAME.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if measure_names and len(measure_names) > 0:
                # Preferuj dokładne dopasowanie
                for mn in measure_names:
                    if mn.get("name", "").lower() == clean_name:
                        print(f"✅ Found exact match for '{clean_name}': {mn.get('name')} (ID: {mn.get('id')})")
                        return str(mn.get("id", ""))

                # Jeśli nie ma dokładnego, weź pierwszy częściowy
                first_match = measure_names[0]
                print(
                    f"✅ Found partial match for '{clean_name}': {first_match.get('name')} (ID: {first_match.get('id')})")
                return str(first_match.get("id", ""))

            return ""

        except Exception as e:
            print(f"❌ Error finding existing MeasureName by name: {e}")
            return ""

    def _update_measure_name_external_id(self, measure_name_id: str, external_id: str, dataset_id: str):
        """
        Aktualizuje external_id w istniejącym MeasureName jeśli jest pusty.
        """
        try:
            measure_name_doc = self.mongo_api_service.get_document(
                measure_name_id,
                Collections.MEASURE_NAME.value,
                dataset_id
            )

            if measure_name_doc and not measure_name_doc.get("external_id"):
                measure_name_doc["external_id"] = f":{external_id}"

                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.MEASURE_NAME.value,
                    id=measure_name_id,
                    new_document=measure_name_doc,
                    dataset_id=dataset_id
                )
                print(f"🔗 Updated MeasureName {measure_name_id} with external_id: :{external_id}")

        except Exception as e:
            print(f"❌ Error updating MeasureName external_id: {e}")

    def _create_new_measure_name_and_measure(self, clean_name: str, source_id: str, dataset_id: str,
                                             import_id: str) -> str:
        """
        Tworzy nowy MeasureName i odpowiadający mu domyślny Measure.

        Returns:
            MongoDB ID nowego MeasureName
        """
        try:
            # 1. Utwórz MeasureName
            from grisera import MeasureNameIn, PropertyIn

            measure_name_in = MeasureNameIn(
                name=clean_name.title(),  # Kapitalizuj pierwszą literę
                type="User defined",
                external_id=f":{source_id}",
                import_job_id=import_id,
                additional_properties=[
                    PropertyIn(key="auto_created", value="true"),
                    PropertyIn(key="source_id", value=source_id),
                    PropertyIn(key="import_job_id", value=import_id)
                ]
            )

            measure_name_service = self.services.get_measure_name_service()
            measure_name_result = measure_name_service.save_measure_name(measure_name_in, dataset_id)

            if hasattr(measure_name_result, 'errors') and measure_name_result.errors:
                print(f"❌ Error creating MeasureName: {measure_name_result.errors}")
                return ""

            measure_name_id = str(measure_name_result.id)
            print(f"✅ Created new MeasureName: '{clean_name}' with ID: {measure_name_id}")

            # 2. Utwórz domyślny Measure dla tego MeasureName
            self._create_default_measure_for_measure_name(measure_name_id, source_id, dataset_id, import_id)

            return measure_name_id

        except Exception as e:
            print(f"❌ Error creating new MeasureName and Measure: {e}")
            return ""

    def _create_default_measure_for_measure_name(self, measure_name_id: str, source_id: str, dataset_id: str,
                                                 import_id: str):
        """
        Tworzy domyślny Measure dla nowo utworzonego MeasureName.
        """
        try:
            from grisera import MeasureIn, PropertyIn

            default_measure_in = MeasureIn(
                datatype="float",
                range="0-1",
                unit="normalized",
                measure_name_id=measure_name_id,
                external_id=source_id,
                import_job_id=import_id,
                additional_properties=[
                    PropertyIn(key="auto_created", value="true"),
                    PropertyIn(key="measure_name_id", value=measure_name_id),
                    PropertyIn(key="import_job_id", value=import_id)
                ]
            )

            measure_service = self.services.get_measure_service()
            measure_result = measure_service.save_measure(default_measure_in, dataset_id)

            if hasattr(measure_result, 'errors') and measure_result.errors:
                print(f"❌ Error creating default Measure: {measure_result.errors}")
            else:
                measure_id = str(measure_result.id)
                print(f"✅ Created default Measure with ID: {measure_id} for MeasureName: {measure_name_id}")

        except Exception as e:
            print(f"❌ Error creating default Measure: {e}")


    def _find_measure_name_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje MeasureName w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            query_filter = {
                "external_id": source_id,
            }

            measure_names = self.mongo_api_service.get_documents(
                collection_name=Collections.MEASURE_NAME.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if measure_names and len(measure_names) > 0:
                return str(measure_names[0].get("id", ""))
            return ""

        except Exception as e:
            print(f"❌ Error finding MeasureName by source_id {source_id}: {e}")
            return ""

    def _save_participant_state_with_participant_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje ParticipantState z mapowaniem participant_id z source ID na MongoDB ID.
        """
        try:
            print(f"💾 Saving ParticipantState with participant mapping...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                print("⚠️ No source_entity_ref found in ParticipantState")
            else:
                print(f"🔍 ParticipantState source ID: {source_entity_ref}")

            # KROK 2: Mapuj participant_id z source ID na MongoDB ID
            mapped_participant_id = grisera_object.participant_id
            if grisera_object.participant_id and str(grisera_object.participant_id).startswith(":"):
                # To jest source ID, mapuj na MongoDB ID
                participant_source_id = str(grisera_object.participant_id).replace(":", "")
                participant_mongo_id = self._find_participant_by_source_id(participant_source_id, dataset_id)

                if participant_mongo_id:
                    mapped_participant_id = participant_mongo_id
                    print(f"✅ Mapped participant_id: {grisera_object.participant_id} -> {mapped_participant_id}")
                else:
                    print(f"❌ Could not find Participant in MongoDB for source ID: {participant_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "PARTICIPANT_NOT_FOUND_FOR_PARTICIPANT_STATE",
                        f"Participant with source ID '{participant_source_id}' not found for ParticipantState",
                        source_entity_ref or "unknown"
                    )
                    # Nie możemy zapisać ParticipantState bez participant_id
                    return None

            if not mapped_participant_id:
                print(f"❌ ParticipantState - Missing participant_id after mapping")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "PARTICIPANT_STATE_MISSING_PARTICIPANT_ID",
                    f"ParticipantState missing participant_id after mapping",
                    source_entity_ref or "unknown"
                )
                return None

            # KROK 3: Utwórz nowy ParticipantStateIn z poprawnym participant_id
            from grisera import ParticipantStateIn
            mapped_participant_state = ParticipantStateIn(
                participant_id=mapped_participant_id,
                personality_ids=grisera_object.personality_ids,
                appearance_ids=grisera_object.appearance_ids,
                age=grisera_object.age,
                external_id=grisera_object.external_id,
                import_job_id=import_id,
                # external_id=grisera_object.external_id,
                additional_properties=grisera_object.additional_properties
            )
            # KROK 4: Użyj participant_service do zapisania ParticipantState (embedded w Participant)
            print(f"✅ ParticipantState being saved with final data: {mapped_participant_state.__dict__}")
            result = self.services.get_participant_service().add_participant_state(mapped_participant_state, dataset_id)
            saved_participant_state_id = str(getattr(result, 'id', 'unknown'))

            print(f"✅ ParticipantState saved successfully with MongoDB ID: {saved_participant_state_id}")
            print(f"🔗 Final participant_id mapping: {grisera_object.participant_id} -> {mapped_participant_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving ParticipantState with participant mapping: {e}")
            self._log_import_error(
                import_id,
                dataset_id,
                "PARTICIPANT_STATE_SAVE_ERROR",
                f"Error saving ParticipantState with participant mapping: {str(e)}",
                source_entity_ref or "unknown"
            )
            raise e

    def _save_observable_information_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje ObservableInformation z mapowaniem source IDs na MongoDB IDs.
        ObservableInformation jest zapisywane jako część Recording (embedded document).
        """
        try:
            source_entity_ref = grisera_object.external_id
            print(f"🔍 ObservableInformation source ID: {source_entity_ref}")

            # 1. Mapuj modality_id (opcjonalne)
            mapped_modality_id = None
            if grisera_object.modality_id:
                modality_source_id = str(grisera_object.modality_id)
                print(f"🔍 Looking for Modality with source ID: {modality_source_id}")
                modality_mongo_id = self._find_modality_by_source_id(modality_source_id, dataset_id)

                if modality_mongo_id:
                    mapped_modality_id = modality_mongo_id
                    print(f"🔗 Mapped modality_id: {grisera_object.modality_id} -> {mapped_modality_id}")
                else:
                    print(f"❌ Could not find Modality in MongoDB for source ID: {modality_source_id}")

            # 2. Mapuj life_activity_id (opcjonalne)
            mapped_life_activity_id = None
            if grisera_object.life_activity_id:
                life_activity_source_id = str(grisera_object.life_activity_id)
                print(f"🔍 Looking for LifeActivity with source ID: {life_activity_source_id}")
                life_activity_mongo_id = self._find_life_activity_by_source_id(life_activity_source_id, dataset_id)

                if life_activity_mongo_id:
                    mapped_life_activity_id = life_activity_mongo_id
                    print(f"🔗 Mapped life_activity_id: {grisera_object.life_activity_id} -> {mapped_life_activity_id}")
                else:
                    print(f"❌ Could not find LifeActivity in MongoDB for source ID: {life_activity_source_id}")

            mapped_recording_id = None
            if grisera_object.recording_id:
                recording_source_id = str(grisera_object.recording_id)
                print(f"🔍 Looking for Recording with source ID: {recording_source_id}")

                # Znajdź Recording po external_id
                recording_mongo_id = self._find_recording_by_source_id(recording_source_id, dataset_id)

                if recording_mongo_id:
                    mapped_recording_id = recording_mongo_id
                    print(f"🔗 Mapped recording_id: {grisera_object.recording_id} -> {mapped_recording_id}")
                else:
                    print(f"❌ Could not find Recording in MongoDB for source ID: {recording_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "RECORDING_NOT_FOUND_FOR_OBSERVABLE_INFO",
                        f"Recording with source ID '{recording_source_id}' not found for ObservableInformation",
                        source_entity_ref or "unknown"
                    )
                    return None

            # Jeśli nie mamy recording_id, nie możemy zapisać
            if not mapped_recording_id:
                print(f"❌ Cannot save ObservableInformation without valid recording_id")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "RECORDING_ID_REQUIRED_FOR_OBSERVABLE_INFO",
                    f"Cannot save ObservableInformation without valid recording_id",
                    source_entity_ref or "unknown"
                )
                return None

            # 4. Utwórz nowy ObservableInformationIn z zmapowanymi ID
            from grisera import ObservableInformationIn
            mapped_observable_info = ObservableInformationIn(
                modality_id=mapped_modality_id,
                life_activity_id=mapped_life_activity_id,
                recording_id=mapped_recording_id,
                external_id=source_entity_ref,
                import_job_id=import_id
            )

            # 5. Zapisz przez ObservableInformationService
            print(f"✅ ObservableInformation being saved with mapped data: {mapped_observable_info.__dict__}")
            result = self.services.get_observable_information_service().save_observable_information(mapped_observable_info, dataset_id)

            # Sprawdź czy nie ma błędów
            if hasattr(result, 'errors') and result.errors:
                print(f"❌ Error saving ObservableInformation: {result.errors}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "OBSERVABLE_INFO_SAVE_ERROR",
                    f"Error saving ObservableInformation: {result.errors}",
                    source_entity_ref or "unknown"
                )
                return None

            saved_observable_info_id = str(getattr(result, 'id', 'unknown'))

            print(f"🔗 Final ObservableInformation mappings:")
            print(f"   modality_id: {grisera_object.modality_id} -> {mapped_modality_id}")
            print(f"   life_activity_id: {grisera_object.life_activity_id} -> {mapped_life_activity_id}")
            print(f"   recording_id: {grisera_object.recording_id} -> {mapped_recording_id}")
            print(f"   ObservableInformation saved with ID: {saved_observable_info_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving ObservableInformation with mapping: {e}")
            raise e

    def _find_modality_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Modality w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            query_filters = [
                {"external_id": source_id},
            ]

            for query_filter in query_filters:
                modalities = self.mongo_api_service.get_documents(
                    collection_name=Collections.MODALITY.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if modalities and len(modalities) > 0:
                    return str(modalities[0].get("id", ""))

            return ""

        except Exception as e:
            print(f"❌ Error finding Modality by source_id {source_id}: {e}")
            return ""

    def _find_life_activity_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje LifeActivity w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            # Sprawdź zarówno dokładny external_id jak i bez prefiksu
            query_filters = [
                {"external_id": source_id},
                {"external_id": f":{source_id}"}
            ]

            for query_filter in query_filters:
                life_activities = self.mongo_api_service.get_documents(
                    collection_name=Collections.LIFE_ACTIVITY.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if life_activities and len(life_activities) > 0:
                    return str(life_activities[0].get("id", ""))

            return ""

        except Exception as e:
            print(f"❌ Error finding LifeActivity by source_id {source_id}: {e}")
            return ""

    def _find_recording_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Recording w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            # Sprawdź zarówno dokładny external_id jak i bez prefiksu
            query_filters = [
                {"external_id": source_id},
            ]

            for query_filter in query_filters:
                recordings = self.mongo_api_service.get_documents(
                    collection_name=Collections.RECORDING.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if recordings and len(recordings) > 0:
                    found_id = str(recordings[0].get("id", ""))
                    print(f"✅ Found Recording: {source_id} -> MongoDB ID: {found_id}")
                    return found_id

            print(f"❌ Recording not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding Recording by source_id {source_id}: {e}")
            return ""

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
                measure_mongo_id = self._find_measure_by_source_id(measure_source_id, dataset_id)

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
                obs_info_mongo_id = self._find_observable_information_by_source_id(obs_info_source_id, dataset_id)

                if obs_info_mongo_id:
                    mapped_observable_information_id = obs_info_mongo_id
                    print(f"🔗 Mapped observable_information_id: {grisera_object.observable_information_id} -> {mapped_observable_information_id}")
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
                    obs_mongo_id = self._find_observable_information_by_source_id(obs_source_id, dataset_id)
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
            print(f"   observable_information_id: {grisera_object.observable_information_id} -> {mapped_observable_information_id}")
            print(f"   observable_information_ids: {grisera_object.observable_information_ids} -> {mapped_observable_information_ids}")
            print(f"   TimeSeries saved with ID: {saved_time_series_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving TimeSeries with mapping: {e}")
            raise e

    def _find_observable_information_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ObservableInformation w MongoDB po source_id.
        Szuka w embedded liście observable_informations w Recording.
        """
        try:
            print(f"🔍 Searching for ObservableInformation with external_id: {source_id}")

            # Zapytanie MongoDB - szukaj Recording które mają ObservableInformation z danym external_id
            query_filter = {
                "observable_informations": {
                    "$elemMatch": {
                        "external_id": source_id
                    }
                }
            }

            recordings = self.mongo_api_service.get_documents(
                collection_name=Collections.RECORDING.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if recordings and len(recordings) > 0:
                recording = recordings[0]
                observable_informations = recording.get("observable_informations", [])

                # Znajdź konkretny ObservableInformation w liście
                for obs_info in observable_informations:
                    if obs_info.get("external_id") == source_id:
                        found_id = str(obs_info.get("id", ""))
                        print(f"✅ Found ObservableInformation: {source_id} -> MongoDB ID: {found_id}")
                        return found_id

            print(f"❌ ObservableInformation not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding ObservableInformation by source_id {source_id}: {e}")
            return ""

    def _find_measure_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Measure w MongoDB po source_id i zwraca jego MongoDB ID
        """
        try:
            # Sprawdź zarówno dokładny external_id jak i bez prefiksu
            query_filters = [
                {"external_id": source_id}
            ]

            for query_filter in query_filters:
                measures = self.mongo_api_service.get_documents(
                    collection_name=Collections.MEASURE.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if measures and len(measures) > 0:
                    found_id = str(measures[0].get("id", ""))
                    print(f"✅ Found Measure: {source_id} -> MongoDB ID: {found_id}")
                    return found_id

            print(f"❌ Measure not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding Measure by source_id {source_id}: {e}")
            return ""
