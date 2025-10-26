import re
from grisera import LifeActivityIn
from typing import Dict, Any, Optional

from mongo_service.collection_mapping import Collections
from .base import BaseEntityConverter, DEBUG
from ..import_logger import get_import_logger


class LifeActivityConverter(BaseEntityConverter[LifeActivityIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["lifeActivityName", "hasName", "name"]
    DEFAULT_MAIN_FIELD_PREFIX = "LifeActivity"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.logger = get_import_logger(import_id=import_id, collection=Collections.LIFE_ACTIVITY)

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

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> str:
        self.logger.log_info(f'🔄 Processing LifeActivity entity: {json_entity}')
        grisera_object = self.convert(json_entity)

        if grisera_object.external_id:
            existing_id = self.find_by_source_id(grisera_object.external_id, dataset_id)
            if existing_id:
                self.logger.log_info(f"✅ LifeActivity found by external_id: {grisera_object.external_id} -> {existing_id}")
                return existing_id

        existing_id = self._find_existing_life_activity_by_name(
            grisera_object.life_activity,
            dataset_id
        )
        if existing_id:
            self.logger.log_info(f"✅ LifeActivity found by name: {grisera_object.life_activity} -> {existing_id}")
            self._update_life_activity_external_id(existing_id, grisera_object.external_id, dataset_id)
            return existing_id

        self.logger.log_info(f"📝 Creating new LifeActivity: {grisera_object.life_activity}")
        return self.services.get_life_activity_service().save_life_activity(grisera_object, dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.LIFE_ACTIVITY)

    def _find_existing_life_activity_by_name(self, life_activity_name: str, dataset_id: str) -> str:
        """Znajduje LifeActivity po nazwie (case-insensitive)"""
        try:
            query_filter = {
                "life_activity": {"$regex": f"^{re.escape(life_activity_name)}$", "$options": "i"}
            }
            life_activities = self.mongo_api_service.get_documents(
                collection_name=Collections.LIFE_ACTIVITY.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if life_activities:
                existing_id = str(life_activities[0].get("id", ""))
                self.logger.log_info(f"🔍 Found existing LifeActivity by name: {life_activity_name} (ID: {existing_id})")
                return existing_id

            return ""
        except Exception as e:
            self.logger.log_info(f"❌ Error finding LifeActivity by name: {e}")
            return ""

    def _update_life_activity_external_id(self, life_activity_id: str, external_id: str, dataset_id: str):
        """Aktualizuje external_id w istniejącym LifeActivity"""
        try:
            life_activity_doc = self.mongo_api_service.get_document(
                life_activity_id,
                Collections.LIFE_ACTIVITY.value,
                dataset_id
            )

            if life_activity_doc and not life_activity_doc.get("external_id"):
                life_activity_doc["external_id"] = external_id
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.LIFE_ACTIVITY.value,
                    id=life_activity_id,
                    new_document=life_activity_doc,
                    dataset_id=dataset_id
                )
                self.logger.log_info(f"🔗 Updated LifeActivity {life_activity_id} with external_id: {external_id}")
        except Exception as e:
            self.logger.log_info(f"❌ Error updating LifeActivity external_id: {e}")
