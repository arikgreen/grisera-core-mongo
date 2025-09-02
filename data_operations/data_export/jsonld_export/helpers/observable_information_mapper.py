"""
ObservableInformation JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ObservableInformationJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji ObservableInformation -> co:ObservableInformation."""
    
    def _get_entity_type(self) -> str:
        return "ObservableInformation"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:ObservableInformation"

    def get_collection_enum(self) -> Collections:
        # ObservableInformation są zagnieżdżone w kolekcji RECORDING
        return Collections.RECORDING

    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera ObservableInformation dla dataset_id z kolekcji RECORDING.
        ObservableInformation są zagnieżdżone w polu 'observable_informations' każdego recording.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")

        # Pobierz wszystkie recording dla danego dataset
        recordings = self._fetch_entities_from_collection_enum(dataset_id)

        all_observable_informations = []
        for recording in recordings:
            if "observable_informations" in recording and recording["observable_informations"]:
                for observable_info in recording["observable_informations"]:
                    # Dodaj parent recording info do każdego observable_information
                    observable_info["_parent_recording"] = {
                        "id": recording["id"],
                        "participation_id": recording.get("participation_id"),
                        "registered_channel_id": recording.get("registered_channel_id")
                    }
                    all_observable_informations.append(observable_info)

        print(
            f"✅ Found {len(all_observable_informations)} {self.entity_type} entities from {len(recordings)} recordings")
        return all_observable_informations
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje ObservableInformation z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        properties = {}
        if "_parent_recording" in entity_doc and entity_doc["_parent_recording"]:
            parent_recording = entity_doc["_parent_recording"]
            properties["co:hasRecording"] = [self._create_id_object(str(parent_recording["id"]))]

        if "modality_id" in entity_doc and entity_doc["modality_id"]:
            properties["co:hasModality"] = [self._create_id_object(str(entity_doc["modality_id"]))]

        if "life_activity_id" in entity_doc and entity_doc["life_activity_id"]:
            properties["co:hasLifeActivity"] = [self._create_id_object(str(entity_doc["life_activity_id"]))]
        
        base_structure.update(properties)
        return base_structure
