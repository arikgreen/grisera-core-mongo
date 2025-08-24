from datetime import datetime
from typing import Dict, Any, Optional
from grisera import RegisteredChannelIn
from .base import BaseEntityConverter, DEBUG
from .registered_data_converter import RegisteredDataConverter
from .channel_converter import ChannelConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class RegisteredChannelConverter(BaseEntityConverter[RegisteredChannelIn]):
    JSON_KEY_CANDIDATES_FOR_CHANNEL_ID = ["hasChannel", "channel_id"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_REGISTERED_DATA_ID = ["hasRegisteredData", "registered_data_id"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "RegisteredChannel"
    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.registered_data_service = RegisteredDataConverter(import_id)
        self.channel_service = ChannelConverter(import_id)
        self.services = MongoServiceFactory()

    
    def convert(self, json_entity: Dict[str, Any]) -> RegisteredChannelIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij Channel ID z JSON - może być zagnieżdżony obiekt
        channel_id = self._extract_channel_id_from_json(json_entity)
        
        # Wyciągnij RegisteredData ID z JSON - może być zagnieżdżony obiekt  
        registered_data_id = self._extract_registered_data_id_from_json(json_entity)
        
        registered_channel = RegisteredChannelIn(
            channel_id=channel_id,
            registered_data_id=registered_data_id
        )

        additional_properties = self._set_common_properties(json_entity, registered_channel)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_CHANNEL_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_REGISTERED_DATA_ID)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        print(f"📝 Creating RegisteredChannelIn: name='{clean_name_for_log}', channel_id='{channel_id}', registered_data_id='{registered_data_id}', external_id='{registered_channel.external_id}', import_job_id='{registered_channel.import_job_id}', properties={len(additional_properties)} (including common)")

        return registered_channel
    
    def _extract_channel_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Channel ID z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_channel_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_CHANNEL_ID)
        if simple_channel_id:
            print(f"✅ Found simple channel_id: {simple_channel_id}")
            return simple_channel_id
        
        # Następnie sprawdź co:hasChannel (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_CHANNEL_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    channel_source_id = self._extract_nested_entity_id(entity_value)
                    if channel_source_id:
                        print(f"✅ Found Channel source ID from {entity_key_with_prefix}: {channel_source_id}")
                        return channel_source_id
        
        print("⚠️ No Channel reference found in RegisteredChannel")
        return None
    
    def _extract_registered_data_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga RegisteredData ID z JSON z zagnieżdżonej struktury hasRegisteredData.
        """
        # Najpierw sprawdź proste przypadki
        simple_rd_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_REGISTERED_DATA_ID)
        if simple_rd_id:
            print(f"✅ Found simple registered_data_id: {simple_rd_id}")
            return simple_rd_id
        
        # Następnie sprawdź co:hasRegisteredData (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_REGISTERED_DATA_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasRegisteredData - wyciągnij @id RegisteredData
                    registered_data_id = self._extract_nested_entity_id(entity_value)
                    if registered_data_id:
                        print(f"✅ Found RegisteredData ID from {entity_key_with_prefix}: {registered_data_id}")
                        # Zapisujemy RegisteredData ID - mapowanie na MongoDB ID zostanie zrobione później
                        return registered_data_id
        
        print("⚠️ No RegisteredData reference found in RegisteredChannel")
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> RegisteredChannelIn:
        return self._save_registered_channel_with_mapping(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.REGISTERED_CHANNEL)

    def _save_registered_channel_with_mapping(self, grisera_object, dataset_id: str, import_id: str):
            """
            Zapisuje RegisteredChannel z mapowaniem source IDs na MongoDB IDs dla registered_data_id i channel_id.
            """

            try:
                print(f"💾 Saving RegisteredChannel with ID mapping...")

                # KROK 1: Pobierz source_entity_ref z additional_properties (to @id z JSON)
                source_entity_ref = grisera_object.external_id

                if not source_entity_ref:
                    print("⚠️ No source_entity_ref found in RegisteredChannel")
                else:
                    print(f"🔍 RegisteredChannel source ID: {source_entity_ref}")

                # KROK 2: Mapuj registered_data_id z source ID na MongoDB ID
                mapped_registered_data_id = grisera_object.registered_data_id
                if grisera_object.registered_data_id and grisera_object.registered_data_id.startswith(":"):
                    # To jest source ID, mapuj na MongoDB ID
                    registered_data_source_id = grisera_object.registered_data_id
                    registered_data_mongo_id = self.registered_data_service.find_by_source_id(registered_data_source_id,
                                                                                       dataset_id)

                    if registered_data_mongo_id:
                        mapped_registered_data_id = registered_data_mongo_id
                        print(
                            f"✅ Mapped registered_data_id: {grisera_object.registered_data_id} -> {registered_data_mongo_id}")
                    else:
                        print(f"❌ Could not find RegisteredData in MongoDB for source ID: {registered_data_source_id}")
                        self._log_import_error(
                            import_id,
                            dataset_id,
                            "REGISTERED_DATA_NOT_FOUND_FOR_REGISTERED_CHANNEL",
                            f"RegisteredData with source ID '{registered_data_source_id}' not found for RegisteredChannel",
                            source_entity_ref or "unknown"
                        )


                channel_source_id = grisera_object.channel_id
                channel_mongo_id = self.channel_service.find_by_source_id(channel_source_id, dataset_id)

                if channel_mongo_id:
                    mapped_channel_id = channel_mongo_id
                    print(f"✅ Mapped channel_id: {grisera_object.channel_id} -> {channel_mongo_id}")
                else:
                    print(f"⚠️ Could not find Channel in MongoDB for source ID: {channel_source_id}")
                    mapped_channel_id = self._find_or_create_channel_by_type_string(
                        channel_source_id,
                        dataset_id,
                        import_id
                    )

                # KROK 4: Utwórz nowy obiekt RegisteredChannel z mapowanymi IDs
                grisera_object.registered_data_id = mapped_registered_data_id
                grisera_object.channel_id = mapped_channel_id

                print(f"✅ RegisteredChannel grisera_object: {grisera_object.__dict__}")
                result = self.services.get_registered_channel_service().save_registered_channel(grisera_object,
                                                                                                dataset_id)

                saved_registered_channel_id = str(getattr(result, 'id', 'unknown'))
                print(f"✅ RegisteredChannel saved with ID: {saved_registered_channel_id}")

                # KROK 6: Loguj mapowanie dla debugowania
                if mapped_registered_data_id != grisera_object.registered_data_id:
                    print(
                        f"🔗 Final registered_data_id mapping: {grisera_object.registered_data_id} -> {mapped_registered_data_id}")
                if mapped_channel_id != grisera_object.channel_id:
                    print(f"🔗 Final channel_id mapping: {grisera_object.channel_id} -> {mapped_channel_id}")

                return result

            except Exception as e:
                print(f"❌ Error saving RegisteredChannel with mapping: {e}")
                raise e

    def _find_or_create_channel_by_type_string(self, channel_type_string: str, dataset_id: str,
                                               import_id: str = None) -> str:
        """
        Dopasowuje typ kanału z JSON-a (np. 'co:channelAudio') do istniejącego kanału w MongoDB
        i aktualizuje jego external_id. Jeśli nie znajdzie dopasowania, zwraca UUID kanału 'Unknown'.

        Args:
            channel_type_string (str): String z JSON-a (np. 'co:channelAudio')
            dataset_id (str): ID datasetu
            import_id (str): ID importu (opcjonalne, do logowania)

        Returns:
            str: UUID kanału z MongoDB
        """
        from grisera.channel.channel_model import Types

        try:
            # Wyciągnięcie nazwy typu z stringa (np. 'co:channelAudio' -> 'audio')
            if ':' in channel_type_string:
                type_part = channel_type_string.split(':')[-1]  # Bierzemy część po ':'
                if type_part.startswith('channel'):
                    type_name = type_part[7:].lower()  # Usuwamy 'channel' i robimy lowercase
                else:
                    type_name = type_part.lower()
            else:
                type_name = channel_type_string.lower()

            print(f"🔍 Szukam kanału dla typu: '{type_name}' (z: '{channel_type_string}')")

            # Sprawdzamy czy typ pasuje do któregoś z enum Types
            matching_type = None
            for channel_type in Types:
                channel_type_value = channel_type.value[0]  # Pierwszy element tuple to nazwa typu
                if type_name == channel_type_value.lower() or type_name in channel_type_value.lower():
                    matching_type = channel_type_value
                    break

            if matching_type:
                print(f"✅ Znaleziono dopasowanie: '{matching_type}'")

                # Szukamy kanału w MongoDB po typie
                query_filter = {"type": matching_type}
                channels = self.mongo_api_service.get_documents(
                    collection_name=Collections.CHANNEL.value,
                    dataset_id=dataset_id,
                    query=query_filter
                )

                if channels and len(channels) > 0:
                    channel = channels[0]
                    channel_id = str(channel.get("id", ""))

                    # Aktualizujemy external_id
                    if channel_id:
                        print(f"🔄 Aktualizuję external_id dla kanału {channel_id}")

                        # Użyjemy bezpośredniego zapytania MongoDB do częściowej aktualizacji
                        from bson import ObjectId
                        db = self.mongo_api_service.client[dataset_id]

                        update_result = db[Collections.CHANNEL.value].update_one(
                            {"_id": ObjectId(channel_id)},
                            {"$set": {"external_id": channel_type_string}}
                        )

                        if update_result.modified_count > 0:
                            print(f"✅ Zaktualizowano external_id dla kanału {matching_type}")
                        else:
                            print(f"⚠️ Nie udało się zaktualizować external_id dla kanału {matching_type}")

                    return channel_id
                else:
                    print(f"❌ Nie znaleziono kanału typu '{matching_type}' w MongoDB")
            else:
                print(f"❌ Nie udało się dopasować typu '{type_name}' do żadnego z dostępnych typów kanałów")

            # Jeśli nie znaleźliśmy dopasowania, szukamy/tworzymy kanał 'Unknown'
            print("🔍 Szukam kanału 'Unknown'...")

            unknown_query = {"type": "Unknown"}
            unknown_channels = self.mongo_api_service.get_documents(
                collection_name=Collections.CHANNEL.value,
                dataset_id=dataset_id,
                query=unknown_query
            )

            if unknown_channels and len(unknown_channels) > 0:
                unknown_channel_id = str(unknown_channels[0].get("id", ""))
                print(f"✅ Znaleziono istniejący kanał 'Unknown': {unknown_channel_id}")
                return unknown_channel_id
            else:
                print("➕ Tworzę nowy kanał 'Unknown'...")
                from grisera import ChannelIn

                unknown_channel = ChannelIn(
                    type="Unknown",
                    description="Unknown channel type",
                    import_job_id=import_id,
                    import_timestamp=datetime.now(),
                )

                unknown_channel_id = self.services.get_channel_service().save_channel(unknown_channel, dataset_id)

                if hasattr(unknown_channel_id, 'id'):
                    unknown_channel_id = str(unknown_channel_id.id)
                else:
                    unknown_channel_id = str(unknown_channel_id)

                print(f"✅ Utworzono nowy kanał 'Unknown': {unknown_channel_id}")
                return unknown_channel_id

        except Exception as e:
            print(f"❌ Błąd podczas dopasowywania kanału dla '{channel_type_string}': {e}")

            try:
                fallback_channels = self.mongo_api_service.get_documents(
                    collection_name=Collections.CHANNEL.value,
                    dataset_id=dataset_id,
                    query={}
                )

                if fallback_channels and len(fallback_channels) > 0:
                    fallback_id = str(fallback_channels[0].get("id", ""))
                    print(f"🔄 Używam fallback kanału: {fallback_id}")
                    return fallback_id
            except:
                pass

            # Ostatnia deska ratunku - zwróć pusty string
            if import_id:
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "CHANNEL_TYPE_MAPPING_FAILED",
                    f"Nie udało się dopasować ani utworzyć kanału dla typu '{channel_type_string}': {e}",
                    channel_type_string
                )

            return ""