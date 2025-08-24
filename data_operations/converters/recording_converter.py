from typing import Dict, Any, Optional
from grisera import RecordingIn, PropertyIn
from .base import BaseEntityConverter, DEBUG
from .registered_channel_converter import RegisteredChannelConverter
from .participation_converter import ParticipationConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class RecordingConverter(BaseEntityConverter[RecordingIn]):
    JSON_KEY_CANDIDATES_FOR_PARTICIPATION_ID = ["hasParticipation", "participation_id"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_REGISTERED_CHANNEL_ID = ["hasRegisteredChannel", "registered_channel_id"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Recording"
    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.registered_channel_service = RegisteredChannelConverter(import_id)
        self.participation_service = ParticipationConverter(import_id)
        self.services = MongoServiceFactory()

    def convert(self, json_entity: Dict[str, Any]) -> RecordingIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij Participation ID z JSON - może być zagnieżdżony obiekt
        participation_id = self._extract_participation_id_from_json(json_entity)
        
        # Wyciągnij RegisteredChannel ID z JSON - może być zagnieżdżony obiekt  
        registered_channel_id = self._extract_registered_channel_id_from_json(json_entity)
        
        recording = RecordingIn(
            participation_id=participation_id,
            registered_channel_id=registered_channel_id
        )

        additional_properties = self._set_common_properties(json_entity, recording)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_PARTICIPATION_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_REGISTERED_CHANNEL_ID)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        if DEBUG:
            print(f"📝 Creating RecordingIn: name='{clean_name_for_log}', participation_id='{participation_id}', registered_channel_id='{registered_channel_id}', external_id='{recording.external_id}', import_job_id='{recording.import_job_id}', properties={len(additional_properties)} (including common)")

        return recording
    
    def _extract_participation_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Participation ID z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_participation_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_PARTICIPATION_ID)
        if simple_participation_id:
            if DEBUG:
                print(f"✅ Found simple participation_id: {simple_participation_id}")
            return simple_participation_id
        
        # Następnie sprawdź co:hasParticipation (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_PARTICIPATION_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    participation_source_id = self._extract_nested_entity_id(entity_value)
                    if participation_source_id:
                        if DEBUG:
                            print(f"✅ Found Participation source ID from {entity_key_with_prefix}: {participation_source_id}")
                        # Zapisujemy source ID - mapowanie na MongoDB ID zostanie zrobione później
                        return participation_source_id
        
        if DEBUG:
            print("⚠️ No Participation reference found in Recording")
        return None
    
    def _extract_registered_channel_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga RegisteredChannel ID z JSON z zagnieżdżonej struktury hasRegisteredChannel.
        """
        # Najpierw sprawdź proste przypadki
        simple_rc_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_REGISTERED_CHANNEL_ID)
        if simple_rc_id:
            if DEBUG:
                print(f"✅ Found simple registered_channel_id: {simple_rc_id}")
            return simple_rc_id
        
        # Następnie sprawdź co:hasRegisteredChannel (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_REGISTERED_CHANNEL_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasRegisteredChannel - wyciągnij @id RegisteredChannel
                    registered_channel_id = self._extract_nested_entity_id(entity_value)
                    if registered_channel_id:
                        if DEBUG:
                            print(f"✅ Found RegisteredChannel ID from {entity_key_with_prefix}: {registered_channel_id}")
                        # Zapisujemy RegisteredChannel ID - mapowanie na MongoDB ID zostanie zrobione później
                        return registered_channel_id
        
        if DEBUG:
            print("⚠️ No RegisteredChannel reference found in Recording")
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> RecordingIn:
        """
        Konwertuje i zapisuje Recording.
        Na razie tylko konwertuje - faktyczne zapisywanie będzie w kolejnej iteracji.
        """
        return self._save_recording_with_mapping(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.RECORDING)


    def _save_recording_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje Recording z mapowaniem source IDs na MongoDB IDs dla participation_id i registered_channel_id.
        """
        try:
            if DEBUG:
                print(f"💾 Saving Recording with ID mapping...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                if DEBUG:
                    print("⚠️ No source_entity_ref found in Recording")
            else:
                if DEBUG:
                    print(f"🔍 Recording source ID: {source_entity_ref}")

            # KROK 2: Mapuj participation_id z source ID na MongoDB ID
            mapped_participation_id = grisera_object.participation_id
            additional_properties = list(
                grisera_object.additional_properties) if grisera_object.additional_properties else []
            participation_source_id = grisera_object.participation_id
            participation_mongo_id = self.participation_service.find_by_source_id(participation_source_id, dataset_id)

            if participation_mongo_id:
                mapped_participation_id = participation_mongo_id
                if DEBUG:
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

            if DEBUG:
                print(f"🔍 Looking fot RegisteredChannel in MongoDB for source ID: {grisera_object.registered_channel_id}")

            # KROK 3: Mapuj registered_channel_id z source ID na MongoDB ID
            registered_channel_source_id = grisera_object.registered_channel_id
            registered_channel_mongo_id = self.registered_channel_service.find_by_source_id(registered_channel_source_id,
                                                                                     dataset_id)

            if registered_channel_mongo_id:
                mapped_registered_channel_id = registered_channel_mongo_id
                if DEBUG:
                    print(
                        f"✅ Mapped registered_channel_id: {grisera_object.registered_channel_id} -> {registered_channel_mongo_id}")
            else:
                print(
                    f"❌ Could not find RegisteredChannel in MongoDB for source ID: {registered_channel_source_id}")
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
                if DEBUG:
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
            if DEBUG:
                print(f"✅ Recording being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_recording_service().save_recording(grisera_object, dataset_id)
            saved_recording_id = str(getattr(result, 'id', 'unknown'))
            if DEBUG:
                print(f"✅ Recording saved with ID: {saved_recording_id}")

            # KROK 6: Loguj mapowanie dla debugowania
            if DEBUG:
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