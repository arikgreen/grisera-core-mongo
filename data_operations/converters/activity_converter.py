from typing import Dict, Any
from grisera import ActivityIn, PropertyIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class ActivityConverter(BaseEntityConverter[ActivityIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["hasActivityType", "activityType", "hasType", "type"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Activity"


    def convert(self, json_entity: Dict[str, Any]) -> ActivityIn:
        activity_type = "individual" # TODO: zmienić na wyciąganie z JSON

        activity = ActivityIn(activity=activity_type)

        additional_properties = self._set_common_properties(json_entity, activity)

        external_id = self._get_external_id(json_entity)
        if external_id:
            clean_name = remove_prefix(external_id)
            additional_properties.append(PropertyIn(key="name", value=clean_name))
        else:
            additional_properties.append(PropertyIn(key="name", value="Activity"))

        additional_properties.append(PropertyIn(key="description", value="Activity description"))

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        processed_clean_keys.extend(["name", "description"])
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)
        activity.additional_properties = additional_properties
        if DEBUG:
            print(f"📝 Creating ActivityIn: activity='{activity_type}', external_id='{activity.external_id}', import_job_id='{activity.import_job_id}', properties={len(additional_properties)} (including common)")
        return activity

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str): # -> ActivityIn:
        result = self.services.get_activity_service().save_activity(self.convert(json_entity), dataset_id)
        return result

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.ACTIVITY)
