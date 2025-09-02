"""
JsonLdExportOrchestrator - główny orchestrator koordynujący cały proces eksportu JSON-LD.
"""

import json
from typing import Dict, Any, Optional
from data_operations.file_operations_model import FileOperationIn
from .data_fetch_service import DataFetchService
from .structure_builder import JsonLdStructureBuilder
from .mapper_registry import get_helper_registry


class JsonLdExportOrchestrator:
    """
    Główny orchestrator koordynujący cały proces eksportu JSON-LD.
    Zarządza przepływem danych między różnymi serwisami.
    """
    
    def __init__(self):
        self.data_fetch_service = DataFetchService()
        self.structure_builder = JsonLdStructureBuilder()
        self.helper_registry = get_helper_registry()
        print("🎭 JsonLdExportOrchestrator initialized")
    
    def export_dataset_to_jsonld(self, export_request: FileOperationIn) -> Dict[str, Any]:
        """
        Główna metoda eksportująca dataset do formatu JSON-LD.
        
        Args:
            export_request: Żądanie eksportu (FileOperationIn)
            
        Returns:
            Wynik eksportu z danymi JSON-LD lub błędami
        """
        dataset_id = export_request.dataset_id
        print(f"🎭 Starting JSON export for dataset: {dataset_id}")
        
        export_result = {
            "success": False,
            "dataset_id": dataset_id,
            "export_type": "json",
            "data": None,
            "statistics": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # Krok 1: Pobierz dane z MongoDB
            print("📥 Step 1: Fetching data from MongoDB...")
            entities_by_type = self.data_fetch_service.fetch_entities_by_dataset_id(dataset_id)
            
            if not entities_by_type:
                export_result["errors"].append("No entities found for dataset")
                print("⚠️ No entities found for dataset")
                return export_result
            
            print(f"✅ Step 1 completed: {len(entities_by_type)} entity types fetched")
            
            # Krok 2: Zbuduj strukturę JSON
            print("🏗️ Step 2: Building JSON structure...")
            json_structure = self.structure_builder.build_json_structure(entities_by_type)
            
            print("✅ Step 2 completed: JSON structure built")
            
            # Krok 3: Waliduj strukturę
            print("🔍 Step 3: Validating JSON structure...")
            validation_result = self.structure_builder.validate_structure(json_structure)

            print("📦 Step 4: Preparing export results...")
            export_result["success"] = True
            export_result["data"] = json_structure
            export_result["statistics"] = validation_result["statistics"]
            
            print(f"✅ JSON export completed successfully:")
            print(f"   - Total entities: {export_result['statistics'].get('total_entities', 0)}")
            print(f"   - Entity sections: {len(export_result['statistics'].get('entity_sections', []))}")
            
            return export_result
            
        except Exception as e:
            error_msg = f"Export orchestration error: {str(e)}"
            export_result["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            return export_result
    
    def export_specific_entity_types(
        self, 
        dataset_id: str, 
        entity_types: list[str]
    ) -> Dict[str, Any]:
        """
        Eksportuje tylko wybrane typy encji dla danego datasetu.
        
        Args:
            dataset_id: ID datasetu
            entity_types: Lista typów encji do eksportu
            
        Returns:
            Wynik eksportu
        """
        print(f"🎭 Starting selective JSON export for dataset: {dataset_id}")
        print(f"🎯 Target entity types: {entity_types}")
        
        export_result = {
            "success": False,
            "dataset_id": dataset_id,
            "export_type": "json-selective",
            "target_entity_types": entity_types,
            "data": None,
            "statistics": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # Waliduj typy encji
            unsupported_types = []
            for entity_type in entity_types:
                if not self.helper_registry.is_supported_entity_type(entity_type):
                    unsupported_types.append(entity_type)
            
            if unsupported_types:
                export_result["errors"].append(f"Unsupported entity types: {unsupported_types}")
                return export_result
            
            # Pobierz dane tylko dla wybranych typów
            entities_by_type = {}
            for entity_type in entity_types:
                print(f"📥 Fetching {entity_type} entities...")
                entities = self.data_fetch_service.fetch_entities_by_type(dataset_id, entity_type)
                if entities:
                    entities_by_type[entity_type] = entities
            
            if not entities_by_type:
                export_result["warnings"].append("No entities found for selected types")
                # Ale nie traktuj tego jako błąd - zwróć pustą strukturę
            
            # Zbuduj strukturę JSON
            json_structure = self.structure_builder.build_json_structure(entities_by_type)
            
            # Waliduj i zwróć wyniki
            validation_result = self.structure_builder.validate_structure(json_structure)
            
            export_result["success"] = True
            export_result["data"] = json_structure
            export_result["statistics"] = validation_result["statistics"]
            export_result["warnings"].extend(validation_result["warnings"])
            
            if validation_result["errors"]:
                export_result["errors"].extend(validation_result["errors"])
            
            print(f"✅ Selective JSON export completed")
            return export_result
            
        except Exception as e:
            error_msg = f"Selective export error: {str(e)}"
            export_result["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            return export_result
    
    def get_export_preview(self, dataset_id: str, limit_per_type: int = 5) -> Dict[str, Any]:
        """
        Tworzy podgląd eksportu z ograniczoną liczbą encji każdego typu.
        
        Args:
            dataset_id: ID datasetu
            limit_per_type: Maksymalna liczba encji każdego typu
            
        Returns:
            Podgląd eksportu
        """
        print(f"👀 Creating export preview for dataset: {dataset_id} (limit: {limit_per_type})")
        
        try:
            # TODO: Implement preview logic with limits
            # Na razie zwracamy pełny eksport - w przyszłości dodamy limitowanie
            
            preview_request = FileOperationIn(
                dataset_id=dataset_id,
                file_name=f"preview_{dataset_id}.jsonld",
                file_type="json-ld"
            )
            
            result = self.export_dataset_to_jsonld(preview_request)
            result["is_preview"] = True
            result["limit_per_type"] = limit_per_type
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Preview generation error: {str(e)}"
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Health check dla orchestratora.
        
        Returns:
            Status orchestratora i wszystkich zależności
        """
        try:
            # Sprawdź wszystkie zależne serwisy
            data_fetch_health = self.data_fetch_service.health_check()
            
            return {
                "status": "healthy",
                "service": "jsonld_export_orchestrator",
                "message": "Orchestrator is running",
                "dependencies": {
                    "data_fetch_service": data_fetch_health["status"],
                    "structure_builder": "available",
                    "helper_registry": "available"
                },
                "supported_entity_types": len(self.helper_registry.get_supported_entity_types())
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "jsonld_export_orchestrator",
                "error": str(e)
            }
