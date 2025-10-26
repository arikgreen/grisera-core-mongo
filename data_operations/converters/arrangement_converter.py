import re
from typing import Dict, Any, Optional
from grisera import ArrangementIn
from .base import BaseEntityConverter, DEBUG
from mongo_service.collection_mapping import Collections
from ..import_logger import get_import_logger


class ArrangementConverter(BaseEntityConverter[ArrangementIn]):
    JSON_KEY_CANDIDATES_FOR_TYPE_FIELD = ["hasArrangementType", "arrangementType", "hasType", "type"]
    JSON_KEY_CANDIDATES_FOR_DISTANCE_FIELD = ["hasDistance", "distance", "arrangementDistance"]
    DEFAULT_MAIN_FIELD_PREFIX = "Arrangement"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.logger = get_import_logger(import_id=import_id, collection=Collections.ARRANGEMENT)

    def convert(self, json_entity: Dict[str, Any]) -> ArrangementIn:
        external_id = self._get_external_id(json_entity)
        print(f"🔄 Converting Arrangement entity with external ID: {external_id} and type: {json_entity.get('type', 'N/A')}")
        arrangement_type = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_TYPE_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )

        arrangement = ArrangementIn(arrangement_type=arrangement_type)

        arrangement_distance = self._get_optional_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_DISTANCE_FIELD
        )
        if arrangement_distance:
            arrangement.arrangement_distance = arrangement_distance

        additional_properties = self._set_common_properties(json_entity, arrangement)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_TYPE_FIELD)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DISTANCE_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(f"✅ Arrangement being saved with final data: {arrangement.__dict__}")

        return arrangement

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> str:
        grisera_object = self.convert(json_entity)

        if grisera_object.external_id:
            existing_id = self.find_by_source_id(grisera_object.external_id, dataset_id)
            if existing_id:
                self.logger.log_info(f"✅ Arrangement found by external_id: {grisera_object.external_id} -> {existing_id}")
                return existing_id

        existing_id = self._find_existing_arrangement_by_type_and_distance(
            grisera_object.arrangement_type,
            grisera_object.arrangement_distance if hasattr(grisera_object, 'arrangement_distance') else None,
            dataset_id
        )
        if existing_id:
            self.logger.log_info(
                f"✅ Arrangement found by type and distance: {grisera_object.arrangement_type}, {getattr(grisera_object, 'arrangement_distance', None)} -> {existing_id}")
            self._update_arrangement_external_id(existing_id, grisera_object.external_id, dataset_id)
            return existing_id

        self.logger.log_info(f"📝 Creating new Arrangement: {grisera_object.arrangement_type}")
        return self.services.get_arrangement_service().save_arrangement(grisera_object, dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.ARRANGEMENT)

    def _find_existing_arrangement_by_type_and_distance(self, arrangement_type: str, arrangement_distance: Optional[str],
                                                         dataset_id: str) -> str:
        """Znajduje Arrangement po krotce (arrangement_type, arrangement_distance) case-insensitive"""
        try:
            query_filter = {
                "arrangement_type": {"$regex": f"^{re.escape(arrangement_type)}$", "$options": "i"},
                "arrangement_distance": arrangement_distance
            }
            arrangements = self.mongo_api_service.get_documents(
                collection_name=Collections.ARRANGEMENT.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if arrangements:
                existing_id = str(arrangements[0].get("id", ""))
                self.logger.log_info(
                    f"🔍 Found existing Arrangement by type and distance: {arrangement_type}, {arrangement_distance} (ID: {existing_id})")
                return existing_id

            return ""
        except Exception as e:
            self.logger.log_info(f"❌ Error finding Arrangement by type and distance: {e}")
            return ""

    def _update_arrangement_external_id(self, arrangement_id: str, external_id: str, dataset_id: str):
        """Aktualizuje external_id w istniejącym Arrangement"""
        try:
            arrangement_doc = self.mongo_api_service.get_document(
                arrangement_id,
                Collections.ARRANGEMENT.value,
                dataset_id
            )

            if arrangement_doc and not arrangement_doc.get("external_id"):
                arrangement_doc["external_id"] = external_id
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.ARRANGEMENT.value,
                    id=arrangement_id,
                    new_document=arrangement_doc,
                    dataset_id=dataset_id
                )
                self.logger.log_info(f"🔗 Updated Arrangement {arrangement_id} with external_id: {external_id}")
        except Exception as e:
            self.logger.log_info(f"❌ Error updating Arrangement external_id: {e}")
