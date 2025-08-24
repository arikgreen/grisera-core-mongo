from typing import Dict, Any, Optional
from grisera import ParticipationIn
from .base import BaseEntityConverter, DEBUG
from .activity_execution_converter import ActivityExecutionConverter
from .participant_state_converter import ParticipantStateConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class ParticipationConverter(BaseEntityConverter[ParticipationIn]):
    JSON_KEY_CANDIDATES_FOR_ACTIVITY_EXECUTION_ID = ["hasActivityExecution", "activity_execution_id"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_PARTICIPANT_STATE_ID = ["hasParticipantState", "participant_state_id"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Participation"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.activity_execution_service = ActivityExecutionConverter(import_id)
        self.participant_state_service = ParticipantStateConverter(import_id)

    def convert(self, json_entity: Dict[str, Any]) -> ParticipationIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij ActivityExecution ID z JSON - może być zagnieżdżony obiekt
        activity_execution_id = self._extract_activity_execution_id_from_json(json_entity)
        
        # Wyciągnij ParticipantState ID z JSON - może być zagnieżdżony obiekt  
        participant_state_id = self._extract_participant_state_id_from_json(json_entity)
        
        # UWAGA: ParticipationIn NIE obsługuje additional_properties!
        # Model ma tylko dwa pola: activity_execution_id i participant_state_id
        
        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        if DEBUG:
            print(f"📝 Creating ParticipationIn: name='{clean_name_for_log}', activity_execution_id='{activity_execution_id}', participant_state_id='{participant_state_id}', external_id='{external_id}' (no additional_properties - model limitation)")
        
        return ParticipationIn(
            activity_execution_id=activity_execution_id,
            participant_state_id=participant_state_id,
            external_id=external_id
        )
    
    def _extract_activity_execution_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga ActivityExecution ID z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_ae_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_ACTIVITY_EXECUTION_ID)
        if simple_ae_id:
            if DEBUG:
                print(f"✅ Found simple activity_execution_id: {simple_ae_id}")
            return simple_ae_id
        
        # Następnie sprawdź co:hasActivityExecution (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_ACTIVITY_EXECUTION_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    ae_source_id = self._extract_nested_entity_id(entity_value)
                    if ae_source_id:
                        if DEBUG:
                            print(f"✅ Found ActivityExecution source ID from {entity_key_with_prefix}: {ae_source_id}")
                        # Zapisujemy source ID - mapowanie na MongoDB ID zostanie zrobione później
                        return ae_source_id
        
        if DEBUG:
            print("⚠️ No ActivityExecution reference found in Participation")
        return None
    
    def _extract_participant_state_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga ParticipantState ID z JSON z zagnieżdżonej struktury hasParticipantState.
        POPRAWKA: Teraz używamy prawdziwego ParticipantState ID zamiast Participant ID!
        """
        # Najpierw sprawdź proste przypadki
        simple_ps_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_PARTICIPANT_STATE_ID)
        if simple_ps_id:
            if DEBUG:
                print(f"✅ Found simple participant_state_id: {simple_ps_id}")
            return simple_ps_id
        
        # Następnie sprawdź co:hasParticipantState (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_PARTICIPANT_STATE_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasParticipantState - wyciągnij @id ParticipantState (nie hasParticipant!)
                    participant_state_id = self._extract_nested_entity_id(entity_value)
                    if participant_state_id:
                        if DEBUG:
                            print(f"✅ Found ParticipantState ID from {entity_key_with_prefix}: {participant_state_id}")
                        # Zapisujemy ParticipantState ID - mapowanie na MongoDB ID zostanie zrobione później
                        return participant_state_id
        
        if DEBUG:
            print("⚠️ No ParticipantState reference found in Participation")
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> ParticipationIn:
        return self._save_participation_with_mapping(self.convert(json_entity),dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje Participation w MongoDB po source_id i zwraca jego MongoDB ID
        NOWA WERSJA - external_id (dla Recording)
        """
        try:
            if DEBUG:
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
                if DEBUG:
                    print(f"✅ Found Participation (via external_id): {source_id} -> MongoDB ID: {participation_id}")
                return participation_id

            # OPCJA 2: Fallback - szukaj po additional_properties (stara metoda)
            if DEBUG:
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
                if DEBUG:
                    print(f"✅ Found Participation (via fallback): {source_id} -> MongoDB ID: {participation_id}")
                return participation_id

            print(f"❌ Participation not found for source ID: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding Participation by source_id {source_id}: {e}")
            return ""

    def _save_participation_with_mapping(self, grisera_object, dataset_id, import_id):
        """
                Zapisuje Participation z mapowaniem source IDs na MongoDB IDs.
                PROSTE MAPOWANIE: source_entity_ref -> MongoDB ID

                MAPOWANIE:
                - activity_execution_id: source_id -> MongoDB ID ActivityExecution (embedded w activities)
                - participant_state_id: source_id -> MongoDB ID ParticipantState (kolekcja participant_states)
                """
        try:
            if DEBUG:
                print(f"💾 Saving Participation with simple ID mapping...")

                print(f"🔍 Original activity_execution_id: {grisera_object.activity_execution_id}")
                print(f"🔍 Original participant_state_id: {grisera_object.participant_state_id}")

            ae_source_id = str(grisera_object.activity_execution_id)
            ae_mongo_id = self.activity_execution_service.find_by_source_id(ae_source_id, dataset_id)

            if ae_mongo_id:
                mapped_activity_execution_id = ae_mongo_id
                if DEBUG:
                    print(f"✅ Mapped activity_execution_id: {grisera_object.activity_execution_id} -> {ae_mongo_id}")
            else:
                print(f"❌ ActivityExecution not found for source ID: {ae_source_id}")
                return None

            mapped_participant_state_id = grisera_object.participant_state_id
            if grisera_object.participant_state_id:
                # To jest source ID, znajdź MongoDB ID ParticipantState
                participant_state_source_id = str(grisera_object.participant_state_id)
                participant_state_mongo_id = self.participant_state_service.find_by_source_id(participant_state_source_id, dataset_id)

                if participant_state_mongo_id:
                    mapped_participant_state_id = participant_state_mongo_id
                    if DEBUG:
                        print(
                            f"✅ Mapped participant_state_id: {grisera_object.participant_state_id} -> ParticipantState ID: {participant_state_mongo_id}")
                else:
                    print(f"❌ ParticipantState not found for source ID: {participant_state_source_id}")
                    return None

            if not mapped_activity_execution_id or not mapped_participant_state_id:
                print(f"❌ Missing required IDs after mapping")
                return None

            grisera_object.activity_execution_id = mapped_activity_execution_id
            grisera_object.participant_state_id = mapped_participant_state_id

            if DEBUG:
                print(f"✅ Participation being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_participation_service().save_participation(grisera_object, dataset_id)
            saved_participation_id = str(getattr(result, 'id', 'unknown'))
            if DEBUG:
                print(f"✅ Participation saved with MongoDB ID: {saved_participation_id}")

            if DEBUG:
                print(
                    f"🔗 Final mapping: ActivityExecution({grisera_object.activity_execution_id} -> {mapped_activity_execution_id}), ParticipantState({grisera_object.participant_state_id} -> {mapped_participant_state_id})")

            return result

        except Exception as e:
            print(f"❌ Error saving Participation with mapping: {e}")
            raise e
