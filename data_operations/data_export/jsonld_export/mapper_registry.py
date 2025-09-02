"""
Registry mapperów JSON-LD - centralna klasa zarządzająca wszystkimi mapperami.
"""

from typing import Dict, Type, Optional
from .helpers import (
    BaseJsonLdHelper,
    TimeSeriesJsonLdHelper,
    ParticipantJsonLdHelper,
    ObservableInformationJsonLdHelper,
    RecordingJsonLdHelper,
    MeasureJsonLdHelper,
    ActivityJsonLdHelper,
    ActivityExecutionJsonLdHelper,
    ParticipationJsonLdHelper,
    RegisteredChannelJsonLdHelper,
    RegisteredDataJsonLdHelper,
    ChannelJsonLdHelper,
    ModalityJsonLdHelper,
    LifeActivityJsonLdHelper,
    ArrangementJsonLdHelper,
    ParticipantStateJsonLdHelper,
    AppearanceJsonLdHelper,
    ExperimentJsonLdHelper,
)


class JsonLdHelperRegistry:
    """
    Centralna klasa zarządzająca wszystkimi mapperami JSON-LD.
    Odpowiada za rejestrację, wyszukiwanie i tworzenie instancji mapperów.
    """
    
    def __init__(self):
        """Inicjalizuje registry z domyślnymi mapperami"""
        self._helpers: Dict[str, Type[BaseJsonLdHelper]] = {}
        self._mapper_instances: Dict[str, BaseJsonLdHelper] = {}
        self._register_default_helpers()
        
    def _register_default_helpers(self):
        """Rejestruje wszystkie standardowe mappery"""
        default_helpers = [
            TimeSeriesJsonLdHelper,
            ParticipantJsonLdHelper,
            ObservableInformationJsonLdHelper,
            RecordingJsonLdHelper,
            MeasureJsonLdHelper,
            ActivityJsonLdHelper,
            ActivityExecutionJsonLdHelper,
            ParticipationJsonLdHelper,
            RegisteredChannelJsonLdHelper,
            RegisteredDataJsonLdHelper,
            ChannelJsonLdHelper,
            ModalityJsonLdHelper,
            LifeActivityJsonLdHelper,
            ArrangementJsonLdHelper,
            ParticipantStateJsonLdHelper,
            AppearanceJsonLdHelper,
            ExperimentJsonLdHelper,
        ]
        
        for mapper_class in default_helpers:
            # Tworzymy tymczasową instancję żeby pobrać entity_type
            temp_mapper = mapper_class()
            entity_type = temp_mapper.entity_type
            self._helpers[entity_type] = mapper_class
            
        print(f"🗂️ JsonLdHelperRegistry initialized with {len(self._helpers)} helpers:")
        for entity_type in self._helpers.keys():
            print(f"   - {entity_type}")
    
    def register_mapper(self, entity_type: str, mapper_class: Type[BaseJsonLdHelper]):
        """
        Rejestruje nowy mapper dla danego typu encji.
        
        Args:
            entity_type: Typ encji (np. 'TimeSeries', 'Participant')
            mapper_class: Klasa mappera
        """
        self._helpers[entity_type] = mapper_class
        # Wyczyść cached instance jeśli istnieje
        if entity_type in self._mapper_instances:
            del self._mapper_instances[entity_type]
        print(f"📝 Registered mapper for entity type: {entity_type}")
    
    def get_mapper(self, entity_type: str) -> Optional[BaseJsonLdHelper]:
        """
        Pobiera mapper dla danego typu encji.
        Używa cache'owania instancji.
        
        Args:
            entity_type: Typ encji (np. 'TimeSeries', 'Participant')
            
        Returns:
            Instance mappera lub None jeśli nie znaleziono
        """
        if entity_type not in self._helpers:
            print(f"⚠️ No mapper found for entity type: {entity_type}")
            return None
            
        # Sprawdź cache
        if entity_type in self._mapper_instances:
            return self._mapper_instances[entity_type]
            
        # Utwórz nową instancję i zapisz w cache
        mapper_class = self._helpers[entity_type]
        mapper_instance = mapper_class()
        self._mapper_instances[entity_type] = mapper_instance
        
        return mapper_instance
    
    def get_collection_key(self, entity_type: str) -> Optional[str]:
        """
        Pobiera klucz kolekcji JSON-LD dla danego typu encji.
        
        Args:
            entity_type: Typ encji
            
        Returns:
            Klucz kolekcji (np. 'co:TimeSeries') lub None
        """
        mapper = self.get_mapper(entity_type)
        if mapper:
            return mapper.get_jsonld_collection_key()
        return None
    
    def get_supported_entity_types(self) -> list[str]:
        """
        Zwraca listę wszystkich obsługiwanych typów encji.
        
        Returns:
            Lista typów encji
        """
        return list(self._helpers.keys())
    
    def is_supported_entity_type(self, entity_type: str) -> bool:
        """
        Sprawdza czy dany typ encji jest obsługiwany.
        
        Args:
            entity_type: Typ encji
            
        Returns:
            True jeśli typ jest obsługiwany
        """
        return entity_type in self._helpers


# Globalna instancja registry (singleton pattern)
_global_registry: Optional[JsonLdHelperRegistry] = None


def get_helper_registry() -> JsonLdHelperRegistry:
    """
    Zwraca globalną instancję JsonLdHelperRegistry (singleton).
    
    Returns:
        Globalna instancja registry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = JsonLdHelperRegistry()
    return _global_registry
