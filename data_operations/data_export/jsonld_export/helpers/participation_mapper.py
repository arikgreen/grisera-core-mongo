"""
Participation JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ParticipationJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Participation -> co:Participation."""
    
    def _get_entity_type(self) -> str:
        return "Participation"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Participation"
    
    def get_collection_enum(self) -> Collections:
        return Collections.PARTICIPATION
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Participation dla dataset_id z standardowej kolekcji.
        Dodatkowo pobiera participant_id z participant_state dla każdego participation.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        # Pobierz participant_id dla każdego participation przez participant_state
        enriched_entities = []
        for entity in entities:
            enriched_entity = entity.copy()
            
            if "participant_state_id" in entity and entity["participant_state_id"]:
                # Pobierz participant_state żeby wyciągnąć participant_id
                participant_states = self.mongo_api_service.get_documents(
                    collection_name=Collections.PARTICIPANT.value,
                    dataset_id=dataset_id,
                    query={
                        "participant_states": {
                            "$elemMatch": {
                                "id": entity["participant_state_id"]
                            }
                        }
                    }
                )
                
                if participant_states and len(participant_states) > 0:
                    participant = participant_states[0]
                    # Znajdź konkretny participant_state w array
                    for ps in participant.get("participant_states", []):
                        if str(ps.get("id")) == str(entity["participant_state_id"]):
                            # Dodaj participant_id do participation
                            enriched_entity["_participant_id"] = participant.get("id")
                            break
            
            enriched_entities.append(enriched_entity)
        
        print(f"✅ Found {len(enriched_entities)} {self.entity_type} entities with enriched participant data")
        return enriched_entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Participation z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}

        # Mapuj participant_state_id
        if "participant_state_id" in entity_doc and entity_doc["participant_state_id"]:
            properties["co:hasParticipantState"] = [self._create_id_object(str(entity_doc["participant_state_id"]))]

        if "_participant_id" in entity_doc and entity_doc["_participant_id"]:
            properties["co:hasParticipant"] = [self._create_id_object(str(entity_doc["_participant_id"]))]

        # Mapuj activity_execution_id
        if "activity_execution_id" in entity_doc and entity_doc["activity_execution_id"]:
            properties["co:hasActivityExecution"] = [self._create_id_object(str(entity_doc["activity_execution_id"]))]


        # TODO: Add hasRecording mapping when we have the relationship
        # Recording ma participation_id, więc możemy to zrobić w Recording mapper

        base_structure.update(properties)
        return base_structure
