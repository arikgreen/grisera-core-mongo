from enum import Enum
from typing import Dict, List
from mongo_service.collection_mapping import Collections


class EntityTypeMapping(Enum):
    """Mapowanie typów encji JSON na kolekcje MongoDB i kolejność importu"""

    # Kolejność od najmniej powiązanych do najbardziej powiązanych (analiza rzeczywistych danych)
    # Poziom 1: Typy podstawowe bez zależności
    MEASURE_NAME = ("MeasureName", Collections.MEASURE_NAME.value, 1, False)  # "measure_names"
    ACTIVITY = ("Activity", Collections.ACTIVITY.value, 2, True)  # "activities" - BASIC TYPE
    CHANNEL = ("Channel", Collections.CHANNEL.value, 3, False)  # "channels"
    MODALITY = ("Modality", Collections.MODALITY.value, 4, False)  # "modalities"
    LIFE_ACTIVITY = ("LifeActivity", Collections.LIFE_ACTIVITY.value, 5, False)  # "life_activities"

    # Poziom 2: Typy z podstawowymi zależnościami
    MEASURE = ("Measure", Collections.MEASURE.value, 6, False)  # "measures" - zależy od MeasureName
    REGISTERED_DATA = ("RegisteredData", Collections.REGISTERED_DATA.value, 7, False)  # "registered_data"
    APPEARANCE = ("Appearance", Collections.APPEARANCE.value, 8, False)  # "appearances"
    APPERANCE_OCCLUSION_MODEL = ("ApperanceOcclusionModel", Collections.APPEARANCE.value, 8, False)  # "appearances" - literówka z JSON
    PERSONALITY = ("Personality", Collections.PERSONALITY.value, 9, False)  # "personalities"
    ARRANGEMENT = ("Arrangement", Collections.ARRANGEMENT.value, 10, False)  # "arrangements"

    # Poziom 3: Typy z średnimi zależnościami
    PARTICIPANT = ("Participant", Collections.PARTICIPANT.value, 11, True)  # "participants" - BASIC TYPE
    REGISTERED_CHANNEL = ("RegisteredChannel", Collections.REGISTERED_CHANNEL.value, 12, False)  # "registered_channels"
    EXPERIMENT = ("Experiment", Collections.EXPERIMENT.value, 13, False)  # "experiments"

    # Poziom 4: Typy z wyższymi zależnościami
    PARTICIPANT_STATE = ("ParticipantState", Collections.PARTICIPANT_STATE.value, 14, False)  # "participant_states"
    ACTIVITY_EXECUTION = ("ActivityExecution", Collections.ACTIVITY_EXECUTION.value, 15, False)  # "activity_executions"

    # Poziom 5: Typy z najwyższymi zależnościami
    PARTICIPATION = ("Participation", Collections.PARTICIPATION.value, 16, False)  # "participations"
    RECORDING = ("Recording", Collections.RECORDING.value, 17, False)  # "recordings"
    OBSERVABLE_INFORMATION = ("ObservableInformation", Collections.OBSERVABLE_INFORMATION.value, 18, False)  # "observable_informations"
    TIME_SERIES = ("TimeSeries", Collections.TIME_SERIES.value, 19, False)  # "timeSeries" (camelCase!)

    # Typy OWL Ontology - ignorowane podczas importu (nie są encjami GRISERA)
    OWL_ONTOLOGY = ("owl:Ontology", None, 0, False)  # Metadane ontologii - ignorowane
    PC_PROPERTY = ("pc:Property", None, 0, False)  # Właściwości - ignorowane
    OWL_NAMED_INDIVIDUAL = ("owl:NamedIndividual", None, 0, False)  # Instancje - ignorowane

    def __init__(self, json_name: str, collection_name: str, import_order: int, is_basic_type: bool):
        self.json_name = json_name
        self.collection_name = collection_name
        self.import_order = import_order
        self.is_basic_type = is_basic_type

    @classmethod
    def get_mapping_dict(cls) -> Dict[str, 'EntityTypeMapping']:
        """Zwraca słownik mapowania json_name -> EntityTypeMapping"""
        return {entity.json_name: entity for entity in cls}

    @classmethod
    def get_import_order(cls) -> List['EntityTypeMapping']:
        """Zwraca encje posortowane według kolejności importu"""
        return sorted(cls, key=lambda x: x.import_order)

    @classmethod
    def find_mapping_by_normalized_name(cls, normalized_name: str) -> 'EntityTypeMapping':
        """Znajduje mapowanie na podstawie znormalizowanej nazwy (bez prefiksu)"""
        mapping_dict = cls.get_mapping_dict()
        return mapping_dict.get(normalized_name)

    @classmethod
    def get_basic_types(cls) -> set:
        """
        Zwraca podstawowe typy encji, które nie wymagają automatycznego tworzenia eksperymentu.
        Te typy mogą występować samodzielnie bez konieczności tworzenia eksperymentu.
        
        Returns:
            set: Zbiór nazw podstawowych typów encji
        """
        return {entity.json_name for entity in cls if entity.is_basic_type}

    @classmethod
    def get_ignored_types(cls) -> set:
        """
        Zwraca typy encji, które są ignorowane podczas importu (np. typy OWL Ontology).
        
        Returns:
            set: Zbiór nazw ignorowanych typów encji
        """
        return {entity.json_name for entity in cls if entity.collection_name is None}

    @classmethod
    def is_ignored_type(cls, entity_type: str) -> bool:
        """
        Sprawdza czy dany typ encji jest ignorowany podczas importu.
        
        Args:
            entity_type: Nazwa typu encji
            
        Returns:
            bool: True jeśli typ jest ignorowany
        """
        return entity_type in cls.get_ignored_types() 