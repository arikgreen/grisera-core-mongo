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
        Dodatkowo pobiera measure_name dla każdego measure.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        entities = self._fetch_entities_from_collection_enum(dataset_id)
        
        enriched_entities = []
        for entity in entities:
            enriched_entity = entity.copy()
            
            if "measure_name_id" in entity and entity["measure_name_id"]:
                measure_names = self.mongo_api_service.get_documents(
                    collection_name=Collections.MEASURE_NAME.value,
                    dataset_id=dataset_id,
                    query={"_id": entity["measure_name_id"]}
                )
                
                if measure_names and len(measure_names) > 0:
                    measure_name = measure_names[0]
                    enriched_entity["_measure_name_data"] = {
                        "id": measure_name.get("id"),
                        "name": measure_name.get("name"),
                        "type": measure_name.get("type")
                    }
                else:
                    print(f"<UNK> [ERROR] No measure name found for {entity['measure_name_id']}")
            
            enriched_entities.append(enriched_entity)
        
        print(f"✅ Found {len(enriched_entities)} {self.entity_type} entities with enriched measure_name data")
        return enriched_entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Measure z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        # Dodaj właściwości JSON-LD
        properties = {}
        
        if "measure_name_id" in entity_doc and entity_doc["measure_name_id"]:
            # Sprawdź czy mamy wzbogacone dane measure_name
            if "_measure_name_data" in entity_doc and entity_doc["_measure_name_data"]:
                measure_name_data = entity_doc["_measure_name_data"]
                # Twórz obiekt z @id i hasName
                measure_name_obj = {
                    "@id": str(measure_name_data.get("id", entity_doc["measure_name_id"]))
                }
                if measure_name_data.get("name"):
                    measure_name_obj["hasName"] = measure_name_data["name"]
                if measure_name_data.get("type"):
                    measure_name_obj["hasType"] = measure_name_data["type"]
                
                properties["co:hasMeasureName"] = [measure_name_obj]
            else:
                # Fallback - tylko @id
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
