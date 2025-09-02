"""
JsonLdStructureBuilder - serwis składający finalną strukturę JSON-LD.
"""

from typing import Dict, Any, List
from datetime import datetime
from .mapper_registry import get_helper_registry


class JsonLdStructureBuilder:
    """
    Serwis odpowiedzialny za składanie finalnej struktury JSON-LD.
    Tworzy strukturę zgodną z ontologią GRISERA.
    """
    
    def __init__(self):
        self.helper_registry = get_helper_registry()
        print("🏗️ JsonLdStructureBuilder initialized")
    
    def build_json_structure(self, entities_by_type: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Buduje finalną strukturę JSON z pogrupowanych encji.
        
        Args:
            entities_by_type: Słownik encji pogrupowanych po typach
            
        Returns:
            Finalna struktura JSON
        """
        print(f"🏗️ Building JSON structure for {len(entities_by_type)} entity types")
        
        # Inicjalizuj podstawową strukturę JSON
        json_structure = {
            "metadata": {
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_entity_types": len(entities_by_type),
                "entity_types": list(entities_by_type.keys())
            }
        }
        
        # Dodaj sekcje dla każdego typu encji
        for entity_type, entities in entities_by_type.items():
            print(f"🏗️ Processing {len(entities)} {entity_type} entities")
            
            helper = self.helper_registry.get_mapper(entity_type)
            if not helper:
                print(f"⚠️ No helper found for entity type: {entity_type}")
                continue
            
            # Mapuj wszystkie encje tego typu
            mapped_entities = []
            for entity_doc in entities:
                try:
                    mapped_entity = helper.map_to_json(entity_doc)
                    mapped_entities.append(mapped_entity)
                except Exception as e:
                    print(f"❌ Error mapping {entity_type} entity: {str(e)}")
                    continue
            
            if mapped_entities:
                json_structure[entity_type] = mapped_entities
                print(f"✅ Added {len(mapped_entities)} {entity_type} entities to JSON structure")
        
        print(f"✅ JSON structure built with {len(json_structure)} sections")
        return json_structure
    
    def _create_context(self) -> Dict[str, Any]:
        """
        Tworzy sekcję @context dla JSON-LD.
        Na razie zwraca podstawowy context - do rozszerzenia później.
        
        Returns:
            Context JSON-LD
        """
        # TODO: Implement proper context based on GRISERA ontology
        return {
            "co": "http://www.semanticweb.org/GRISERA/contextualOntology#",
            "pc": "http://www.semanticweb.org/GRISERA/contextualOntology/propertyConcept#",
            "appearanceOcclusion": "http://www.semanticweb.org/GRISERA/contextualOntology/models/appearanceOcclusion#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        }
    
    def _create_ontology_section(self) -> List[Dict[str, Any]]:
        """
        Tworzy sekcję owl:Ontology.
        Na razie zwraca podstawową strukturę - do rozszerzenia później.
        
        Returns:
            Lista z metadanymi ontologii
        """
        # TODO: Implement proper ontology metadata
        return [
            {
                "@id": "http://www.semanticweb.org/ontologies/grisera-export",
                "rdf:type": [
                    {
                        "@id": "owl:Ontology"
                    }
                ],
                "owl:imports": [
                    {
                        "@id": "http://www.semanticweb.org/GRISERA/contextualOntology"
                    }
                ]
            }
        ]
    
    def validate_structure(self, json_structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Waliduje strukturę JSON.
        Na razie podstawowa walidacja - do rozszerzenia później.
        
        Args:
            json_structure: Struktura JSON do walidacji
            
        Returns:
            Wynik walidacji
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "statistics": {}
        }
        
        try:
            # Sprawdź podstawowe wymagane sekcje
            required_sections = ["metadata"]
            for section in required_sections:
                if section not in json_structure:
                    validation_result["errors"].append(f"Missing required section: {section}")
                    validation_result["is_valid"] = False
            
            # Zbierz statystyki
            total_entities = 0
            entity_sections = []
            
            for key, value in json_structure.items():
                if key != "metadata" and isinstance(value, list):
                    entity_sections.append(key)
                    total_entities += len(value)
            
            validation_result["statistics"] = {
                "total_entities": total_entities,
                "entity_sections": entity_sections,  # Lista stringów, nie liczba
                "sections": list(entity_sections)
            }
            
            # Debug print
            print(f"🔍 DEBUG: Validation result statistics:")
            print(f"   - total_entities: {total_entities}")
            print(f"   - entity_sections: {entity_sections}")
            print(f"   - entity_sections type: {type(entity_sections)}")
            print(f"   - entity_sections length: {len(entity_sections)}")
            print(f"   - sections: {list(entity_sections)}")
            
            print(f"📊 Validation completed: {total_entities} entities in {len(entity_sections)} sections")
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
            validation_result["is_valid"] = False
            print(f"❌ Validation failed: {str(e)}")
        
        return validation_result
    
    def get_structure_statistics(self, json_structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Zwraca statystyki struktury JSON.
        
        Args:
            json_structure: Struktura JSON
            
        Returns:
            Statystyki struktury
        """
        try:
            statistics = {
                "total_sections": len(json_structure),
                "entity_sections": {},
                "total_entities": 0
            }
            
            for key, value in json_structure.items():
                if key != "metadata" and isinstance(value, list):
                    entity_count = len(value)
                    statistics["entity_sections"][key] = entity_count
                    statistics["total_entities"] += entity_count
            
            return statistics
            
        except Exception as e:
            print(f"❌ Error calculating statistics: {str(e)}")
            return {"error": str(e)}
