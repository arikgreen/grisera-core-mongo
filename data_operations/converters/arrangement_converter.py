from typing import Dict, Any
from grisera import ArrangementIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class ArrangementConverter(BaseEntityConverter[ArrangementIn]):
    JSON_KEY_CANDIDATES_FOR_TYPE_FIELD = ["arrangementType", "hasType", "type"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Arrangement"
    
    def convert(self, json_entity: Dict[str, Any]) -> ArrangementIn:
        external_id = self._get_external_id(json_entity)
        arrangement_type = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_TYPE_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )
        
        arrangement = ArrangementIn(arrangement_type=arrangement_type)

        additional_properties = self._set_common_properties(json_entity, arrangement)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_TYPE_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(f"✅ Arrangement being saved with final data: {arrangement.__dict__}")

        return arrangement


    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> ArrangementIn:
        return self.services.get_arrangement_service().save_arrangement(self.convert(json_entity))

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.ARRANGEMENT)