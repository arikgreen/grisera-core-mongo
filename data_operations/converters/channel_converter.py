import re
from grisera import ChannelIn
from typing import Dict, Any, Optional

from mongo_service.collection_mapping import Collections
from .base import BaseEntityConverter, DEBUG
from ..import_logger import get_import_logger


class ChannelConverter(BaseEntityConverter[ChannelIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["channelName", "hasName", "name"]
    JSON_KEY_CANDIDATES_FOR_DESCRIPTION_FIELD = ["hasDescription", "description"]
    DEFAULT_MAIN_FIELD_PREFIX = "Channel"

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.logger = get_import_logger(import_id=import_id, collection=Collections.CHANNEL)

    def convert(self, json_entity: Dict[str, Any]) -> ChannelIn:
        external_id = self._get_external_id(json_entity)

        channel_name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )

        channel_description = self._get_optional_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_DESCRIPTION_FIELD
        ) or channel_name

        channel = ChannelIn(type=channel_name, description=channel_description)

        additional_properties = self._set_common_properties(json_entity, channel)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DESCRIPTION_FIELD)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)
        channel.additional_properties = additional_properties
        if DEBUG:
            print(
                f"📝 Creating ChannelIn: channel_name='{channel_name}', description='{channel_description}', external_id='{channel.external_id}', import_job_id='{channel.import_job_id}', properties={len(additional_properties)} (including common)")
        return channel

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> str:
        grisera_object = self.convert(json_entity)

        if grisera_object.external_id:
            existing_id = self.find_by_source_id(grisera_object.external_id, dataset_id)
            if existing_id:
                self.logger.log_info(f"✅ Channel found by external_id: {grisera_object.external_id} -> {existing_id}")
                return existing_id

        existing_id = self._find_existing_channel_by_type_and_description(
            grisera_object.type,
            grisera_object.description,
            dataset_id
        )
        if existing_id:
            self.logger.log_info(
                f"✅ Channel found by type and description: {grisera_object.type}, {grisera_object.description} -> {existing_id}")
            self._update_channel_external_id(existing_id, grisera_object.external_id, dataset_id)
            return existing_id

        self.logger.log_info(f"📝 Creating new Channel: {grisera_object.type}")
        return self.services.get_channel_service().save_channel(grisera_object, dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.CHANNEL)

    def _find_existing_channel_by_type_and_description(self, channel_type: str, channel_description: str, dataset_id: str) -> str:
        """Znajduje Channel po krotce (type, description) case-insensitive"""
        try:
            query_filter = {
                "type": {"$regex": f"^{re.escape(channel_type)}$", "$options": "i"},
                "description": {"$regex": f"^{re.escape(channel_description)}$", "$options": "i"}
            }
            channels = self.mongo_api_service.get_documents(
                collection_name=Collections.CHANNEL.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if channels:
                existing_id = str(channels[0].get("id", ""))
                self.logger.log_info(
                    f"🔍 Found existing Channel by type and description: {channel_type}, {channel_description} (ID: {existing_id})")
                return existing_id

            return ""
        except Exception as e:
            self.logger.log_info(f"❌ Error finding Channel by type and description: {e}")
            return ""

    def _update_channel_external_id(self, channel_id: str, external_id: str, dataset_id: str):
        """Aktualizuje external_id w istniejącym Channel"""
        try:
            channel_doc = self.mongo_api_service.get_document(
                channel_id,
                Collections.CHANNEL.value,
                dataset_id
            )

            if channel_doc and not channel_doc.get("external_id"):
                channel_doc["external_id"] = external_id
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.CHANNEL.value,
                    id=channel_id,
                    new_document=channel_doc,
                    dataset_id=dataset_id
                )
                self.logger.log_info(f"🔗 Updated Channel {channel_id} with external_id: {external_id}")
        except Exception as e:
            self.logger.log_info(f"❌ Error updating Channel external_id: {e}")
