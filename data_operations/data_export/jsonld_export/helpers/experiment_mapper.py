"""
Experiment JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ExperimentJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Experiment -> co:Experiment."""
    
    def _get_entity_type(self) -> str:
        return "Experiment"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Experiment"
    
    def get_collection_enum(self) -> Collections:
        return Collections.EXPERIMENT

    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Pobiera Experiment + jego scenariusze"""
        print(f"🔍 [Experiment] Starting fetch_entities for dataset: {dataset_id}")

        try:
            # Pobierz experiment
            print(f"�� [Experiment] Fetching experiments from collection: {self.get_collection_enum().value}")
            experiments = self._fetch_entities_from_collection_enum(dataset_id)
            print(f"✅ [Experiment] Found {len(experiments)} experiments")

            # Dla każdego experiment pobierz jego scenariusze
            for i, experiment in enumerate(experiments):
                print(
                    f"🔍 [Experiment] Processing experiment {i + 1}/{len(experiments)}: {experiment.get('id', 'NO_ID')}")

                experiment_id = experiment.get("id")
                if not experiment_id:
                    print(f"⚠️ [Experiment] Experiment {i + 1} has no id, skipping scenarios")
                    continue

                print(f"🔍 [Experiment] Looking for scenarios with experiment_id: {experiment_id}")

                try:
                    # Pobierz scenariusze po experiment_id
                    scenarios = self.mongo_api_service.get_documents(
                        collection_name="scenarios",
                        dataset_id=dataset_id,
                        query={"experiment_id": experiment_id}
                    )
                    scenarios_list = list(scenarios) if scenarios else []
                    print(f"✅ [Experiment] Found {len(scenarios_list)} scenarios for experiment {experiment_id}")

                    experiment["_scenarios"] = scenarios_list

                except Exception as e:
                    print(f"❌ [Experiment] Error fetching scenarios for experiment {experiment_id}: {str(e)}")
                    experiment["_scenarios"] = []

            print(f"✅ [Experiment] fetch_entities completed for {len(experiments)} experiments")
            return experiments

        except Exception as e:
            print(f"❌ [Experiment] Error in fetch_entities: {str(e)}")
            return []
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Experiment z MongoDB na JSON"""
        base_structure = self._create_basic_json_structure(entity_doc)
        properties = {}

        if "experiment_name" in entity_doc and entity_doc["experiment_name"]:
            properties["co:hasName"] = entity_doc["experiment_name"]

        # Mapuj name z additional_properties (fallback)
        if "additional_properties" in entity_doc and entity_doc["additional_properties"]:
            for prop in entity_doc["additional_properties"]:
                if prop.get("key") == "name" and prop.get("value"):
                    properties["co:hasName"] = prop["value"]
                    break

            for prop in entity_doc["additional_properties"]:
                if prop.get("key") == "description" and prop.get("value"):
                    properties["co:hasDescription"] = prop["value"]
                    break

            for prop in entity_doc["additional_properties"]:
                if prop.get("key") == "creator" and prop.get("value"):
                    properties["co:hasCreator"] = prop["value"]
                    break

        if "_scenarios" in entity_doc and entity_doc["_scenarios"]:
            all_activity_execution_ids = []

            for scenario in entity_doc["_scenarios"]:
                if "activity_executions" in scenario and scenario["activity_executions"]:
                    for ae_group in scenario["activity_executions"]:
                        for ae_id in ae_group:
                            all_activity_execution_ids.append({"@id": f"{ae_id}"})

            if all_activity_execution_ids:
                properties["co:hasScenario"] = all_activity_execution_ids  # ← co:hasScenario z ID activity executions

        base_structure.update(properties)
        return base_structure
