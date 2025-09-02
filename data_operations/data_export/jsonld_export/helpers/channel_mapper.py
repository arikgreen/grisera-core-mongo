"""
Channel JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ChannelJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Channel -> co:Channel."""
    
    def _get_entity_type(self) -> str:
        return "Channel"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Channel"
    
    def get_collection_enum(self) -> Collections:
        return Collections.CHANNEL
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Channel dla dataset_id z standardowej kolekcji.
        """
        # print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        # entities = self._fetch_entities_from_collection_enum(dataset_id)
        #
        # print(f"✅ Found {len(entities)} {self.entity_type} entities")
        # return entities
        return [] # brak bezpośrednich Channel w owl
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Channel z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # TODO: Add specific Channel mappings
        # - hasRegisteredChannel
        # - channel properties
        
        return base_structure
