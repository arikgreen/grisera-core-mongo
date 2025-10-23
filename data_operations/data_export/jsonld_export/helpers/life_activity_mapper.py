"""
LifeActivity JSON-LD Helper
"""

from typing import Dict, Any, List

from mongo_service.collection_mapping import Collections
from .base_mapper import BaseJsonLdHelper


class LifeActivityJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji LifeActivity -> co:LifeActivity."""

    def _get_entity_type(self) -> str:
        return "LifeActivity"

    def get_jsonld_collection_key(self) -> str:
        return "co:LifeActivity"

    def get_collection_enum(self) -> Collections:
        return Collections.LIFE_ACTIVITY

    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera LifeActivity dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        #
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities

    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje LifeActivity z MongoDB na JSON-LD zgodnie z wymaganą strukturą"""
        base_structure = self._create_basic_json_structure(entity_doc)

        properties = {}

        if "life_activity" in entity_doc and entity_doc["life_activity"]:
            life_activity_value = entity_doc["life_activity"]
            properties["co:hasName"] = life_activity_value
            properties["co:hasDescription"] = life_activity_value

        base_structure.update(properties)
        return base_structure
