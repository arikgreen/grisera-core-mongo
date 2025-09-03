"""
RegisteredData JSON-LD Helper
"""

from typing import Dict, Any, List

from mongo_service.collection_mapping import Collections
from .base_mapper import BaseJsonLdHelper


class RegisteredDataJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji RegisteredData -> co:RegisteredData."""

    def _get_entity_type(self) -> str:
        return "RegisteredData"

    def get_jsonld_collection_key(self) -> str:
        return "co:RegisteredData"

    def get_collection_enum(self) -> Collections:
        return Collections.REGISTERED_DATA

    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera RegisteredData dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)

        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities

    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje RegisteredData z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)

        properties = {}

        # Dodaj registeredDataSource z pola source
        if "source" in entity_doc and entity_doc["source"]:
            properties["co:registeredDataSource"] = entity_doc["source"]

        base_structure.update(properties)
        return base_structure
