"""
TimeSeries JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class TimeSeriesJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji TimeSeries -> co:TimeSeries. Standardowe pobieranie z kolekcji."""
    
    def _get_entity_type(self) -> str:
        return "TimeSeries"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:TimeSeries"
    
    def get_collection_enum(self) -> Collections:
        return Collections.TIME_SERIES
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera TimeSeries dla dataset_id z standardowej kolekcji.
        TimeSeries są przechowywane jako oddzielna kolekcja.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje TimeSeries z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)

        # Dodaj właściwości JSON-LD
        properties = {}

        if "timestamp" in entity_doc and entity_doc["timestamp"]:
            properties["co:hasTimestamp"] = entity_doc["timestamp"]

        if "value" in entity_doc and entity_doc["value"]:
            properties["co:hasValue"] = entity_doc["value"]

        if "metadata" in entity_doc and entity_doc["metadata"]:
            metadata = entity_doc["metadata"]
            
            if "source" in metadata and metadata["source"]:
                properties["co:timeSeriesSource"] = metadata["source"]
                
            if "observable_information_ids" in metadata and metadata["observable_information_ids"]:
                properties["co:hasObservableInformation"] = [self._create_id_object(oi_id) for oi_id in metadata["observable_information_ids"]]
                
            if "measure_id" in metadata and metadata["measure_id"]:
                properties["co:hasMeasure"] = [self._create_id_object(metadata["measure_id"])]

        # Dodaj brakujące powiązania - pobierz z powiązanych kolekcji
        if "metadata" in entity_doc and entity_doc["metadata"]:
            metadata = entity_doc["metadata"]
            
            # Pobierz ObservableInformation po observable_information_id
            if "observable_information_id" in metadata and metadata["observable_information_id"]:
                obs_info_id = metadata["observable_information_id"]
                # TODO: Pobierz ObservableInformation i dodaj jego powiązania (Recording, Participation, etc.)
                properties["co:hasObservableInformation"] = [self._create_id_object(obs_info_id)]
                
            # Pobierz Measure po measure_id
            if "measure_id" in metadata and metadata["measure_id"]:
                measure_id = metadata["measure_id"]
                # TODO: Pobierz Measure i dodaj jego powiązania (MeasureName, etc.)
                properties["co:hasMeasure"] = [self._create_id_object(measure_id)]

        base_structure.update(properties)
        return base_structure
