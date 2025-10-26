import re
from grisera import ModalityIn
from typing import Dict, Any, Optional

from mongo_service.collection_mapping import Collections
from .base import BaseEntityConverter, DEBUG
from ..import_logger import get_import_logger


class ModalityConverter(BaseEntityConverter[ModalityIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["modalityName", "hasName", "name"]
    DEFAULT_MAIN_FIELD_PREFIX = "Modality"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.logger = get_import_logger(import_id=import_id, collection=Collections.MODALITY)

    def convert(self, json_entity: Dict[str, Any]) -> ModalityIn:
        external_id = self._get_external_id(json_entity)
        self.logger.log_info(f'🔄 Converting Modality entity with external_id: {external_id}')

        modality_name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )

        modality = ModalityIn(modality=modality_name)

        additional_properties = self._set_common_properties(json_entity, modality)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        if DEBUG:
            print(
                f"📝 Creating ModalityIn: modality_name='{modality_name}', external_id='{modality.external_id}', import_job_id='{modality.import_job_id}', properties={len(additional_properties)} (including common)")
        return modality

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> str:
        grisera_object = self.convert(json_entity)

        if grisera_object.external_id:
            existing_id = self.find_by_source_id(grisera_object.external_id, dataset_id)
            if existing_id:
                self.logger.log_info(f"✅ Modality found by external_id: {grisera_object.external_id} -> {existing_id}")
                return existing_id

        existing_id = self._find_existing_modality_by_name(grisera_object.modality, dataset_id)
        if existing_id:
            self.logger.log_info(f"✅ Modality found by name: {grisera_object.modality} -> {existing_id}")
            self._update_modality_external_id(existing_id, grisera_object.external_id, dataset_id)
            return existing_id

        self.logger.log_info(f"📝 Creating new Modality: {grisera_object.modality}")
        return self.services.get_modality_service().save_modality(grisera_object, dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.MODALITY)

    def _find_existing_modality_by_name(self, modality_name: str, dataset_id: str) -> str:
        """Znajduje Modality po nazwie (case-insensitive)"""
        try:
            query_filter = {
                "modality": {"$regex": f"^{re.escape(modality_name)}$", "$options": "i"}
            }
            modalities = self.mongo_api_service.get_documents(
                collection_name=Collections.MODALITY.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if modalities:
                existing_id = str(modalities[0].get("id", ""))
                self.logger.log_info(f"🔍 Found existing Modality by name: {modality_name} (ID: {existing_id})")
                return existing_id

            return ""
        except Exception as e:
            self.logger.log_info(f"❌ Error finding Modality by name: {e}")
            return ""

    def _update_modality_external_id(self, modality_id: str, external_id: str, dataset_id: str):
        """Aktualizuje external_id w istniejącym Modality"""
        try:
            modality_doc = self.mongo_api_service.get_document(
                modality_id,
                Collections.MODALITY.value,
                dataset_id
            )

            if modality_doc and not modality_doc.get("external_id"):
                modality_doc["external_id"] = external_id
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.MODALITY.value,
                    id=modality_id,
                    new_document=modality_doc,
                    dataset_id=dataset_id
                )
                self.logger.log_info(f"🔗 Updated Modality {modality_id} with external_id: {external_id}")
        except Exception as e:
            self.logger.log_info(f"❌ Error updating Modality external_id: {e}")
