"""
RegisteredChannel JSON-LD Helper
"""

from typing import Dict, Any, List

from mongo_service.collection_mapping import Collections
from .base_mapper import BaseJsonLdHelper


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
        Pobiera RegisteredChannel dla dataset_id z zagnieżdżonymi elementami używając agregacji MongoDB.
        Pobiera powiązane Channel oraz RegisteredData.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")

        collection_name = self.get_collection_enum().value

        aggregation = [
            # Step 1: Join with channels
            {
                "$lookup": {
                    "from": "channels",
                    "localField": "channel_id",
                    "foreignField": "_id",
                    "as": "related_channels"
                }
            },

            # Step 2: Join with registered_data
            {
                "$lookup": {
                    "from": "registered_data",
                    "localField": "registered_data_id",
                    "foreignField": "_id",
                    "as": "related_registered_data"
                }
            }
        ]

        db = self.mongo_api_service.client[dataset_id]
        entities = list(db[collection_name].aggregate(aggregation))

        # Convert ObjectIds to strings to avoid JSON serialization issues
        for entity in entities:
            self.mongo_api_service._fix_output_ids(entity)

        print(f"✅ Found {len(entities)} {self.entity_type} entities with nested data")
        return entities

    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje RegisteredChannel z MongoDB na JSON-LD z zagnieżdżonymi elementami"""
        base_structure = self._create_basic_json_structure(entity_doc)

        properties = {}

        # Mapuj Channel
        if "related_channels" in entity_doc and entity_doc["related_channels"]:
            channels = []
            for channel in entity_doc["related_channels"]:
                channel_obj = {
                    "@id": f"{channel['_id']}"
                }
                channels.append(channel_obj)

            if channels:
                properties["co:hasChannel"] = channels

        # Mapuj RegisteredData  
        if "related_registered_data" in entity_doc and entity_doc["related_registered_data"]:
            registered_data_list = []
            for registered_data in entity_doc["related_registered_data"]:
                registered_data_obj = {
                    "@id": f"{registered_data['_id']}"
                }
                registered_data_list.append(registered_data_obj)

            if registered_data_list:
                properties["co:hasRegisteredData"] = registered_data_list

        base_structure.update(properties)
        return base_structure
