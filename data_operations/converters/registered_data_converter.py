from typing import Dict, Any
from grisera import RegisteredDataIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class RegisteredDataConverter(BaseEntityConverter[RegisteredDataIn]):
    JSON_KEY_CANDIDATES_FOR_SOURCE = ["source", "hasSource"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "RegisteredData"
    
    def convert(self, json_entity: Dict[str, Any]) -> RegisteredDataIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij source - opcjonalny
        source = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_SOURCE)
        
        if not source:
            # Generuj source URL na podstawie external_id  
            clean_id = remove_prefix(external_id) if external_id else "unknown"
            source = f"https://road.affectivese.org/datasets/InconsistencyDataset/{clean_id}.csv"
        
        registered_data = RegisteredDataIn(source=source)

        additional_properties = self._set_common_properties(json_entity, registered_data)

        if not any(prop.key in ["name", "description"] for prop in additional_properties if hasattr(prop, 'key')):
            from grisera import PropertyIn
            clean_id = remove_prefix(external_id) if external_id else "unknown"
            additional_properties.extend([
                PropertyIn(key="name", value=clean_id),  # Nazwa na podstawie ID
                PropertyIn(key="description", value=f"Auto-generated registered data for {clean_id}")
            ])

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_SOURCE)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        print(f"📝 Creating RegisteredDataIn: name='{clean_name_for_log}', source='{source}', external_id='{registered_data.external_id}', import_job_id='{registered_data.import_job_id}', properties={len(additional_properties)} (including common)")
        registered_data.additional_properties = additional_properties
        return registered_data

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> RegisteredDataIn:
        return self.services.get_registered_data_service().save_registered_data(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.REGISTERED_DATA)


