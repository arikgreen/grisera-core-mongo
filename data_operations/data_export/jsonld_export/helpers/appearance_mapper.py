"""
Appearance JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class AppearanceJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Appearance -> co:Appearance."""
    
    def _get_entity_type(self) -> str:
        return "Appearance"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Appearance"
    
    def get_collection_enum(self) -> Collections:
        return Collections.APPEARANCE
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Appearance dla dataset_id z standardowej kolekcji.
        """
        # print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        # entities = self._fetch_entities_from_collection_enum(dataset_id)
        #
        # print(f"✅ Found {len(entities)} {self.entity_type} entities")
        # return entities
        # FIXME Brak w owl
        return []
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Appearance z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # TODO: Add specific Appearance mappings
        # - hasParticipantState
        # - appearance properties (occlusion, somatotype)
        
        return base_structure
