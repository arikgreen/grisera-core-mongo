"""
ExportServiceFactory - factory do tworzenia skonfigurowanych instancji serwisów eksportu JSON-LD.
"""

from typing import Optional, Dict, Any
from .export_orchestrator import JsonLdExportOrchestrator
from .data_fetch_service import DataFetchService
from .structure_builder import JsonLdStructureBuilder
from .mapper_registry import JsonLdHelperRegistry, get_helper_registry


class ExportServiceFactory:
    """
    Factory do tworzenia skonfigurowanych instancji serwisów eksportu JSON-LD.
    Umożliwia centralne zarządzanie konfiguracją i zależnościami.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicjalizuje factory z opcjonalną konfiguracją.
        
        Args:
            config: Opcjonalna konfiguracja factory
        """
        self.config = config or {}
        self._orchestrator_instance: Optional[JsonLdExportOrchestrator] = None
        self._data_fetch_service_instance: Optional[DataFetchService] = None
        self._structure_builder_instance: Optional[JsonLdStructureBuilder] = None
        self._helper_registry_instance: Optional[JsonLdHelperRegistry] = None
        
        print(f"🏭 ExportServiceFactory initialized with config: {self.config}")
    
    def create_orchestrator(self, force_new: bool = False) -> JsonLdExportOrchestrator:
        """
        Tworzy lub zwraca orchestrator eksportu JSON-LD.
        
        Args:
            force_new: Jeśli True, zawsze tworzy nową instancję
            
        Returns:
            Skonfigurowana instancja orchestratora
        """
        if self._orchestrator_instance is None or force_new:
            print("🏭 Creating new JsonLdExportOrchestrator instance")
            self._orchestrator_instance = JsonLdExportOrchestrator()
        
        return self._orchestrator_instance
    
    def create_data_fetch_service(self, force_new: bool = False) -> DataFetchService:
        """
        Tworzy lub zwraca serwis pobierania danych.
        
        Args:
            force_new: Jeśli True, zawsze tworzy nową instancję
            
        Returns:
            Skonfigurowana instancja serwisu
        """
        if self._data_fetch_service_instance is None or force_new:
            print("🏭 Creating new DataFetchService instance")
            self._data_fetch_service_instance = DataFetchService()
        
        return self._data_fetch_service_instance
    
    def create_structure_builder(self, force_new: bool = False) -> JsonLdStructureBuilder:
        """
        Tworzy lub zwraca builder struktury JSON-LD.
        
        Args:
            force_new: Jeśli True, zawsze tworzy nową instancję
            
        Returns:
            Skonfigurowana instancja buildera
        """
        if self._structure_builder_instance is None or force_new:
            print("🏭 Creating new JsonLdStructureBuilder instance")
            self._structure_builder_instance = JsonLdStructureBuilder()
        
        return self._structure_builder_instance
    
    def create_helper_registry(self, force_new: bool = False) -> JsonLdHelperRegistry:
        """
        Tworzy lub zwraca registry helperów.
        
        Args:
            force_new: Jeśli True, zawsze tworzy nową instancję
            
        Returns:
            Skonfigurowana instancja registry
        """
        if self._helper_registry_instance is None or force_new:
            print("🏭 Creating new JsonLdHelperRegistry instance")
            self._helper_registry_instance = JsonLdHelperRegistry()
        
        return self._helper_registry_instance
    
    def create_full_export_stack(self) -> JsonLdExportOrchestrator:
        """
        Tworzy kompletny stack eksportu JSON-LD z wszystkimi zależnościami.
        
        Returns:
            Skonfigurowany orchestrator z wszystkimi zależnościami
        """
        print("🏭 Creating full JSON-LD export stack")
        
        # Utwórz wszystkie komponenty
        helper_registry = self.create_helper_registry()
        data_fetch_service = self.create_data_fetch_service()
        structure_builder = self.create_structure_builder()
        orchestrator = self.create_orchestrator()
        
        print("✅ Full JSON-LD export stack created successfully")
        return orchestrator
    
    def health_check_all_services(self) -> Dict[str, Any]:
        """
        Sprawdza status wszystkich serwisów eksportu.
        
        Returns:
            Status wszystkich serwisów
        """
        print("🏭 Running health check on all export services")
        
        health_status = {
            "factory_status": "healthy",
            "services": {},
            "overall_status": "healthy",
            "errors": []
        }
        
        try:
            # Test każdego serwisu
            services_to_test = [
                ("data_fetch_service", self.create_data_fetch_service),
                ("orchestrator", self.create_orchestrator),
            ]
            
            for service_name, service_creator in services_to_test:
                try:
                    service = service_creator()
                    if hasattr(service, 'health_check'):
                        service_health = service.health_check()
                        health_status["services"][service_name] = service_health
                        
                        if service_health.get("status") != "healthy":
                            health_status["overall_status"] = "degraded"
                    else:
                        health_status["services"][service_name] = {"status": "no_health_check"}
                        
                except Exception as e:
                    health_status["services"][service_name] = {
                        "status": "error", 
                        "error": str(e)
                    }
                    health_status["overall_status"] = "unhealthy"
                    health_status["errors"].append(f"{service_name}: {str(e)}")
            
            # Test helper registry
            try:
                registry = get_helper_registry()
                supported_types = len(registry.get_supported_entity_types())
                health_status["services"]["helper_registry"] = {
                    "status": "healthy",
                    "supported_entity_types": supported_types
                }
            except Exception as e:
                health_status["services"]["helper_registry"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall_status"] = "unhealthy"
                health_status["errors"].append(f"helper_registry: {str(e)}")
            
        except Exception as e:
            health_status["factory_status"] = "error"
            health_status["overall_status"] = "unhealthy"
            health_status["errors"].append(f"Factory error: {str(e)}")
        
        print(f"🏭 Health check completed: {health_status['overall_status']}")
        return health_status
    
    def get_factory_info(self) -> Dict[str, Any]:
        """
        Zwraca informacje o factory i jego konfiguracji.
        
        Returns:
            Informacje o factory
        """
        return {
            "factory_type": "ExportServiceFactory",
            "config": self.config,
            "created_instances": {
                "orchestrator": self._orchestrator_instance is not None,
                "data_fetch_service": self._data_fetch_service_instance is not None,
                "structure_builder": self._structure_builder_instance is not None,
                "helper_registry": self._helper_registry_instance is not None,
            },
            "supported_features": [
                "json_ld_export",
                "selective_entity_export", 
                "export_preview",
                "health_monitoring"
            ]
        }


# Globalna instancja factory (singleton pattern)
_global_factory: Optional[ExportServiceFactory] = None


def get_export_service_factory(config: Optional[Dict[str, Any]] = None) -> ExportServiceFactory:
    """
    Zwraca globalną instancję ExportServiceFactory (singleton).
    
    Args:
        config: Opcjonalna konfiguracja (używana tylko przy pierwszym wywołaniu)
        
    Returns:
        Globalna instancja factory
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = ExportServiceFactory(config)
    return _global_factory
