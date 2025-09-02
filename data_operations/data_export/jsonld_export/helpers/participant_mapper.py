"""
Participant JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ParticipantJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Participant -> co:Participant. Obsługuje zagnieżdżone participant_states."""
    
    def _get_entity_type(self) -> str:
        return "Participant"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Participant"
    
    def get_collection_enum(self) -> Collections:
        return Collections.PARTICIPANT
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera participants dla dataset_id.
        Participants mają zagnieżdżone participant_states, które trzeba wyciągnąć osobno.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        participants = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(participants)} participants")
        
        # Wyciągnij participant_states jako oddzielne encje
        participant_states = []
        for participant in participants:
            if "participant_states" in participant and participant["participant_states"]:
                for state in participant["participant_states"]:
                    # Dodaj participant_id do state dla połączenia
                    state["participant_external_id"] = participant.get("external_id")
                    participant_states.append(state)
        
        if participant_states:
            print(f"✅ Also extracted {len(participant_states)} participant states")
            # Zapisz participant_states dla późniejszego użycia przez ParticipantStateHelper
            # TODO: Można to zoptymalizować przez globalny cache
        
        return participants
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Participant z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)

        # Dodaj właściwości JSON-LD
        properties = {}

        if "name" in entity_doc and entity_doc["name"]:
            properties["co:hasName"] = entity_doc["name"]

        if "date_of_birth" in entity_doc and entity_doc["date_of_birth"]:
            properties["co:hasDateOfBirth"] = self._create_id_object(entity_doc["date_of_birth"])

        if "sex" in entity_doc and entity_doc["sex"]:
            properties["co:hasSex"] = [self._create_id_object(entity_doc["sex"])]  # Lista z jednym obiektem

        if "disorder" in entity_doc and entity_doc["disorder"]:
            properties["co:hasDisorder"] = [self._create_id_object(entity_doc["disorder"])]  # Lista z jednym obiektem

        base_structure.update(properties)

        return base_structure
