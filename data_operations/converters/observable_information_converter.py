from typing import Dict, Any, Optional
from grisera import ObservableInformationIn
from .base import BaseEntityConverter, DEBUG
from .modality_converter import ModalityConverter
from .life_activity_converter import LifeActivityConverter
from .recording_converter import RecordingConverter

from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class ObservableInformationConverter(BaseEntityConverter[ObservableInformationIn]):
    JSON_KEY_CANDIDATES_FOR_MODALITY_ID = ["hasModality", "modality_id"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_LIFE_ACTIVITY_ID = ["hasLifeActivity", "life_activity_id"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_RECORDING_ID = ["hasRecording", "recording_id"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "ObservableInformation"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.modality_service = ModalityConverter(import_id)
        self.life_activity_service = LifeActivityConverter(import_id)
        self.recording_service = RecordingConverter(import_id)
        self.services = MongoServiceFactory()

    def convert(self, json_entity: Dict[str, Any]) -> ObservableInformationIn:
        external_id = self._get_external_id(json_entity)

        modality_id = self._extract_modality_id_from_json(json_entity)
        
        life_activity_id = self._extract_life_activity_id_from_json(json_entity)
        
        recording_id = self._extract_recording_id_from_json(json_entity)
        
        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        if DEBUG:
            print(f"📝 Creating ObservableInformationIn: name='{clean_name_for_log}', modality_id='{modality_id}', life_activity_id='{life_activity_id}', recording_id='{recording_id}', external_id='{external_id}'")
        
        observable_information = ObservableInformationIn(
            modality_id=modality_id,
            life_activity_id=life_activity_id,
            recording_id=recording_id,
            # external_id=external_id
        )
        additional_properties = self._set_common_properties(json_entity, observable_information)
        return observable_information

    def _extract_modality_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Modality ID z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_modality_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_MODALITY_ID)
        if simple_modality_id:
            if DEBUG:
                print(f"✅ Found simple modality_id: {simple_modality_id}")
            return simple_modality_id
        
        # Następnie sprawdź co:hasModality (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_MODALITY_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    modality_source_id = self._extract_nested_entity_id(entity_value)
                    if modality_source_id:
                        if DEBUG:
                            print(f"✅ Found Modality source ID from {entity_key_with_prefix}: {modality_source_id}")
                        # Zapisujemy source ID - mapowanie na MongoDB ID zostanie zrobione później
                        return modality_source_id
        
        if DEBUG:
            print("⚠️ No Modality reference found in ObservableInformation")
        return None
    
    def _extract_life_activity_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga LifeActivity ID z JSON z zagnieżdżonej struktury hasLifeActivity.
        """
        # Najpierw sprawdź proste przypadki
        simple_la_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_LIFE_ACTIVITY_ID)
        if simple_la_id:
            if DEBUG:
                print(f"✅ Found simple life_activity_id: {simple_la_id}")
            return simple_la_id
        
        # Następnie sprawdź co:hasLifeActivity (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_LIFE_ACTIVITY_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasLifeActivity - wyciągnij @id LifeActivity
                    life_activity_id = self._extract_nested_entity_id(entity_value)
                    if life_activity_id:
                        if DEBUG:
                            print(f"✅ Found LifeActivity ID from {entity_key_with_prefix}: {life_activity_id}")
                        # Zapisujemy LifeActivity ID - mapowanie na MongoDB ID zostanie zrobione później
                        return life_activity_id
        
        if DEBUG:
            print("⚠️ No LifeActivity reference found in ObservableInformation")
        return None
    
    def _extract_recording_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Recording ID z JSON z zagnieżdżonej struktury hasRecording.
        """
        # Najpierw sprawdź proste przypadki
        simple_recording_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_RECORDING_ID)
        if simple_recording_id:
            if DEBUG:
                print(f"✅ Found simple recording_id: {simple_recording_id}")
            return simple_recording_id
        
        # Następnie sprawdź co:hasRecording (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_RECORDING_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasRecording - wyciągnij @id Recording
                    recording_id = self._extract_nested_entity_id(entity_value)
                    if recording_id:
                        if DEBUG:
                            print(f"✅ Found Recording ID from {entity_key_with_prefix}: {recording_id}")
                        # Zapisujemy Recording ID - mapowanie na MongoDB ID zostanie zrobione później
                        return recording_id
        
        if DEBUG:
            print("⚠️ No Recording reference found in ObservableInformation")
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str):# -> ObservableInformationIn:
        return self._save_observable_information_with_mapping(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ObservableInformation w MongoDB po source_id.
        Szuka w embedded liście observable_informations w Recording.
        """
        try:
            if DEBUG:
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

                for obs_info in observable_informations:
                    if obs_info.get("external_id") == source_id:
                        found_id = str(obs_info.get("id", ""))
                        if DEBUG:
                            print(f"✅ Found ObservableInformation: {source_id} -> MongoDB ID: {found_id}")
                        return found_id

            print(f"❌ ObservableInformation not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding ObservableInformation by source_id {source_id}: {e}")
            return ""


    def _save_observable_information_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje ObservableInformation z mapowaniem source IDs na MongoDB IDs.
        ObservableInformation jest zapisywane jako część Recording (embedded document).
        """
        try:
            source_entity_ref = grisera_object.external_id
            if DEBUG:
                print(f"🔍 ObservableInformation source ID: {source_entity_ref}")

            # 1. Mapuj modality_id (opcjonalne)
            mapped_modality_id = None
            if grisera_object.modality_id:
                modality_source_id = str(grisera_object.modality_id)
                if DEBUG:
                    print(f"🔍 Looking for Modality with source ID: {modality_source_id}")
                modality_mongo_id = self.modality_service.find_by_source_id(modality_source_id, dataset_id)

                if modality_mongo_id:
                    mapped_modality_id = modality_mongo_id
                    if DEBUG:
                        print(f"🔗 Mapped modality_id: {grisera_object.modality_id} -> {mapped_modality_id}")
                else:
                    print(f"❌ Could not find Modality in MongoDB for source ID: {modality_source_id}")

            # 2. Mapuj life_activity_id (opcjonalne)
            mapped_life_activity_id = None
            if grisera_object.life_activity_id:
                life_activity_source_id = str(grisera_object.life_activity_id)
                if DEBUG:
                    print(f"🔍 Looking for LifeActivity with source ID: {life_activity_source_id}")
                life_activity_mongo_id = self.life_activity_service.find_by_source_id(life_activity_source_id, dataset_id)

                if life_activity_mongo_id:
                    mapped_life_activity_id = life_activity_mongo_id
                    if DEBUG:
                        print(
                            f"🔗 Mapped life_activity_id: {grisera_object.life_activity_id} -> {mapped_life_activity_id}")
                else:
                    print(f"❌ Could not find LifeActivity in MongoDB for source ID: {life_activity_source_id}")

            mapped_recording_id = None
            if grisera_object.recording_id:
                recording_source_id = str(grisera_object.recording_id)
                if DEBUG:
                    print(f"🔍 Looking for Recording with source ID: {recording_source_id}")

                recording_mongo_id = self.recording_service.find_by_source_id(recording_source_id, dataset_id)

                if recording_mongo_id:
                    mapped_recording_id = recording_mongo_id
                    if DEBUG:
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

            if DEBUG:
                print(f"✅ ObservableInformation being saved with mapped data: {mapped_observable_info.__dict__}")
            result = self.services.get_observable_information_service().save_observable_information(
                mapped_observable_info, dataset_id)

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

            return result

        except Exception as e:
            print(f"❌ Error saving ObservableInformation with mapping: {e}")
            raise e
