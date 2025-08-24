from typing import Dict, Any
from grisera import LifeActivityIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class LifeActivityConverter(BaseEntityConverter[LifeActivityIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["lifeActivityName", "hasName", "name"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "LifeActivity"
    
    def convert(self, json_entity: Dict[str, Any]) -> LifeActivityIn:
        external_id = self._get_external_id(json_entity)
        life_activity_name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )
        
        life_activity = LifeActivityIn(life_activity=life_activity_name)

        additional_properties = self._set_common_properties(json_entity, life_activity)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(f"✅ LifeActivity being saved with final data: {life_activity.__dict__}")
        return life_activity

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> LifeActivityIn:
        return self.services.get_life_activity_service().save_life_activity(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.LIFE_ACTIVITY)


