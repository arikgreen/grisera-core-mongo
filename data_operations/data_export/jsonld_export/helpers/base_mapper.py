from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.collection_mapping import Collections
from data_operations.entity_type_mapping import EntityTypeMapping

DEBUG=True

class BaseJsonLdHelper(ABC):
    """
    Abstrakcyjna klasa bazowa dla helperów JSON-LD.
    Każdy helper odpowiada za pobieranie danych i mapowanie jednego typu encji.
    """
    
    def __init__(self):
        self.entity_type = self._get_entity_type()
        self.mongo_api_service = MongoApiService()
        
    @abstractmethod
    def _get_entity_type(self) -> str:
        """Zwraca typ encji obsługiwany przez ten mapper (np. 'TimeSeries', 'Participant')"""
        pass
        
    @abstractmethod
    def get_jsonld_collection_key(self) -> str:
        """Zwraca klucz kolekcji w JSON-LD (np. 'co:TimeSeries', 'co:Participant')"""
        pass
    
    @abstractmethod
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera encje tego typu dla danego dataset_id z MongoDB.
        Każdy helper implementuje własną logikę pobierania (w tym zagnieżdżone kolekcje).
        
        Args:
            dataset_id: ID datasetu
            
        Returns:
            Lista dokumentów encji z MongoDB
        """
        pass
    
    @abstractmethod
    def get_collection_enum(self) -> Collections:
        """
        Zwraca enum kolekcji MongoDB dla tego typu encji.
        Każdy helper musi zdefiniować swoją kolekcję.
        
        Returns:
            Enum kolekcji z Collections
        """
        pass
    
    @abstractmethod
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapuje dokument encji z MongoDB na strukturę JSON.
        
        Args:
            entity_doc: Dokument encji z MongoDB
            
        Returns:
            Zmapowana struktura JSON dla tej encji
        """
        pass
    
    def _extract_entity_id(self, entity_doc: Dict[str, Any]) -> str:
        """
        Wyciąga ID encji z dokumentu MongoDB.
        """
        try:
            if "id" in entity_doc:
                return str(entity_doc['id'])
            if "_id" in entity_doc:
                return str(entity_doc['_id'])
            else:
                return f"unknown_{self.entity_type}"
        except Exception as e:
            print(f"❌ [DEBUG] Error in _extract_entity_id: {str(e)}")
            print(f"❌ [DEBUG] Entity doc: {entity_doc}")
            return f"error_{self.entity_type}"

    def _create_basic_json_structure(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tworzy podstawową strukturę JSON z id i type.
        Każdy helper może to rozszerzyć o specyficzne pola.
        """
        if DEBUG:
            print(f"🔍 [DEBUG] _create_basic_json_structure - Full entity_doc: {entity_doc}")
        
        entity_id = self._extract_entity_id(entity_doc)
        
        return {
            "@id": entity_id
        }
    
    def _get_collection_name_for_entity_type(self, entity_type: str) -> Optional[str]:
        """
        Pobiera nazwę kolekcji MongoDB dla danego typu encji.
        Wykorzystuje EntityTypeMapping.
        
        Args:
            entity_type: Typ encji
            
        Returns:
            Nazwa kolekcji MongoDB lub None
        """
        try:
            entity_mapping = EntityTypeMapping.find_mapping_by_normalized_name(entity_type)
            if entity_mapping and entity_mapping.collection_name:
                return entity_mapping.collection_name
            return None
        except Exception as e:
            print(f"❌ Error getting collection name for {entity_type}: {str(e)}")
            return None
    
    def _fetch_entities_from_collection(self, dataset_id: str, collection_name: str) -> List[Dict[str, Any]]:
        """
        Podstawowa metoda pobierania encji z kolekcji MongoDB.
        Może być używana przez konkretne helpery jako punkt startowy.
        
        Args:
            dataset_id: ID datasetu
            collection_name: Nazwa kolekcji MongoDB
            
        Returns:
            Lista dokumentów z MongoDB
        """
        try:
            query_filter = {"dataset_id": dataset_id}
            entities = self.mongo_api_service.find(collection_name, query_filter)
            return list(entities) if entities else []
        except Exception as e:
            print(f"❌ Error fetching from collection {collection_name}: {str(e)}")
            return []
    
    def _fetch_entities_from_collection_enum(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera encje z kolekcji MongoDB używając enum kolekcji.
        Prosta implementacja dla helperów z jedną kolekcją.
        
        Args:
            dataset_id: ID datasetu
            
        Returns:
            Lista dokumentów z MongoDB
        """
        try:
            collection_enum = self.get_collection_enum()
            return self.mongo_api_service.get_documents(
                collection_name=collection_enum.value,
                dataset_id=dataset_id
            )
        except Exception as e:
            print(f"❌ Error fetching from collection {self.get_collection_enum().value}: {str(e)}")
            return []


    def _create_id_object(self, value: str) -> Dict[str, str]:
        """
        Tworzy obiekt @id dla pól które zawsze mają strukturę @id.

        Args:
            value: Wartość pola (np. "68b6181ca79cd150f0ef9fb4")

        Returns:
            Obiekt z @id (np. {"@id": "co:68b6181ca79cd150f0ef9fb4"})
        """
        if not value:
            return None

        return {"@id": f"{value}"}