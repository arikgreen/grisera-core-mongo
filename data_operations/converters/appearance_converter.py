from typing import Dict, Any, Optional
from grisera import AppearanceOcclusionIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections


class AppearanceConverter(BaseEntityConverter[AppearanceOcclusionIn]):
    JSON_KEY_CANDIDATES_FOR_BEARD = ["hasBeardValue", "beard", "beardValue"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_MOUSTACHE = ["hasMoustacheValue", "moustache", "moustacheValue"]  # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_GLASSES = ["hasGlasses", "glasses"]  # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "Appearance"
    
    def convert(self, json_entity: Dict[str, Any]) -> AppearanceOcclusionIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij beard - może być zagnieżdżony obiekt
        beard = self._extract_beard_from_json(json_entity)
        
        # Wyciągnij moustache - może być zagnieżdżony obiekt  
        moustache = self._extract_moustache_from_json(json_entity)
        
        # Wyciągnij glasses - może być zagnieżdżony obiekt  
        glasses = self._extract_glasses_from_json(json_entity)
        
        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        if DEBUG:
            print(f"📝 Creating AppearanceOcclusionIn: name='{clean_name_for_log}', beard='{beard}', moustache='{moustache}', glasses='{glasses}', external_id='{external_id}'")
        
        return AppearanceOcclusionIn(
            beard=beard,
            moustache=moustache,
            glasses=glasses,
            external_id=external_id
        )
    
    def _extract_beard_from_json(self, json_entity: Dict[str, Any]) -> str:
        """
        Wyciąga beard z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_beard = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_BEARD)
        if simple_beard:
            if DEBUG:
                print(f"✅ Found simple beard: {simple_beard}")
            return self._map_beard_value(simple_beard)
        
        # Następnie sprawdź zagnieżdżone obiekty
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_BEARD:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    beard_value = self._extract_nested_entity_id(entity_value)
                    if beard_value:
                        if DEBUG:
                            print(f"✅ Found beard from {entity_key_with_prefix}: {beard_value}")
                        return self._map_beard_value(beard_value)
        
        if DEBUG:
            print("⚠️ No beard found in Appearance, using default: 'no'")
        return "no"
    
    def _extract_moustache_from_json(self, json_entity: Dict[str, Any]) -> str:
        """
        Wyciąga moustache z JSON, obsługuje zagnieżdżone obiekty.
        """
        # Najpierw sprawdź proste przypadki
        simple_moustache = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_MOUSTACHE)
        if simple_moustache:
            if DEBUG:
                print(f"✅ Found simple moustache: {simple_moustache}")
            return self._map_moustache_value(simple_moustache)
        
        # Następnie sprawdź zagnieżdżone obiekty
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_MOUSTACHE:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    moustache_value = self._extract_nested_entity_id(entity_value)
                    if moustache_value:
                        if DEBUG:
                            print(f"✅ Found moustache from {entity_key_with_prefix}: {moustache_value}")
                        return self._map_moustache_value(moustache_value)
        
        if DEBUG:
            print("⚠️ No moustache found in Appearance, using default: 'no'")
        return "no"
    
    def _extract_glasses_from_json(self, json_entity: Dict[str, Any]) -> bool:
        """
        Wyciąga glasses z JSON.
        """
        glasses_value = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_GLASSES)
        if glasses_value is not None:
            if DEBUG:
                print(f"✅ Found glasses: {glasses_value}")
            return str(glasses_value).lower() == "true"
        
        if DEBUG:
            print("⚠️ No glasses found in Appearance, using default: False")
        return False
    
    def _map_beard_value(self, beard_value: str) -> str:
        """
        Mapuje wartość beard z JSON na enum FacialHair.
        """
        beard_lower = beard_value.lower()
        if "heavy" in beard_lower:
            return "Heavy"
        elif "some" in beard_lower:
            return "Some"
        elif "no" in beard_lower or "none" in beard_lower:
            return "None"
        else:
            if DEBUG:
                print(f"⚠️ Unknown beard value: {beard_value}, using default: 'None'")
            return "None"
    
    def _map_moustache_value(self, moustache_value: str) -> str:
        """
        Mapuje wartość moustache z JSON na enum FacialHair.
        """
        moustache_lower = moustache_value.lower()
        if "heavy" in moustache_lower:
            return "Heavy"
        elif "some" in moustache_lower:
            return "Some"
        elif "no" in moustache_lower or "none" in moustache_lower:
            return "None"
        else:
            if DEBUG:
                print(f"⚠️ Unknown moustache value: {moustache_value}, using default: 'None'")
            return "None"

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> AppearanceOcclusionIn:
        return self.convert(json_entity)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.APPEARANCE)


