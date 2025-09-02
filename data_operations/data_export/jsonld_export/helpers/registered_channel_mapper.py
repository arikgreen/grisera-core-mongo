"""
RegisteredChannel JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class RegisteredChannelJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji RegisteredChannel -> co:RegisteredChannel."""
    
    def _get_entity_type(self) -> str:
        return "RegisteredChannel"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:RegisteredChannel"
    
    def get_collection_enum(self) -> Collections:
        return Collections.REGISTERED_CHANNEL
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera RegisteredChannel dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje RegisteredChannel z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # TODO: Add specific RegisteredChannel mappings
        # - hasChannel
        # - hasRegisteredData
        # - hasRecording
        
        return base_structure
