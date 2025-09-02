"""
ActivityExecution JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ActivityExecutionJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji ActivityExecution -> co:ActivityExecution."""
    
    def _get_entity_type(self) -> str:
        return "ActivityExecution"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:ActivityExecution"
    
    def get_collection_enum(self) -> Collections:
        # Activity executions są zagnieżdżone w kolekcji ACTIVITY
        return Collections.ACTIVITY
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera ActivityExecution dla dataset_id z kolekcji ACTIVITY.
        Activity executions są zagnieżdżone w polu 'activity_executions' każdego activity.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        
        # Pobierz wszystkie activity dla danego dataset
        activities = self._fetch_entities_from_collection_enum(dataset_id)
        
        # Wyciągnij activity executions z każdego activity
        all_activity_executions = []
        for activity in activities:
            if "activity_executions" in activity and activity["activity_executions"]:
                for activity_execution in activity["activity_executions"]:
                    # Dodaj parent activity info do każdego activity execution
                    activity_execution["_parent_activity"] = {
                        "id": activity["id"],
                        "external_id": activity.get("external_id"),
                        "activity_type": activity.get("activity")
                    }
                    all_activity_executions.append(activity_execution)
        
        print(f"✅ Found {len(all_activity_executions)} {self.entity_type} entities from {len(activities)} activities")
        return all_activity_executions
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje ActivityExecution z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}

        # Mapuj activity_id - używamy ID z parent activity
        if "_parent_activity" in entity_doc and entity_doc["_parent_activity"]:
            parent_activity = entity_doc["_parent_activity"]
            properties["co:hasActivity"] = [self._create_id_object(str(parent_activity["id"]))]

        # Mapuj arrangement_id (może być null)
        if "arrangement_id" in entity_doc and entity_doc["arrangement_id"]:
            properties["co:hasArrangement"] = [self._create_id_object(str(entity_doc["arrangement_id"]))]

        base_structure.update(properties)
        return base_structure
