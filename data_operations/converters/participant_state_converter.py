from typing import Dict, Any, Optional, List
from grisera import ParticipantStateIn
from .base import BaseEntityConverter, DEBUG
from .participant_converter import ParticipantConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class ParticipantStateConverter(BaseEntityConverter["ParticipantStateIn"]):
    JSON_KEY_CANDIDATES_FOR_PARTICIPANT_ID = ["hasParticipant", "participant_id"]
    JSON_KEY_CANDIDATES_FOR_AGE = ["age", "hasAge"]
    JSON_KEY_CANDIDATES_FOR_PERSONALITY = ["hasPersonality", "personality_ids"]
    JSON_KEY_CANDIDATES_FOR_APPEARANCE = ["hasApperance", "hasAppearance", "appearance_ids"]  # Note: "hasApperance" jest w JSON (typo)
    DEFAULT_MAIN_FIELD_PREFIX = "ParticipantState"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.participant_service = ParticipantConverter(import_id)
        self.services = MongoServiceFactory()

    def convert(self, json_entity: Dict[str, Any]) -> "ParticipantStateIn":
        external_id = self._get_external_id(json_entity)
        
        # Wyciągnij participant_id z zagnieżdżonej struktury hasParticipant
        participant_id = self._extract_participant_id_from_json(json_entity)
        
        # Wyciągnij proste pola
        age = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_AGE)
        if age:
            try:
                age = int(age)
            except (ValueError, TypeError):
                age = None
        
        personality_ids = self._extract_related_ids(json_entity, self.JSON_KEY_CANDIDATES_FOR_PERSONALITY) ## EXTERNAL ID
        
        appearance_ids = self._extract_related_ids(json_entity, self.JSON_KEY_CANDIDATES_FOR_APPEARANCE) ## EXTERNAL ID
        
        participant_state = ParticipantStateIn(
            participant_id=participant_id,
            # personality_ids=personality_ids,
            # appearance_ids=appearance_ids,
            age=age
        )

        additional_properties = self._set_common_properties(json_entity, participant_state)

        # Wyklucz już przetworzone klucze
        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_PARTICIPANT_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_AGE)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_PERSONALITY)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_APPEARANCE)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"

        if DEBUG:
            print(f"📝 Creating ParticipantStateIn: name='{clean_name_for_log}', participant_id='{participant_id}', age={age}, external_id='{participant_state.external_id}', import_job_id='{participant_state.import_job_id}', properties={len(additional_properties)} (including common)")

        return participant_state
    
    def _extract_participant_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Participant ID z zagnieżdżonej struktury hasParticipant.
        """
        # Najpierw sprawdź proste przypadki
        simple_participant_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_PARTICIPANT_ID)
        if simple_participant_id:
            if DEBUG:
                print(f"✅ Found simple participant_id: {simple_participant_id}")
            return simple_participant_id
        
        # Następnie sprawdź co:hasParticipant (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_PARTICIPANT_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    participant_id = self._extract_nested_entity_id(entity_value)
                    if participant_id:
                        if DEBUG:
                            print(f"✅ Found Participant ID from {entity_key_with_prefix}: {participant_id}")
                        # Zapisujemy Participant ID - mapowanie na MongoDB ID zostanie zrobione później
                        return participant_id
        
        if DEBUG:
            print("⚠️ No Participant reference found in ParticipantState")
        return None
    
    def _extract_related_ids(self, json_entity: Dict[str, Any], key_candidates: List[str]) -> Optional[List[str]]:
        """
        Wyciąga listę powiązanych ID z zagnieżdżonych obiektów.
        """
        ids = []
        
        for clean_candidate_key in key_candidates:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    if isinstance(entity_value, list):
                        for item in entity_value:
                            if isinstance(item, dict) and "@id" in item:
                                ids.append(str(item["@id"]))
                    elif isinstance(entity_value, dict) and "@id" in entity_value:
                        ids.append(str(entity_value["@id"]))
        
        return ids if ids else None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> ParticipantStateIn:
        """
        Konwertuje i zapisuje ParticipantState.
        Na razie tylko konwertuje - faktyczne zapisywanie będzie w kolejnej iteracji.
        """
        return self._save_participant_state_with_participant_mapping(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ParticipantState w MongoDB po source_id i zwraca jego MongoDB ID.
        POPRAWKA: ParticipantState jest embedded w participants.participant_states[]
        """
        try:
            if DEBUG:
               print(f"🔍 Searching for ParticipantState with source_id: {source_id}")

            # Szukaj w kolekcji participants w embedded participant_states array
            query_filter = {
                "participant_states": {
                    "$elemMatch": {
                        "external_id": f"{source_id}"
                    }
                }
            }
            if DEBUG:
                print(f"🔍 Query filter for embedded ParticipantState: {query_filter}")

            participants_with_states = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,  # Szukamy w participants!
                dataset_id=dataset_id,
                query=query_filter
            )
            if DEBUG:

                print(f"🔍 Found {len(participants_with_states) if participants_with_states else 0} participants with matching ParticipantState")

            if participants_with_states and len(participants_with_states) > 0:
                participant_doc = participants_with_states[0]

                # Znajdź konkretny ParticipantState w participant_states array
                for ps in participant_doc.get("participant_states", []):
                    if ps.get("external_id") == source_id:
                        ps_id = str(ps.get("id", ""))
                        if DEBUG:
                            print(f"✅ Found embedded ParticipantState: {source_id} -> MongoDB ID: {ps_id}")
                        return ps_id

            print(f"❌ ParticipantState not found for source ID: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding ParticipantState by source_id {source_id}: {e}")
            return ""

    def _save_participant_state_with_participant_mapping(self, grisera_object, dataset_id: str, import_id: str):
        """
        Zapisuje ParticipantState z mapowaniem participant_id z source ID na MongoDB ID.
        """
        try:
            if DEBUG:
                print(f"💾 Saving ParticipantState with participant mapping...")

            # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
            source_entity_ref = grisera_object.external_id

            if not source_entity_ref:
                if DEBUG:
                    print("⚠️ No source_entity_ref found in ParticipantState")
            else:
                if DEBUG:
                    print(f"🔍 ParticipantState source ID: {source_entity_ref}")

            # KROK 2: Mapuj participant_id z source ID na MongoDB ID
            mapped_participant_id = grisera_object.participant_id
            if grisera_object.participant_id and str(grisera_object.participant_id).startswith(":"):
                # To jest source ID, mapuj na MongoDB ID
                participant_source_id = str(grisera_object.participant_id).replace(":", "")
                participant_mongo_id = self.participant_service.find_by_source_id(participant_source_id, dataset_id)

                if participant_mongo_id:
                    mapped_participant_id = participant_mongo_id
                    if DEBUG:
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

            grisera_object.participant_id = mapped_participant_id
            grisera_object.import_job_id = import_id
            if DEBUG:
                print(f"✅ ParticipantState being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_participant_service().add_participant_state(grisera_object,dataset_id)
            saved_participant_state_id = str(getattr(result, 'id', 'unknown'))
            if DEBUG:
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

