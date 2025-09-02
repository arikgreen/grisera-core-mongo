"""
DataFetchService - serwis odpowiedzialny tylko za pobieranie danych z MongoDB.
Deleguje pobieranie do specjalistycznych helperów, które obsługują zagnieżdżone kolekcje.
"""

from typing import Dict, Any, List, Optional
from .helpers import (
    TimeSeriesJsonLdHelper,
    ParticipantJsonLdHelper,
    ParticipantStateJsonLdHelper,
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
    AppearanceJsonLdHelper,
    ExperimentJsonLdHelper,
)


class DataFetchService:
    """
    Serwis odpowiedzialny za pobieranie danych z MongoDB dla eksportu JSON-LD.
    Deleguje pobieranie do specjalistycznych helperów.
    """
    
    def __init__(self):
        self.helpers = {
            "TimeSeries": TimeSeriesJsonLdHelper(),
            "Participant": ParticipantJsonLdHelper(),
            "ParticipantState": ParticipantStateJsonLdHelper(),
            "ObservableInformation": ObservableInformationJsonLdHelper(),
            "Recording": RecordingJsonLdHelper(),
            "Measure": MeasureJsonLdHelper(),
            "Activity": ActivityJsonLdHelper(),
            "ActivityExecution": ActivityExecutionJsonLdHelper(),
            "Participation": ParticipationJsonLdHelper(),
            "RegisteredChannel": RegisteredChannelJsonLdHelper(),
            "RegisteredData": RegisteredDataJsonLdHelper(),
            "Channel": ChannelJsonLdHelper(),
            "Modality": ModalityJsonLdHelper(),
            "LifeActivity": LifeActivityJsonLdHelper(),
            "Arrangement": ArrangementJsonLdHelper(),
            "Appearance": AppearanceJsonLdHelper(),
            "Experiment": ExperimentJsonLdHelper(),
        }
        print(f"🔍 DataFetchService initialized with {len(self.helpers)} helpers")
    
    def fetch_entities_by_dataset_id(self, dataset_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Pobiera wszystkie encje dla danego dataset_id, grupując po typach.
        Deleguje pobieranie do specjalistycznych helperów.
        
        Args:
            dataset_id: ID datasetu
            
        Returns:
            Słownik gdzie klucz to typ encji, wartość to lista dokumentów
        """
        print(f"🔍 Fetching all entities for dataset ID: {dataset_id} using helpers")
        
        entities_by_type = {}
        
        # Iteruj przez wszystkie dostępne helpery
        for entity_type, helper in self.helpers.items():
            print(f"🔍 Fetching {entity_type} entities using {helper.__class__.__name__}...")
            
            try:
                entities = helper.fetch_entities(dataset_id)
                if entities:
                    entities_by_type[entity_type] = entities
                    print(f"✅ Found {len(entities)} {entity_type} entities")
                else:
                    print(f"ℹ️ No {entity_type} entities found")
                    
            except Exception as e:
                print(f"❌ Error fetching {entity_type} entities: {str(e)}")
                continue
        
        total_entities = sum(len(entities) for entities in entities_by_type.values())
        print(f"✅ Total entities fetched: {total_entities} across {len(entities_by_type)} types")
        
        return entities_by_type
    
    def fetch_entities_by_type(self, dataset_id: str, entity_type: str) -> List[Dict[str, Any]]:
        """
        Pobiera encje konkretnego typu dla danego dataset_id.
        Deleguje do odpowiedniego helpera.
        
        Args:
            dataset_id: ID datasetu
            entity_type: Typ encji (np. 'TimeSeries', 'Participant')
            
        Returns:
            Lista dokumentów encji z MongoDB
        """
        print(f"🔍 Fetching {entity_type} entities for dataset ID: {dataset_id}")
        
        if entity_type not in self.helpers:
            print(f"⚠️ No helper available for entity type: {entity_type}")
            return []
        
        helper = self.helpers[entity_type]
        return helper.fetch_entities(dataset_id)
    

    
    def get_supported_entity_types(self) -> List[str]:
        """
        Zwraca listę wszystkich obsługiwanych typów encji.
        
        Returns:
            Lista typów encji
        """
        return list(self.helpers.keys())
    
    def health_check(self) -> Dict[str, Any]:
        """
        Health check dla serwisu pobierania danych.
        
        Returns:
            Status serwisu
        """
        try:
            return {
                "status": "healthy",
                "service": "data_fetch",
                "message": "Data fetch service is running with helpers",
                "supported_entity_types": len(self.helpers),
                "available_helpers": list(self.helpers.keys())
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "data_fetch", 
                "error": str(e)
            }
