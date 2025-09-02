"""
ParticipantState JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ParticipantStateJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji ParticipantState -> co:ParticipantState. Pobiera dane z zagnieżdżonych participant_states."""
    
    def _get_entity_type(self) -> str:
        return "ParticipantState"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:ParticipantState"
    
    def get_collection_enum(self) -> Collections:
        return Collections.PARTICIPANT_STATE
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera participant_states z zagnieżdżonych participant.participant_states.
        ParticipantStates nie są przechowywane jako oddzielna kolekcja, tylko jako zagnieżdżone dokumenty.
        """
        print(f"🔍 Fetching {self.entity_type} from nested participant.participant_states")
        
        # Pobierz participants żeby wyciągnąć participant_states
        participants = self.mongo_api_service.get_documents(
            collection_name=Collections.PARTICIPANT.value,
            dataset_id=dataset_id
        )
        
        # Wyciągnij wszystkie participant_states
        participant_states = []
        for participant in participants:
            if "participant_states" in participant and participant["participant_states"]:
                for state in participant["participant_states"]:
                    # Dodaj informacje o parent participant
                    state["participant_external_id"] = participant.get("external_id")
                    state["_participant_id"] = participant.get("id")
                    participant_states.append(state)
        
        print(f"✅ Found {len(participant_states)} participant states from {len(participants)} participants")
        return participant_states
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje ParticipantState z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}
        
        if "age" in entity_doc and entity_doc["age"]:
            properties["co:hasAge"] = entity_doc["age"]
            
        if "personality_ids" in entity_doc and entity_doc["personality_ids"]:
            properties["co:hasPersonality"] = [self._create_id_object(pid) for pid in entity_doc["personality_ids"]]
            
        if "appearance_ids" in entity_doc and entity_doc["appearance_ids"]:
            properties["co:hasAppearance"] = [self._create_id_object(aid) for aid in entity_doc["appearance_ids"]]
            
        if "_participant_id" in entity_doc and entity_doc["_participant_id"]:
            properties["co:hasParticipant"] = [self._create_id_object(entity_doc["_participant_id"])]
        
        base_structure.update(properties)
        return base_structure
