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
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Participation z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}

        # Mapuj participant_state_id
        if "participant_state_id" in entity_doc and entity_doc["participant_state_id"]:
            properties["co:hasParticipantState"] = [self._create_id_object(str(entity_doc["participant_state_id"]))]

        # Mapuj activity_execution_id
        if "activity_execution_id" in entity_doc and entity_doc["activity_execution_id"]:
            properties["co:hasActivityExecution"] = [self._create_id_object(str(entity_doc["activity_execution_id"]))]


        # TODO: Add hasRecording mapping when we have the relationship
        # Recording ma participation_id, więc możemy to zrobić w Recording mapper

        base_structure.update(properties)
        return base_structure
