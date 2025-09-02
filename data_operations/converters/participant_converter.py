from typing import Dict, Any

from grisera import ParticipantIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix

from data_operations.data_mappers import map_sex_value
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class ParticipantConverter(BaseEntityConverter[ParticipantIn]):
    JSON_KEY_CANDIDATES_FOR_NAME = ["name", "hasName"]
    JSON_KEY_CANDIDATES_FOR_SEX = ["sex", "hasSex"]
    JSON_KEY_CANDIDATES_FOR_DOB = ["dateOfBirth", "hasDateOfBirth"]
    JSON_KEY_CANDIDATES_FOR_DISORDER = ["disorder", "hasDisorder"]
    DEFAULT_MAIN_FIELD_PREFIX = "Participant"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.services = MongoServiceFactory()

    def convert(self, json_entity: Dict[str, Any]) -> ParticipantIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij nazwę uczestnika
        name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_NAME,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            external_id
        )

        # Wyciągnij pola specyficzne dla Participant
        raw_sex = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_SEX, perform_deep_lookup=True)
        sex = map_sex_value(raw_sex) if raw_sex else None
        date_of_birth = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_DOB)
        disorder = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_DISORDER)

        # Utwórz obiekt ParticipantIn
        participant = ParticipantIn(
            name=name,
            sex=sex,
            date_of_birth=date_of_birth,
            disorder=disorder
        )

        # Ustaw standardowe właściwości importu bezpośrednio na obiekcie
        additional_properties = self._set_common_properties(json_entity, participant)

        # Wyklucz już przetworzone klucze z additional_properties
        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_NAME)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_SEX)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DOB)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DISORDER)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(f"✅ Participant being saved with final data: {participant.__dict__}")

        return participant

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> ParticipantIn:
        return self.services.get_participant_service().save_participant(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Finds Participant in MongoDB by source_id and returns its MongoDB ID
        """
        try:
            if DEBUG:
                print(f"🔍 Searching for Participant with source_id: {source_id}")

            query_filter = {
                "external_id": f":{source_id}"
            }

            if DEBUG:
                print(f"🔍 Query filter: {query_filter}")

            participants = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if DEBUG:
                print(f"🔍 Found {len(participants) if participants else 0} participants")

            if participants and len(participants) > 0:
                participant_id = str(participants[0].get("id", ""))
                if DEBUG:
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

            if DEBUG:
                print(
                    f"🔍 DEBUG: Found {len(all_participants) if all_participants else 0} total participants with source_entity_ref")
            if DEBUG:
                for i, participant in enumerate(all_participants[:3]):  # Pokaż pierwsze 3
                    for prop in participant.get("additional_properties", []):
                        if prop.get("key") == "source_entity_ref":
                            print(f"🔍 DEBUG: Participant {i + 1} has source_entity_ref: '{prop.get('value')}'")
                            break

            return ""

        except Exception as e:
            print(f"❌ Error finding Participant by source_id {source_id}: {e}")
            return ""

