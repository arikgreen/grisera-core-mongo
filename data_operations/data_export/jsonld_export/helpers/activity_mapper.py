"""
Activity JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ActivityJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Activity -> co:Activity."""
    
    def _get_entity_type(self) -> str:
        return "Activity"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Activity"
    
    def get_collection_enum(self) -> Collections:
        return Collections.ACTIVITY
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Activity dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Activity z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)

        # Dodaj właściwości JSON-LD
        properties = {}

        # Mapuj activity type
        if "activity" in entity_doc and entity_doc["activity"]:
            properties["co:hasActivityType"] = entity_doc["activity"]

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
