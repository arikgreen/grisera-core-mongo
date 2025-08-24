from typing import Dict, Any
from grisera import MeasureNameIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class MeasureNameConverter(BaseEntityConverter[MeasureNameIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["measureName", "hasName", "name"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Measure"
    
    def convert(self, json_entity: Dict[str, Any]) -> MeasureNameIn:
        external_id = self._get_external_id(json_entity)
        measure_name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )
        
        measure_name_obj = MeasureNameIn(
            name=measure_name,
            type="User defined"
        )

        additional_properties = self._set_common_properties(json_entity, measure_name_obj)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(f"📝 Creating MeasureNameIn: measure_name='{measure_name}', external_id='{measure_name_obj.external_id}', import_job_id='{measure_name_obj.import_job_id}', properties={len(additional_properties)} (including common)")
        if DEBUG:
            print(f"✅ MeasureName being saved with final data: {measure_name_obj.__dict__}")
        return measure_name_obj

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str): #-> MeasureNameIn:
        return self.services.get_measure_name_service().save_measure_name(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.MEASURE_NAME)


