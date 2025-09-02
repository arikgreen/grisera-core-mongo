from typing import Dict, Any, List, Set
from datetime import datetime
import json

from mongo_service.mongo_api_service import MongoApiService
from mongo_service.collection_mapping import Collections
from data_operations.file_operations_model import FileOperationIn
from data_operations.file_operations_service import FileOperationsStatusService

# Import GRISERA serwisów i modeli
from services.mongo_services import MongoServiceFactory
from grisera import (
    PropertyIn,
    ScenarioIn, ScenarioService
)


class ScenarioBuilderService:
    """
    Serwis odpowiedzialny za budowanie scenariuszy sekwencyjnych na podstawie ActivityExecution
    """
    
    def __init__(self, mongo_api_service: MongoApiService, import_id: str, dataset_id: str):
        self.mongo_api_service = mongo_api_service
        self.import_id = import_id
        self.dataset_id = dataset_id
    
    def build_scenarios(self) -> int:
        """
        Buduje scenariusze sekwencyjne na podstawie ActivityExecution połączonych przez hasNext...
        Returns: liczba utworzonych scenariuszy
        """
        try:
            print(f"🎬 Starting sequential scenarios building for import: {self.import_id}")
            
            # Pobierz wszystkie ActivityExecution z bieżącego importu
            query_filter = {"import_job_id": self.import_id}
            activity_executions = self.mongo_api_service.get_documents(
                collection_name="activity_executions",
                dataset_id=self.dataset_id,
                query=query_filter
            )
            
            if not activity_executions:
                print("⚠️ No ActivityExecutions found for scenario building")
                return 0
            
            print(f"📊 Found {len(activity_executions)} ActivityExecutions to analyze")
            
            # Przygotuj słownik dla szybkiego dostępu po source_entity_ref
            ae_by_source_ref = {ae["source_entity_ref"]: ae for ae in activity_executions}
            print(f"🗂️ Indexed {len(ae_by_source_ref)} ActivityExecutions by source_entity_ref")
            
            # Znajdź pola referencyjne wskazujące na następny ActivityExecution
            next_ref_fields = [
                "has_next_activity_execution_ref",
                "has_next_ref", 
                "next_activity_execution_ref",
                "co_has_next_activity_execution_ref"  # możliwe warianty
            ]
            
            # Zidentyfikuj które ActivityExecution są referencjonowane jako "następne"
            referenced_as_next = set()
            ae_next_mapping = {}  # source_id -> next_source_id
            
            for ae in activity_executions:
                for field_name in next_ref_fields:
                    if field_name in ae and ae[field_name]:
                        next_source_id = ae[field_name]
                        if isinstance(next_source_id, str):
                            referenced_as_next.add(next_source_id)
                            ae_next_mapping[ae["source_entity_ref"]] = next_source_id
                            print(f"🔗 Found chain: {ae['source_entity_ref']} -> {next_source_id}")
                        elif isinstance(next_source_id, list) and len(next_source_id) > 0:
                            # Jeśli lista, weź pierwszy element
                            next_id = next_source_id[0]
                            referenced_as_next.add(next_id)
                            ae_next_mapping[ae["source_entity_ref"]] = next_id
                            print(f"🔗 Found chain: {ae['source_entity_ref']} -> {next_id} (from list)")
            
            print(f"🔗 Found {len(ae_next_mapping)} next-references")
            
            # Znajdź początki scenariuszy (nie są referencjonowane jako "następne")
            scenario_starts = []
            for ae in activity_executions:
                if ae["source_entity_ref"] not in referenced_as_next:
                    scenario_starts.append(ae["source_entity_ref"])
            
            print(f"🎬 Found {len(scenario_starts)} potential scenario starts: {scenario_starts}")
            
            scenarios_created = 0
            
            # Zbuduj scenariusze dla każdego początku
            for start_source_id in scenario_starts:
                try:
                    scenario_chain = self._build_chain(
                        start_source_id, 
                        ae_next_mapping, 
                        ae_by_source_ref
                    )
                    
                    if len(scenario_chain) > 1:  # Scenariusz musi mieć więcej niż 1 ActivityExecution
                        scenario_doc = {
                            "import_job_id": self.import_id,
                            "dataset_id": self.dataset_id,
                            "scenario_source_ref": start_source_id,  # Główny identyfikator scenariusza
                            "activity_execution_source_refs": scenario_chain,  # Lista ID ActivityExecution
                            "activity_execution_count": len(scenario_chain),
                            "created_at": datetime.utcnow().isoformat(),
                            "scenario_type": "sequential"
                        }
                        
                        # Zapisz scenariusz do MongoDB
                        scenario_id = self.mongo_api_service.create_document_from_dict(
                            scenario_doc,
                            Collections.SCENARIO.value,  # "scenarios"
                            self.dataset_id
                        )
                        
                        scenarios_created += 1
                        print(f"🎭 Created scenario {scenarios_created}: {scenario_id} with {len(scenario_chain)} ActivityExecutions")
                        print(f"   Chain: {' -> '.join(scenario_chain)}")
                    
                    else:
                        print(f"⚠️ Skipping single ActivityExecution scenario: {start_source_id}")
                        
                except Exception as e:
                    print(f"❌ Error building scenario for {start_source_id}: {str(e)}")
                    self._log_scenario_error(
                        "SCENARIO_BUILD_ERROR",
                        f"Error building scenario for {start_source_id}: {str(e)}",
                        start_source_id
                    )
            
            print(f"🎉 Sequential scenarios building completed: {scenarios_created} scenarios created")
            return scenarios_created
            
        except Exception as e:
            print(f"❌ Critical error in scenarios building: {str(e)}")
            self._log_scenario_error(
                "CRITICAL_SCENARIO_ERROR",
                f"Critical error in scenarios building: {str(e)}"
            )
            return 0
    
    def _build_chain(
        self, 
        start_source_id: str, 
        ae_next_mapping: Dict[str, str], 
        ae_by_source_ref: Dict[str, Any]
    ) -> List[str]:
        """
        Buduje łańcuch scenariusza rozpoczynając od danego ActivityExecution
        Returns: lista source_id w kolejności scenariusza
        """
        chain = [start_source_id]
        visited = {start_source_id}  # Wykrywanie cykli
        current_id = start_source_id
        
        print(f"🔄 Building chain starting from: {start_source_id}")
        
        while current_id in ae_next_mapping:
            next_id = ae_next_mapping[current_id]
            
            if next_id in visited:
                print(f"⚠️ Cycle detected in scenario chain at: {next_id}")
                self._log_scenario_error(
                    "SCENARIO_CYCLE_DETECTED",
                    f"Cycle detected in scenario chain: {' -> '.join(chain)} -> {next_id}",
                    current_id
                )
                break
            
            if next_id not in ae_by_source_ref:
                print(f"⚠️ Referenced ActivityExecution not found: {next_id}")
                break
            
            chain.append(next_id)
            visited.add(next_id)
            current_id = next_id
            print(f"   ➡️ Added to chain: {next_id}")
        
        print(f"✅ Chain completed with {len(chain)} ActivityExecutions")
        return chain
    
    def _log_scenario_error(
        self,
        error_code: str,
        message: str,
        problematic_entity_id: str = None
    ):
        """Loguje błąd scenariusza do bazy danych"""
        print(f"📝 Logging scenario error: {error_code} - {message}")
        
        error_doc = {
            "import_job_id": self.import_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error_code": error_code,
            "message": message,
            "context": {
                "import_phase": "scenario_building",
                "dataset_id": self.dataset_id,
                "scenario_builder": True
            }
        }
        
        if problematic_entity_id:
            error_doc["problematic_entity_id"] = problematic_entity_id
            error_doc["context"]["entity_id"] = problematic_entity_id
            print(f"🔍 Error relates to entity: {problematic_entity_id}")
        
        # Dodaj metadane błędu specyficzne dla scenariuszy
        error_doc["context"]["error_severity"] = self._determine_scenario_error_severity(error_code)
        error_doc["context"]["retry_recommended"] = self._is_scenario_retry_recommended(error_code)
        
        try:
            self.mongo_api_service.create_document_from_dict(
                error_doc,
                Collections.IMPORT_ERRORS.value,  # "import_errors"
                self.dataset_id
            )
            print(f"✅ Scenario error logged to database")
        except Exception as e:
            # Błąd podczas logowania błędu - nie przerywaj procesu
            print(f"❌ Failed to log scenario error to database: {e}")
            print(f"💾 Original error was: {error_code} - {message}")
    
    def _determine_scenario_error_severity(self, error_code: str) -> str:
        """Określa poziom ważności błędu scenariusza"""
        critical_errors = ["CRITICAL_SCENARIO_ERROR"]
        warning_errors = ["SCENARIO_CYCLE_DETECTED"]
        
        if error_code in critical_errors:
            return "CRITICAL"
        elif error_code in warning_errors:
            return "WARNING"
        else:
            return "ERROR"
    
    def _is_scenario_retry_recommended(self, error_code: str) -> bool:
        """Określa czy błąd scenariusza sugeruje ponowienie próby"""
        retry_errors = ["SCENARIO_BUILD_ERROR"]
        no_retry_errors = ["CRITICAL_SCENARIO_ERROR", "SCENARIO_CYCLE_DETECTED"]
        
        if error_code in no_retry_errors:
            return False
        elif error_code in retry_errors:
            return True
        else:
            return False  # Domyślnie nie rekomenduj retry


