import json
from typing import Dict, Any, List
from grisera import ExperimentIn, PropertyIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections

class ExperimentConverter(BaseEntityConverter[ExperimentIn]):
    JSON_KEY_CANDIDATES_FOR_MAIN_FIELD = ["experimentName", "hasName", "name"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_CREATOR = ["creator", "hasCreator", "author", "hasAuthor"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_DESCRIPTION = ["description", "hasDescription", "comment", "hasComment"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_FOOTNOTE = ["footnote", "hasFootnote", "note", "hasNote"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_SCENARIO = ["hasScenario", "scenario", "activityExecutions"] # Czyste klucze dla powiązań z ActivityExecution
    DEFAULT_MAIN_FIELD_PREFIX = "Experiment"
    
    def convert(self, json_entity: Dict[str, Any]) -> ExperimentIn:
        external_id = self._get_external_id(json_entity)

        experiment_name = self._get_main_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD,
            self.DEFAULT_MAIN_FIELD_PREFIX,
            entity_id_str_for_fallback=external_id
        )
        
        # Szukaj creator w JSON, jeśli nie ma, użyj domyślnego
        creator = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_CREATOR)
        if not creator:
            creator = "system"
            if DEBUG:
                print(f"ℹ️ No creator found for experiment '{experiment_name}', using default: '{creator}'")
        
        # Szukaj description w JSON, jeśli nie ma, użyj domyślnego
        description = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_DESCRIPTION)
        if not description:
            description = f"Added during import {self.import_id}"
            if DEBUG:
                print(f"ℹ️ No description found for experiment '{experiment_name}', using default: '{description}'")
        
        # Szukaj footnote w JSON (opcjonalne, może być puste)
        footnote = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_FOOTNOTE)
        if footnote:
            if DEBUG:
                print(f"✅ Found footnote for experiment '{experiment_name}': '{footnote}'")
        
        # Znajdź powiązania z ActivityExecution (co:hasScenario)
        scenario_activity_executions = self._extract_activity_execution_references(json_entity)
        scenario_data = self._extract_full_scenario_data(json_entity)
        
        experiment = ExperimentIn(experiment_name=experiment_name)

        additional_properties = self._set_common_properties(json_entity, experiment)

        # Dodaj creator, description i footnote jako PropertyIn (zgodnie z konwencją UI)
        additional_properties.append(PropertyIn(key="creator", value=creator))
        additional_properties.append(PropertyIn(key="description", value=description))
        if footnote:
            additional_properties.append(PropertyIn(key="footnote", value=footnote))

        # Dodaj powiązania z ActivityExecution jako PropertyIn
        if scenario_activity_executions:
            additional_properties.append(PropertyIn(
                key="has_scenario_activity_execution_ids",
                value=",".join(scenario_activity_executions)
            ))
            if DEBUG:
                print(f"✅ Found {len(scenario_activity_executions)} ActivityExecution references in experiment")

        # Dodaj pełne dane scenariuszy jako JSON dla nowej logiki
        if scenario_data:
            additional_properties.append(PropertyIn(
                key="has_scenario_data",
                value=json.dumps(scenario_data)
            ))
            if DEBUG:
                print(f"✅ Saved {len(scenario_data)} full scenario data entries for new scenario logic")

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MAIN_FIELD)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_CREATOR)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DESCRIPTION)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_FOOTNOTE)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_SCENARIO)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        footnote_log = f", footnote='{footnote}'" if footnote else ""
        scenario_log = f", scenario_ae_count={len(scenario_activity_executions)}" if scenario_activity_executions else ""
        experiment.additional_properties = additional_properties
        if DEBUG:
            print(f"✅ Experiment being saved with final data: {experiment.__dict__}")

        return experiment
    
    def _extract_activity_execution_references(self, json_entity: Dict[str, Any]) -> List[str]:
        """
        Wyciąga referencje do ActivityExecution z pól JSON odpowiadających co:hasScenario
        """
        activity_execution_ids = []
        
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_SCENARIO:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # Wartość może być listą obiektów z @id lub prostą listą ID
                    if isinstance(entity_value, list):
                        for item in entity_value:
                            if isinstance(item, dict) and "@id" in item:
                                # Obiekt z @id
                                activity_execution_ids.append(str(item["@id"]))
                            elif isinstance(item, str):
                                # Proste ID jako string
                                activity_execution_ids.append(item)
                    elif isinstance(entity_value, dict) and "@id" in entity_value:
                        # Pojedynczy obiekt z @id  
                        activity_execution_ids.append(str(entity_value["@id"]))
                    elif isinstance(entity_value, str):
                        # Pojedyncze ID jako string
                        activity_execution_ids.append(entity_value)
        
        # Usuń duplikaty zachowując kolejność
        unique_ids = []
        for id_str in activity_execution_ids:
            if id_str and id_str not in unique_ids:
                unique_ids.append(id_str)
        
        return unique_ids

    def _extract_full_scenario_data(self, json_entity: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Wyciąga pełne dane ActivityExecution z co:hasScenario wraz z co:hasActivity.
        Zwraca listę obiektów ActivityExecution z ich pełnymi danymi.
        """
        scenario_data = []
        
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_SCENARIO:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    if isinstance(entity_value, list):
                        for item in entity_value:
                            if isinstance(item, dict):
                                # To jest pełny obiekt ActivityExecution
                                scenario_data.append(item)
                    elif isinstance(entity_value, dict):
                        # Pojedynczy obiekt ActivityExecution
                        scenario_data.append(entity_value)
        
        return scenario_data

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str):# -> ExperimentIn:
        return self.services.get_experiment_service().save_experiment(self.convert(json_entity), dataset_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.ARRANGEMENT)
