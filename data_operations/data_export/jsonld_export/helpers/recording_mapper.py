"""
Recording JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class RecordingJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Recording -> co:Recording."""
    
    def _get_entity_type(self) -> str:
        return "Recording"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Recording"
    
    def get_collection_enum(self) -> Collections:
        return Collections.RECORDING
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Recording dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Recording z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # TODO co:hasProperty
        properties = {}
        
        if "participation_id" in entity_doc and entity_doc["participation_id"]:
            properties["co:hasParticipation"] = [self._create_id_object(entity_doc["participation_id"])]
            
        if "registered_channel_id" in entity_doc and entity_doc["registered_channel_id"]:
            properties["co:hasRegisteredChannel"] = [self._create_id_object(entity_doc["registered_channel_id"])]
            

        base_structure.update(properties)
        return base_structure
