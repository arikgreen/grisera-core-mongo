from typing import Dict, Any, Optional
from grisera import ActivityExecutionIn, PropertyIn
from .base import BaseEntityConverter, DEBUG
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory

from .activity_converter import ActivityConverter

class ActivityExecutionConverter(BaseEntityConverter[ActivityExecutionIn]):
    JSON_KEY_CANDIDATES_FOR_ACTIVITY_ID = ["hasActivity", "activity_id", "activityId"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_ARRANGEMENT_ID = ["hasArrangement", "arrangement_id", "arrangementId"] # Czyste klucze
    JSON_KEY_CANDIDATES_FOR_NEXT_ID = ["hasNextActivityExecution", "nextActivityExecution", "next_activity_execution_id"] # Czyste klucze
    DEFAULT_MAIN_FIELD_PREFIX = "ActivityExecution"
    
    # Klasowy licznik dla unikalnych nazw scenario execution
    _scenario_execution_counter = 0

    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.activity_service = ActivityConverter(import_id)
        self.services = MongoServiceFactory()

    def convert(self, json_entity: Dict[str, Any]) -> ActivityExecutionIn:
        external_id = self._get_external_id(json_entity)

        # Pobierz powiązane ID
        activity_id = self._extract_activity_id_from_json(json_entity)
        arrangement_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_ARRANGEMENT_ID)
        next_activity_execution_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_NEXT_ID)

        activity_execution = ActivityExecutionIn(
            activity_id=activity_id,
            arrangement_id=arrangement_id
        )

        additional_properties = self._set_common_properties(json_entity, activity_execution)

        if external_id:
            clean_name = remove_prefix(external_id)
            additional_properties.append(PropertyIn(key="name", value=clean_name))
        else:
            additional_properties.append(PropertyIn(key="name", value="ActivityExecution"))

        ActivityExecutionConverter._scenario_execution_counter += 1
        scenario_execution_name = f"Scenario Execution {ActivityExecutionConverter._scenario_execution_counter}"
        additional_properties.append(PropertyIn(key="scenarioExecutionName", value=scenario_execution_name))
        if DEBUG:
            print(f"✅ Added scenarioExecutionName: '{scenario_execution_name}' to Activity Execution")

        # Dodaj next_activity_execution_id jako PropertyIn jeśli istnieje (będzie używane do budowania scenariuszy)
        if next_activity_execution_id:
            additional_properties.append(PropertyIn(key="next_activity_execution_id", value=next_activity_execution_id))
            if DEBUG:
                print(f"✅ Found next activity execution reference: {next_activity_execution_id}")

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_ACTIVITY_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_ARRANGEMENT_ID)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_NEXT_ID)
        # Dodaj "name", "description" i "scenarioExecutionName" do wykluczonych
        processed_clean_keys.extend(["name", "description", "scenarioExecutionName"])
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        next_log = f", next_id='{next_activity_execution_id}'" if next_activity_execution_id else ""
        if DEBUG:
            print(f"📝 Creating ActivityExecutionIn: name='{clean_name_for_log}', activity_id='{activity_id}', arrangement_id='{arrangement_id}'{next_log}, scenario_exec_name='{scenario_execution_name}', external_id='{activity_execution.external_id}', import_job_id='{activity_execution.import_job_id}', properties={len(additional_properties)} (including common)")
        activity_execution.additional_properties = additional_properties
        if DEBUG:
            print(f"📝 Creating ActivityExecutionIn: {activity_execution.__dict__} (including common)")

        return activity_execution
    
    def _extract_activity_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga Activity ID z JSON, mapuje go na MongoDB ID Activity lub zwraca source ID.
        """
        # Najpierw sprawdź proste przypadki (activity_id, activityId)
        simple_activity_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_ACTIVITY_ID)
        if simple_activity_id:
            if DEBUG:
                print(f"✅ Found simple activity_id: {simple_activity_id}")
            return simple_activity_id
        
        # Następnie sprawdź co:hasActivity (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_ACTIVITY_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    activity_source_id = self._extract_activity_source_id(entity_value)
                    if activity_source_id:
                        if DEBUG:
                            print(f"✅ Found Activity source ID from {entity_key_with_prefix}: {activity_source_id}")
                        # Tutaj zapisujemy source ID, mapowanie na MongoDB ID zostanie zrobione przy zapisie
                        return activity_source_id
        
        if DEBUG:
            print("⚠️ No Activity reference found in ActivityExecution")
        return None
    
    def _extract_activity_source_id(self, activity_value: Any) -> Optional[str]:
        """
        Wyciąga source ID Activity z różnych formatów JSON.
        """
        if isinstance(activity_value, list) and len(activity_value) > 0:
            # Lista obiektów Activity
            first_activity = activity_value[0]
            if isinstance(first_activity, dict) and "@id" in first_activity:
                return str(first_activity["@id"])
        elif isinstance(activity_value, dict) and "@id" in activity_value:
            # Pojedynczy obiekt Activity
            return str(activity_value["@id"])
        elif isinstance(activity_value, str):
            # Proste ID jako string
            return activity_value
        
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> ActivityExecutionIn:
        """
        Konwertuje i zapisuje ActivityExecution.
        Na razie tylko konwertuje - faktyczne zapisywanie będzie w kolejnej iteracji.
        """
        return self._save_activity_execution_with_scenario_linking(self.convert(json_entity), dataset_id, import_id)

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """
        Znajduje ActivityExecution w MongoDB po source_id i zwraca jego MongoDB ID.

        """
        try:
            if DEBUG:
                print(f"🔍 Searching for ActivityExecution with source_id: {source_id}")

            query_filter = {
                "activity_executions": {
                    "$elemMatch": {
                        "external_id": f"{source_id}"
                    }
                }
            }

            activities_with_matching_executions = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,  # SZUKAJ W ACTIVITIES, NIE ACTIVITY_EXECUTIONS!
                dataset_id=dataset_id,
                query=query_filter
            )

            if DEBUG:
                print(
                    f"🔍 Found {len(activities_with_matching_executions) if activities_with_matching_executions else 0} activities with matching ActivityExecution")

            # Przeszukaj embedded activity_executions w znalezionych activities
            for activity_doc in activities_with_matching_executions:
                activity_executions = activity_doc.get("activity_executions", [])

                for ae_doc in activity_executions:
                    # Sprawdź czy ten ActivityExecution ma odpowiedni source_entity_ref
                    external_id = ae_doc.get("external_id")
                    if source_id == external_id or source_id == external_id.replace(":", ""):
                        ae_id = str(ae_doc.get("id", ""))
                        if DEBUG:
                            print(f"✅ Found ActivityExecution: {source_id} -> MongoDB ID: {ae_id}")
                        return ae_id
                    else:
                        if DEBUG:
                            print(f"🔍 Checking ActivityExecution with external_id: {external_id}")
                            print(f"🔍 Searching ActivityExecution with source_id: {source_id}")

            print(f"❌ ActivityExecution with source_id '{source_id}' not found in any activity")
            return ""

        except Exception as e:
            print(f"❌ Error finding ActivityExecution by source_id {source_id}: {e}")
            return ""

    def _save_activity_execution_with_scenario_linking(self, grisera_object, dataset_id: str, import_id: str):
            """
            Zapisuje ActivityExecution z mapowaniem activity_id i linkiem do scenariusza
            """
            try:
                if DEBUG:
                    print(f"💾 Saving ActivityExecution with scenario linking...")

                source_entity_ref = grisera_object.external_id

                if not source_entity_ref:
                    if DEBUG:
                        print("⚠️ No source_entity_ref found in ActivityExecution")
                    # Zapisz bez mapowania
                    return self.services.get_activity_execution_service().save_activity_execution(grisera_object,
                                                                                                  dataset_id)

                if DEBUG:
                    print(f"🔍 ActivityExecution source ID: {source_entity_ref}")

                activity_source_id = grisera_object.activity_id
                activity_mongo_id = self.activity_service.find_by_source_id(grisera_object.activity_id, dataset_id)

                if activity_mongo_id:
                    grisera_object.activity_id = activity_mongo_id
                else:
                    print(f"❌ Could not find Activity in MongoDB for source ID: {activity_source_id}")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "ACTIVITY_NOT_FOUND_FOR_AE",
                        f"Activity with source ID '{activity_source_id}' not found for ActivityExecution",
                        source_entity_ref
                    )

                if DEBUG:
                    print(f"✅ ActivityExecution being saved with final data: {grisera_object.__dict__}")
                result = self.services.get_activity_execution_service().save_activity_execution(grisera_object,
                                                                                                dataset_id)
                saved_ae_id = str(getattr(result, 'id', 'unknown'))
                if DEBUG:
                    print(f"✅ ActivityExecution saved with ID: {saved_ae_id}. Activity : {grisera_object.__dict__}")
                return result

            except Exception as e:
                print(f"❌ Error saving ActivityExecution with scenario linking: {e}")
                raise e