class ExperimentScenariosBuilder:
    """
    Serwis odpowiedzialny za budowanie scenariuszy na podstawie eksperymentów
    """
    
    def __init__(self, mongo_api_service: MongoApiService, services: MongoServiceFactory, file_ops_service: FileOperationsStatusService):
        self.mongo_api_service = mongo_api_service
        self.services = services
        self.file_ops_service = file_ops_service
        
        # Globalny licznik dla nazw Scenario Execution
        self.scenario_execution_counter = 1
    
    def build_experiment_scenarios(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Buduje scenariusze na podstawie zaimportowanych eksperymentów.

        NOWA LOGIKA:
        1. Scenariusz (Scenario) = szablon dla Activity (już mamy)
        2. Scenario Execution = konkretne wykonanie scenariusza - grupa Activity Executions z tym samym scenarioExecutionName
        """
        print(f"🎬 Building experiment-based scenarios for import ID: {import_id}")
        scenarios_created = 0
        scenario_executions_created = 0
        processed_activities = set()  # Deduplikacja scenariuszy dla tego samego Activity

        try:
            # KROK 1: Pobierz eksperymenty zaimportowane w tym import_id
            print("📋 Step 1: Fetching experiments imported in this job...")
            query_filter = {
                "import_job_id": import_id
            }

            imported_experiments = self.mongo_api_service.get_documents(
                collection_name=Collections.EXPERIMENT.value,
                dataset_id=import_data.dataset_id,
                query=query_filter
            )

            if not imported_experiments:
                print("ℹ️ No experiments found from this import job")
                return 0

            print(f"📊 Found {len(imported_experiments)} experiments imported in this job")

            # KROK 2: Dla każdego eksperymentu analizuj ActivityExecution w hasScenario
            for experiment_doc in imported_experiments:
                experiment_id = str(experiment_doc.get("id", "unknown"))
                experiment_name = experiment_doc.get("experiment_name", f"Experiment_{experiment_id}")
                print(f"\n🧪 Processing experiment: {experiment_name} (ID: {experiment_id})")

                # KROK 2.1: Pobierz ActivityExecution z has_scenario_data w additional_properties
                activity_executions = self._extract_activity_executions_from_experiment(experiment_doc)
                if not activity_executions:
                    print(f"ℹ️ No ActivityExecution found in experiment {experiment_id}")
                    continue

                print(f"📋 Found {len(activity_executions)} ActivityExecution in hasScenario")

                # KROK 2.2: Zbierz wszystkie unikalne Activities z tego eksperymentu (SZABLON SCENARIUSZA)
                experiment_activities = []
                for ae_data in activity_executions:
                    ae_id = ae_data.get("@id", "unknown")
                    print(f"🔍 Processing ActivityExecution: {ae_id}")

                    # Wyciągnij Activity ID z co:hasActivity
                    activity_source_id = self._extract_activity_id_from_ae(ae_data)
                    if not activity_source_id:
                        ae_external_id = ae_id
                        if ae_external_id:
                            print(f"🔍 Searching for activity with activity_execution external_id: {ae_external_id}")

                            query_filter = {
                                "activity_executions": {
                                    "$elemMatch": {
                                        "external_id": f"{ae_external_id}"
                                    }
                                }
                            }

                            activities = self.mongo_api_service.get_documents(
                                collection_name=Collections.ACTIVITY.value,
                                dataset_id=import_data.dataset_id,
                                query=query_filter
                            )

                            if activities and len(activities) > 0:
                                activity_doc = activities[0]
                                activity_id = str(activity_doc.get("id", ""))
                                print(
                                    f"✅ Found activity by fallback: {activity_id} for AE external_id: {ae_external_id}")
                                activity_res = self._find_by_id(activity_id, import_data.dataset_id, Collections.ACTIVITY)
                                if activity_res:
                                    print(f"�� activity_res type: {type(activity_res)}")
                                    print(f"🔍 activity_res content: {activity_res}")
                                    if isinstance(activity_res, dict) and "external_id" in activity_res and \
                                            activity_res["external_id"]:
                                        activity_source_id = str(activity_res["external_id"])
                                        print(f"✅ Using external_id from activity_res (dict): {activity_source_id}")
                                    elif hasattr(activity_res, 'external_id') and activity_res.external_id:
                                        activity_source_id = str(activity_res.external_id)
                                        print(f"✅ Using external_id from activity_res (object): {activity_source_id}")
                                else:
                                    print(f"❌ _find_by_id failed for activity_id: {activity_id}")
                            else:
                                print(f"❌ No Activity found in ActivityExecution {ae_id} nor by fallback")
                                self._log_import_error(
                                    import_id,
                                    import_data.dataset_id,
                                    "MISSING_ACTIVITY_IN_AE",
                                    f"No co:hasActivity found in ActivityExecution {ae_id} nor by fallback",
                                    ae_id
                                )
                                continue


                    # KROK 2.3: Sprawdź czy Activity istnieje w MongoDB
                    activity_mongo_id = self._find_activity_by_source_id(activity_source_id, import_data.dataset_id)
                    if not activity_mongo_id:
                        print(f"❌ Activity with source ID '{activity_source_id}' not found in MongoDB")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "ACTIVITY_NOT_FOUND_IN_MONGO",
                            f"Activity with source ID '{activity_source_id}' not found in MongoDB",
                            activity_source_id
                        )
                        continue

                    # Dodaj do listy Activities dla tego eksperymentu (z duplikacją)
                    if activity_mongo_id not in [a["mongo_id"] for a in experiment_activities]:
                        experiment_activities.append({
                            "source_id": activity_source_id,
                            "mongo_id": activity_mongo_id
                        })
                        print(f"✅ Added Activity {activity_source_id} (MongoDB ID: {activity_mongo_id})")

                # KROK 2.4: Stwórz jeden scenariusz-szablon dla wszystkich Activities z eksperymentu
                if experiment_activities:
                    scenario_name = f"Scenario Template for Experiment {experiment_name}"
                    scenario_description = f"Template scenario containing {len(experiment_activities)} activities from experiment '{experiment_name}'"

                    # Stwórz additional_properties z wszystkimi activity_id
                    additional_properties = [
                        PropertyIn(key="name", value=scenario_name),
                        PropertyIn(key="description", value=scenario_description),
                        PropertyIn(key="auto_generated", value="true"),
                        PropertyIn(key="scenario_type", value="template"),
                        PropertyIn(key="source_experiment_id", value=experiment_id),
                        PropertyIn(key="import_job_id", value=import_id),
                        PropertyIn(key="status", value="completed")
                    ]

                    # Dodaj wszystkie activity_id jako osobne PropertyIn
                    for activity in experiment_activities:
                        additional_properties.append(PropertyIn(
                            key="activity_id",
                            value=activity["mongo_id"]
                        ))
                        print(f"🎯 Added activity_id: {activity['mongo_id']} (source: {activity['source_id']})")

                    scenario_in = ScenarioIn(
                        experiment_id=experiment_id,
                        activity_executions=[],  # Pusta lista - activity_id będzie w additional_properties
                        additional_properties=additional_properties
                    )

                    # KROK 2.5: Zapisz scenariusz szablon
                    try:
                        scenario_service = self.services.get_scenario_service()
                        scenario_result = scenario_service.save_scenario(scenario_in, import_data.dataset_id)

                        # Debug: sprawdź co zwraca serwis
                        print(
                            f"🔍 Scenario service result: id={getattr(scenario_result, 'id', 'MISSING')}, errors={getattr(scenario_result, 'errors', 'NONE')}")

                        if hasattr(scenario_result, 'errors') and scenario_result.errors:
                            print(f"❌ Error creating template scenario: {scenario_result.errors}")
                            self._log_import_error(
                                import_id,
                                import_data.dataset_id,
                                "SCENARIO_TEMPLATE_CREATION_ERROR",
                                f"Failed to create template scenario: {scenario_result.errors}",
                                scenario_name
                            )
                        elif not hasattr(scenario_result, 'id') or scenario_result.id is None:
                            print(f"❌ Template scenario created but ID is missing or None")
                            self._log_import_error(
                                import_id,
                                import_data.dataset_id,
                                "SCENARIO_TEMPLATE_ID_MISSING",
                                f"Template scenario created but ID is missing or None",
                                scenario_name
                            )
                        else:
                            template_scenario_id = str(scenario_result.id)
                            scenarios_created += 1
                            print(
                                f"🎭 Created template scenario {scenarios_created}: {template_scenario_id} with {len(experiment_activities)} activities")

                            # KROK 3: Stwórz Scenario Executions na podstawie Activity Executions
                            executions_created = self._create_scenario_executions(
                                experiment_id,
                                template_scenario_id,
                                activity_executions,
                                import_data.dataset_id,
                                import_id
                            )
                            scenario_executions_created += executions_created
                            print(
                                f"🎯 Created {executions_created} scenario executions for template {template_scenario_id}")

                    except Exception as e:
                        print(f"❌ Exception creating template scenario: {str(e)}")
                        self._log_import_error(
                            import_id,
                            import_data.dataset_id,
                            "SCENARIO_TEMPLATE_CREATION_EXCEPTION",
                            f"Exception creating template scenario: {str(e)}",
                            scenario_name
                        )
                else:
                    print(f"⚠️ No valid Activities found for experiment {experiment_id}")

            print(
                f"🎭 Scenario building completed. Created {scenarios_created} template scenarios and {scenario_executions_created} scenario executions")

            # NOWA LOGIKA: Dodaj participantów do eksperymentów
            print(f"\n👥 FAZA 2: Adding participants to experiments from import job: {import_id}")
            participants_processed = self._process_participants_for_experiments(imported_experiments, import_id,
                                                                                import_data.dataset_id)
            print(
                f"✅ Participant processing completed. Updated {participants_processed} experiments with participants")

            return scenarios_created + scenario_executions_created

        except Exception as e:
            print(f"❌ Error in scenario building: {str(e)}")
            self._log_import_error(
                import_id,
                import_data.dataset_id,
                "SCENARIO_BUILDING_ERROR",
                f"Error in scenario building: {str(e)}"
            )
            return scenarios_created

    def _extract_activity_executions_from_experiment(self, experiment_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Wyciąga pełne dane ActivityExecution z has_scenario_data w additional_properties
        """
        additional_properties = experiment_doc.get("additional_properties", [])
        if additional_properties is None:
            additional_properties = []
        for prop in additional_properties:
            if prop.get("key") == "has_scenario_data":
                scenario_data_str = prop.get("value", "")
                if scenario_data_str:
                    try:
                        return json.loads(scenario_data_str)
                    except json.JSONDecodeError:
                        print(f"❌ Invalid JSON in has_scenario_data: {scenario_data_str}")
                        return []

        print("ℹ️ No has_scenario_data found in experiment")
        return []

    def _extract_activity_id_from_ae(self, ae_data: Dict[str, Any]) -> str:
        """
        Wyciąga Activity ID z ActivityExecution data
        """
        has_activity = ae_data.get("co:hasActivity", [])
        if has_activity and len(has_activity) > 0:
            activity_ref = has_activity[0]
            return activity_ref.get("@id", "")
        return ""

    def _create_scenario_executions(self, experiment_id: str, template_scenario_id: str,
                                    activity_executions: List[Dict[str, Any]], dataset_id: str,
                                    import_id: str) -> int:
        """
        Tworzy osobne Scenario Executions dla każdego ActivityExecution który pasuje do template scenario.

        NOWA LOGIKA:
        1. Pobierz template scenario i sprawdź jakie activity_id ma
        2. Dla każdego ActivityExecution sprawdź czy jego activity_id pasuje do template scenario
        3. Jeśli TAK → stwórz osobny "Scenario Execution X" z tym jednym ActivityExecution
        4. Każdy Scenario Execution = 1 ActivityExecution
        """
        try:
            print(f"🎬 Creating individual scenario executions for template scenario {template_scenario_id}")

            # KROK 1: Pobierz template scenario i wyciągnij activity_id z additional_properties
            try:
                scenario_dict = self.mongo_api_service.get_document(
                    template_scenario_id,
                    Collections.SCENARIO.value,
                    dataset_id
                )
                if not scenario_dict:
                    print(f"❌ Template scenario {template_scenario_id} not found")
                    return 0

                print(f"✅ Retrieved template scenario: {scenario_dict.get('id')}")

                # Wyciągnij activity_id z additional_properties template scenario
                template_activity_ids = []
                for prop in scenario_dict.get("additional_properties", []):
                    if prop.get("key") == "activity_id":
                        template_activity_ids.append(prop.get("value"))

                if not template_activity_ids:
                    print(f"⚠️ Template scenario has no activity_id in additional_properties")
                    return 0

                print(f"🎯 Template scenario activity_ids: {template_activity_ids}")

                # Upewnij się że activity_executions jest listą
                if "activity_executions" not in scenario_dict:
                    scenario_dict["activity_executions"] = []

            except Exception as e:
                print(f"❌ Error retrieving template scenario {template_scenario_id}: {e}")
                return 0

            # KROK 2: Pobierz Activity które zawierają Activity Executions z tego import job
            query_filter = {
                "import_job_id": import_id,
                "activity_executions": {"$exists": True, "$ne": []}  # Activity musi mieć activity_executions
            }

            activities_with_executions = self.mongo_api_service.get_documents(
                collection_name=Collections.ACTIVITY.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if not activities_with_executions:
                print("ℹ️ No Activities with Activity Executions found from this import job")
                return 0

            print(f"📋 Found {len(activities_with_executions)} Activities with Activity Executions from this import")

            # KROK 3: Przejdź przez wszystkie Activity Executions i sprawdź które pasują do template scenario
            matching_activity_executions = []
            total_ae_found = 0

            for activity_doc in activities_with_executions:
                activity_id = str(activity_doc.get("id"))
                activity_name = activity_doc.get("activity", "unknown")
                ae_list = activity_doc.get("activity_executions", [])

                print(
                    f"🔍 Processing Activity '{activity_name}' (ID: {activity_id}) with {len(ae_list)} Activity Executions")

                # Sprawdź czy to Activity pasuje do template scenario
                if activity_id in template_activity_ids:
                    print(f"✅ Activity {activity_name} (ID: {activity_id}) MATCHES template scenario!")

                    for ae_doc in ae_list:
                        total_ae_found += 1

                        # Znajdź source_entity_ref (oryginalną nazwę z JSON)
                        source_name = ae_doc.get("external_id", "Unknown")
                        if source_name and source_name.startswith(":"):
                            source_name = source_name[1:]

                        matching_activity_executions.append({
                            "ae_doc": ae_doc,
                            "source_name": source_name,
                            "activity_name": activity_name
                        })

                        print(f"📎 Added matching ActivityExecution: {source_name} (ID: {ae_doc.get('id')})")
                else:
                    print(f"⚠️ Activity {activity_name} (ID: {activity_id}) does NOT match template scenario")

            print(f"📊 Total matching Activity Executions found: {len(matching_activity_executions)}")

            if not matching_activity_executions:
                print("ℹ️ No matching Activity Executions found for template scenario")
                return 0

            # KROK 4: Stwórz osobny Scenario Execution dla każdego pasującego ActivityExecution
            scenario_executions_created = 0

            for ae_info in matching_activity_executions:
                ae_doc = ae_info["ae_doc"]
                source_name = ae_info["source_name"]
                activity_name = ae_info["activity_name"]
                ae_id = str(ae_doc.get("id"))

                # Globalny licznik dla nazw Scenario Execution
                scenario_execution_name = f"Scenario Execution {self.scenario_execution_counter}"
                self.scenario_execution_counter += 1
                print(f"\n🎯 Creating {scenario_execution_name} for ActivityExecution '{source_name}'")

                # Stwórz listę z jednym ActivityExecution ID
                single_ae_list = [ae_id]

                # Dodaj jako osobną listę do activity_executions template scenario
                scenario_dict["activity_executions"].append(single_ae_list)
                scenario_executions_created += 1

                print(f"✅ Created {scenario_execution_name}: [{source_name}] (ID: {ae_id})")

            # KROK 5: Zapisz zaktualizowany template scenario do MongoDB
            try:
                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.SCENARIO.value,
                    id=template_scenario_id,
                    new_document=scenario_dict,
                    dataset_id=dataset_id
                )

                print(
                    f"🎭 Successfully updated template scenario {template_scenario_id} with {scenario_executions_created} individual scenario executions")

                # Loguj finalną strukturę
                print(
                    f"📊 Final activity_executions structure: {len(scenario_dict['activity_executions'])} scenario executions")
                for i, execution in enumerate(scenario_dict["activity_executions"]):
                    print(
                        f"   Scenario Execution {i + 1}: {len(execution)} Activity Execution (ID: {execution[0] if execution else 'empty'})")

                return scenario_executions_created

            except Exception as e:
                print(f"❌ Error updating template scenario {template_scenario_id}: {e}")
                self._log_import_error(
                    import_id,
                    dataset_id,
                    "SCENARIO_UPDATE_ERROR",
                    f"Error updating template scenario with individual executions: {str(e)}",
                    template_scenario_id
                )
                return 0

        except Exception as e:
            print(f"❌ Error creating individual scenario executions: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "SCENARIO_EXECUTION_CREATION_ERROR",
                f"Error creating individual scenario executions: {str(e)}"
            )
            return 0

    def _find_imported_participants(self, import_id: str, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Znajduje participantów zaimportowanych w tym import job.

        Args:
            import_id: ID procesu importu
            dataset_id: ID datasetu

        Returns:
            Lista słowników z danymi participantów (id, name, source_id)
        """
        try:
            print(f"👥 Searching for participants imported in job: {import_id}")

            query_filter = {
                "import_job_id": import_id
            }

            imported_participants = self.mongo_api_service.get_documents(
                collection_name=Collections.PARTICIPANT.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if not imported_participants:
                print(f"ℹ️ No participants found for import job: {import_id}")
                return []

            participants_data = []
            for participant_doc in imported_participants:
                participant_id = str(participant_doc.get("id", "unknown"))
                participant_name = participant_doc.get("name", "Unknown Participant")

                source_id = participant_doc.get("external_id", "Unknown")
                if source_id and source_id.startswith(":"):
                    source_id = source_id[1:]

                participants_data.append({
                    "mongo_id": participant_id,
                    "name": participant_name,
                    "source_id": source_id
                })

                print(
                    f"✅ Found participant: {participant_name} (MongoDB ID: {participant_id}, Source: {source_id})")

            print(f"📊 Total participants found: {len(participants_data)}")
            return participants_data

        except Exception as e:
            print(f"❌ Error finding imported participants: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "PARTICIPANT_SEARCH_ERROR",
                f"Error finding imported participants: {str(e)}"
            )
            return []

    def _add_participants_to_experiment(self, experiment_id: str, participants: List[Dict[str, Any]],
                                        dataset_id: str) -> bool:
        """
        Dodaje participantów do eksperymentu przez aktualizację additional_properties.
        Wykorzystuje wzorzec z frontend UI (participant_id w additional_properties).

        Args:
            experiment_id: MongoDB ID eksperymentu
            participants: Lista participantów (z mongo_id, name, source_id)
            dataset_id: ID datasetu

        Returns:
            True jeśli operacja zakończona sukcesem, False w przeciwnym razie
        """
        try:
            print(f"👥 Adding {len(participants)} participants to experiment: {experiment_id}")

            # KROK 1: Pobierz istniejący dokument eksperymentu
            experiment_doc = self.mongo_api_service.get_document(
                experiment_id,
                Collections.EXPERIMENT.value,
                dataset_id
            )

            if not experiment_doc:
                print(f"❌ Experiment {experiment_id} not found")
                return False

            experiment_name = experiment_doc.get("experiment_name", f"Experiment_{experiment_id}")
            print(f"✅ Retrieved experiment: {experiment_name}")

            # KROK 2: Przygotuj additional_properties z participant_id (wzorzec frontend)
            current_additional_properties = experiment_doc.get("additional_properties", [])
            if current_additional_properties is None:
                current_additional_properties = []
            # Sprawdź czy już są participanci w additional_properties
            existing_participant_ids = set()
            for prop in current_additional_properties:
                if prop.get("key") == "participant_id":
                    existing_participant_ids.add(prop.get("value"))

            print(f"📋 Existing participants in experiment: {len(existing_participant_ids)}")

            # KROK 3: Dodaj nowych participantów (unikaj duplikatów)
            new_participants_added = 0
            for participant in participants:
                participant_mongo_id = participant["mongo_id"]
                participant_name = participant["name"]

                if participant_mongo_id not in existing_participant_ids:
                    # Dodaj participant_id do additional_properties (wzorzec frontend)
                    current_additional_properties.append({
                        "key": "participant_id",
                        "value": participant_mongo_id
                    })
                    new_participants_added += 1
                    print(f"✅ Added participant to experiment: {participant_name} (ID: {participant_mongo_id})")
                else:
                    print(f"⚠️ Participant already in experiment: {participant_name} (ID: {participant_mongo_id})")

            if new_participants_added == 0:
                print(f"ℹ️ No new participants to add to experiment {experiment_name}")
                return True

            # KROK 4: Zaktualizuj dokument eksperymentu (replace całego dokumentu)
            experiment_doc["additional_properties"] = current_additional_properties

            self.mongo_api_service.update_document_with_dict(
                collection_name=Collections.EXPERIMENT.value,
                id=experiment_id,
                new_document=experiment_doc,
                dataset_id=dataset_id
            )

            print(f"🎉 Successfully added {new_participants_added} participants to experiment '{experiment_name}'")
            print(
                f"📊 Total participants in experiment: {len([p for p in current_additional_properties if p.get('key') == 'participant_id'])}")

            return True

        except Exception as e:
            print(f"❌ Error adding participants to experiment {experiment_id}: {str(e)}")
            return False

    def _process_participants_for_experiments(self, experiments: List[Dict[str, Any]], import_id: str,
                                              dataset_id: str) -> int:
        """
        Przetwarza i dodaje participantów do eksperymentów zaimportowanych w tym import job.

        Args:
            experiments: Lista słowników z danymi eksperymentów
            import_id: ID procesu importu
            dataset_id: ID datasetu

        Returns:
            Liczba zaktualizowanych eksperymentów
        """
        try:
            print(f"👥 Starting participant processing for {len(experiments)} experiments")

            # KROK 1: Znajdź wszystkich participantów z tego import job (raz dla wszystkich eksperymentów)
            participants = self._find_imported_participants(import_id, dataset_id)

            if not participants:
                print(f"ℹ️ No participants found for import job: {import_id}")
                return 0

            print(f"📊 Found {len(participants)} participants to add to experiments")

            # KROK 2: Dla każdego eksperymentu dodaj participantów
            updated_count = 0
            for experiment_doc in experiments:
                experiment_id = str(experiment_doc.get("id", "unknown"))
                print(f"🧪 Processing experiment: {experiment_id}")

                if self._add_participants_to_experiment(experiment_id, participants, dataset_id):
                    updated_count += 1
                    print(f"✅ Experiment '{experiment_id}' updated successfully with participants")
                else:
                    print(f"❌ Error updating experiment {experiment_id} with participants")
                    self._log_import_error(
                        import_id,
                        dataset_id,
                        "EXPERIMENT_PARTICIPANT_UPDATE_FAILED",
                        f"Failed to add participants to experiment {experiment_id}",
                        experiment_id
                    )

            print(f"📈 Participant processing summary: {updated_count}/{len(experiments)} experiments updated")
            return updated_count

        except Exception as e:
            print(f"❌ Error processing participants for experiments: {str(e)}")
            self._log_import_error(
                import_id,
                dataset_id,
                "PARTICIPANT_PROCESSING_ERROR",
                f"Error processing participants for experiments: {str(e)}"
            )
            return 0

    ## FIXME 2 duplikaty
    def _find_activity_by_source_id(self, source_id: str, dataset_id: str) -> str:
        """Znajduje Activity w MongoDB po source_id i zwraca jego MongoDB ID"""
        return self._find_by_source_id(source_id, dataset_id, Collections.ACTIVITY)


    def _find_by_source_id(self, source_id: str, dataset_id: str, collection: Collections) -> str:
        """
        Uniwersalna metoda do znajdowania dokumentów po source_id
        """
        try:
            documents = self.mongo_api_service.get_documents(
                collection_name=collection.value,
                dataset_id=dataset_id,
                query={"external_id": source_id}
            )

            if documents:
                found_id = str(documents[0].get("id", ""))
                print(f"✅ Found {collection.value}: {source_id} -> MongoDB ID: {found_id}")
                return found_id

            print(f"❌ {collection.value} not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding {collection.value} by source_id {source_id}: {e}")
            return ""


    def _find_by_id(self, id: str, dataset_id: str, collection: Collections) -> str:
        """
        Uniwersalna metoda do znajdowania dokumentów po source_id
        """
        try:
            documents = self.mongo_api_service.get_documents(
                collection_name=collection.value,
                dataset_id=dataset_id,
                query={"_id": id}
            )

            if documents:
                found_id = str(documents[0].get("id", ""))
                print(f"✅ Found {collection.value}: {id} -> MongoDB ID: {found_id}")
                return documents[0]

            print(f"❌ {collection.value} not found for _id: {id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding {collection.value} by _id {id}: {e}")
            return ""

    def _log_import_error(
            self,
            import_id: str,
            dataset_id: str,
            error_type: str,
            error_message: str,
            entity_str: str = None
    ):
        """
        Loguje błąd importu do bazy danych używając FileOperationsStatusService
        """
        self.file_ops_service.log_error(
            operation_uuid=import_id,
            dataset_id=dataset_id,
            error_type=error_type,
            error_message=error_message,
            entity_str=entity_str
        ) 