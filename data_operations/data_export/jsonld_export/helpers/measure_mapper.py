"""
Measure JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class MeasureJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Measure -> co:Measure."""
    
    def _get_entity_type(self) -> str:
        return "Measure"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Measure"
    
    def get_collection_enum(self) -> Collections:
        return Collections.MEASURE
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Measure dla dataset_id z standardowej kolekcji.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Measure z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}
        
        if "measure_name_id" in entity_doc and entity_doc["measure_name_id"]:
            properties["co:hasMeasureName"] = [self._create_id_object(entity_doc["measure_name_id"])]
            
        if "datatype" in entity_doc and entity_doc["datatype"]:
            properties["co:hasDatatype"] = entity_doc["datatype"]
            
        if "range" in entity_doc and entity_doc["range"]:
            properties["co:hasRange"] = entity_doc["range"]
            
        if "unit" in entity_doc and entity_doc["unit"]:
            properties["co:hasUnit"] = entity_doc["unit"]
            
        if "values" in entity_doc and entity_doc["values"]:
            # TODO: Mapuj values na odpowiednią strukturę
            properties["co:hasValues"] = entity_doc["values"]
        
        base_structure.update(properties)
        return base_structure
