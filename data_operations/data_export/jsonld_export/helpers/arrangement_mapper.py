"""
Arrangement JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ArrangementJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Arrangement -> co:Arrangement."""
    
    def _get_entity_type(self) -> str:
        return "Arrangement"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Arrangement"
    
    def get_collection_enum(self) -> Collections:
        return Collections.ARRANGEMENT
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Arrangement dla dataset_id z standardowej kolekcji.
        """
        # print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        # entities = self._fetch_entities_from_collection_enum(dataset_id)
        #
        # print(f"✅ Found {len(entities)} {self.entity_type} entities")
        # return entities
        return [] # brak bezpośrednich Arrangement w owl

    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Arrangement z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}

        # Mapuj arrangement_type
        if "arrangement_type" in entity_doc and entity_doc["arrangement_type"]:
            properties["co:hasArrangementType"] = entity_doc["arrangement_type"]

        # Mapuj name z additional_properties
        if "additional_properties" in entity_doc and entity_doc["additional_properties"]:
            for prop in entity_doc["additional_properties"]:
                if prop.get("key") == "name" and prop.get("value"):
                    properties["co:hasName"] = prop["value"]
                    break

            for prop in entity_doc["additional_properties"]:
                if prop.get("key") == "description" and prop.get("value"):
                    properties["co:hasDescription"] = prop["value"]
                    break

        base_structure.update(properties)
        return base_structure
