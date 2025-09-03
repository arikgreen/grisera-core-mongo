from typing import Union, List, Dict, Any, Set
import json
from datetime import datetime

from data_operations.utils import decode_file_content, remove_prefix
from data_operations.converters import ENTITY_CONVERTERS, BaseEntityConverter
from data_operations.entity_type_mapping import EntityTypeMapping
from data_operations.file_operations_model import FileOperationIn

from mongo_service.mongo_api_service import MongoApiService
from mongo_service.collection_mapping import Collections

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
    RegisteredChannelIn,
    ObservableInformationIn
)

from data_operations.file_operations_service import FileOperationsStatusService
from data_operations.scenario_builder import ExperimentScenariosBuilder

DEBUG = True

class JsonImportService:
    """
    Serwis dedykowany do importu danych JSON ontologicznych.
    """

    def __init__(self):
        self.mongo_api_service = MongoApiService()
        self.services = MongoServiceFactory()
        self.file_ops_service = FileOperationsStatusService()
        
        self.experiment_scenarios_builder = ExperimentScenariosBuilder(
            self.mongo_api_service, 
            self.services, 
            self.file_ops_service
        )

        print("🔧 JsonImportService initialized with ExperimentScenariosBuilder")

    def import_json_data(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Importuje dane JSON zgodnie z instrukcją ontologiczną
        Returns: liczba zaimportowanych rekordów
        """
        print(f"📄 Starting JSON data import for import ID: {import_id}")
        processed_ids: Set[str] = set()
        total_imported = 0

        try:
            print("🔓 Decoding file content using utils...")
            decoded_content = decode_file_content(import_data.file_content)
            print(f"📏 File content size: {len(decoded_content)} characters")

            json_data = json.loads(decoded_content)

            if not isinstance(json_data, dict):
                error_msg = "Expected JSON object at root level"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)

            experiment_id = self._handle_experiment_creation(import_data, json_data, import_id)
            if experiment_id:
                print(f"🧪 Using experiment ID: {experiment_id}")
                if not import_data.experiment_id:
                    import_data.experiment_id = experiment_id

            # Count total TimeSeries for progress tracking
            total_time_series = 0
            for json_key in json_data.keys():
                normalized_key = remove_prefix(json_key)
                if normalized_key == "TimeSeries" and isinstance(json_data[json_key], list):
                    total_time_series = len(json_data[json_key])
                    break
            
            if total_time_series > 0:
                self.file_ops_service.set_total_count(import_id, import_data.dataset_id, "total_time_series", total_time_series)
                print(f"📊 Total TimeSeries to import: {total_time_series}")

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
                            processed_ids
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

            print(f"✅ JSON import completed! Total imported: {total_imported} entities")
            print(f"🧠 Processed unique IDs: {len(processed_ids)}")

            print("🎬 Building scenarios based on experiments and ActivityExecution...")
            scenarios_count = self.experiment_scenarios_builder.build_experiment_scenarios(import_data, import_id)
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
            processed_ids: Set[str]
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
                grisera_object = self._save_json_as_grisera_object(
                    entity,
                    entity_type,
                    dataset_id,
                    import_id
                )
                imported_count += 1

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

    def _save_json_as_grisera_object(
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
            grisera_object = converter.save(json_entity, dataset_id, import_id)

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

    @staticmethod
    def _get_entity_type_from_collection(collection_name: str) -> str:
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

    def _handle_experiment_creation(self, import_data: FileOperationIn, json_data: Dict[str, Any],
                                    import_id: str) -> str:
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
        experiment_from_json = self._find_and_import_experiment_from_json(json_data, import_data.dataset_id,
                                                                          import_id)
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

    def _find_and_import_experiment_from_json(self, json_data: Dict[str, Any], dataset_id: str,
                                              import_id: str) -> str:
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
