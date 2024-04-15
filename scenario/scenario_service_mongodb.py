from typing import List, Union

from grisera import ActivityExecutionService
from grisera import ExperimentOut
from grisera import ExperimentService
from mongo_service.collection_mapping import Collections
from grisera import (
    ScenarioIn,
    ScenarioOut,
    OrderChangeIn,
    OrderChangeOut,
)
from grisera import (
    ActivityExecutionIn,
)
from grisera import NotFoundByIdModel
from grisera import ScenarioService
from mongo_service.service_mixins import (
    GenericMongoServiceMixin,
)


class ScenarioServiceMongoDB(ScenarioService, GenericMongoServiceMixin):
    """
    Object to handle logic of scenarios requests

    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    activity_execution_service (ActivityExecutionService): Service used to communicate with ActivityExecution
    experiment_service (ExperimentService): Service used to communicate with Experiment
    """

    def __init__(self):
        super().__init__()
        self.activity_execution_service: ActivityExecutionService = None
        self.experiment_service: ExperimentService = None

    def save_scenario(self, scenario: ScenarioIn):
        """
        Send request to mongo api to create new scenario

        Args:
            scenario (ScenarioIn): Scenario to be added

        Returns:
            Result of request as scenario object
        """

        related_experiment = self.experiment_service.get_experiment(
            scenario.experiment_id
        )
        related_experiment_exists = related_experiment is not NotFoundByIdModel
        if scenario.experiment_id is not None and not related_experiment_exists:
            return ScenarioOut(errors={"errors": "given channel does not exist"})

        activity_executions = [
            self.activity_execution_service.save_activity_execution(
                activity_execution=activity_execution
            )
            for activity_execution in scenario.activity_executions
        ]
        activity_executions_ids = [ae.id for ae in activity_executions]

        scenario = ScenarioIn(**scenario.dict())
        scenario_dict = scenario.dict()
        scenario_dict[
            "activity_executions"
        ] = activity_executions_ids  # only ids are saved to db
        created_scenario_id = self.mongo_api_service.create_document_from_dict(
            scenario_dict, Collections.SCENARIO
        )
        scenario_dict["activity_executions"] = activity_executions
        return ScenarioOut(**scenario_dict)

    def add_activity_execution(
        self, previous_id: Union[int, str], activity_execution: ActivityExecutionIn
    ):
        """
        Send request to mongo api to add activity_execution to scenario after the activity execution with previous_id.
        If previous_id is an identity of an experiment then activity execution is set as a first one in the scenario,
        otherwise it is added after the previous one identified with previous_id

        Args:
            previous_id (int | str): identity of previous activity_execution or experiment
            activity_execution (ActivityExecutionIn): ActivityExecution to be added

        Returns:
            Result of request as activity_execution object
        """
        activity_execution = self.activity_execution_service.save_activity_execution(
            activity_execution=activity_execution
        )
        new_activity_execution_id = activity_execution.id

        self._put_activity_execution_after_element(
            previous_id, new_activity_execution_id
        )

        return activity_execution

    def change_order(self, order_change: OrderChangeIn):
        """
        Send request to mongo api to change order in scenario

        Args:
            order_change (OrderChangeIn): Ids of activity_executions to change order by

        Returns:
            Result of request as changed order ids
        """
        activity_execution_id = order_change.activity_execution_id
        self.delete_activity_execution(activity_execution_id)

        previous_id = order_change.previous_id
        self._put_activity_execution_after_element(previous_id, activity_execution_id)

        return OrderChangeOut(**OrderChangeIn.dict())

    def _put_activity_execution_after_element(
        self,
        previous_id: Union[int, str],
        activity_execution_id: Union[int, str],
    ):
        scenario, related_element = self.get_scenario_by_element_id(previous_id)
        if type(scenario) is NotFoundByIdModel:
            return scenario
        scenario_dict = self.get_scenario_dict_by_scenario_id(scenario.id)

        is_from_experiment = type(related_element) is ExperimentOut
        if is_from_experiment:
            new_activity_execution_index = 0
        else:
            previous_activity_execution_index = scenario_dict[
                "activity_executions"
            ].index(previous_id)
            new_activity_execution_index = previous_activity_execution_index + 1
        scenario_dict["activity_executions"].insert(
            new_activity_execution_index, activity_execution_id
        )

        self.mongo_api_service.update_document_with_dict(
            Collections.SCENARIO, scenario.id, scenario_dict
        )  # update must be performed with dict, as model is different from saved scenarios (only ae ids are stored)

    def delete_activity_execution(self, activity_execution_id: Union[int, str]):
        """
        Send request to mongo api to delete activity_execution from scenario

        Args:
            activity_execution_id (int | str): identity of activity_execution to delete

        Returns:
            Result of request as activity_execution object
        """
        scenario = self.get_scenario_by_activity_execution(activity_execution_id)
        if type(scenario) is NotFoundByIdModel:
            return scenario
        scenario_dict = self.get_scenario_dict_by_scenario_id(scenario.id)
        scenario_dict["activity_executions"].remove(activity_execution_id)

        self.mongo_api_service.update_document_with_dict(
            Collections.SCENARIO, scenario.id, scenario_dict
        )  # update must be performed with dict, as model is different from saved scenarios (only ae ids are stored)

        return self.activity_execution_service.get_activity_execution(
            activity_execution_id
        )

    def get_scenario_dict_by_scenario_id(self, scenario_id: Union[int, str]):
        """Return scenario dict directly from db (without parsing ae ids to objects)"""
        return self.mongo_api_service.get_document(scenario_id, Collections.SCENARIO)

    def get_scenario_by_element_id(self, element_id: Union[int, str], depth: int):
        """
        Send request to mongo api to get activity executions and experiment from scenario

        Args:
            element_id (int | str): identity of experiment or activity execution which is included in scenario
            depth: (int): specifies how many related entities will be traversed to create the response

        Returns:
            Result of request as Scenario object and element specified by element_id
        """
        experiment_result = self.experiment_service.get_experiment(
            experiment_id=element_id
        )
        if type(experiment_result) is not NotFoundByIdModel:
            scenario = self.get_scenario_by_experiment(element_id, depth)
            return scenario, experiment_result

        activity_execution_result = (
            self.activity_execution_service.get_activity_execution(element_id)
        )
        if type(activity_execution_result) is not NotFoundByIdModel:
            scenario = self.get_scenario_by_activity_execution(element_id, depth)
            return scenario, activity_execution_result

        return (
            NotFoundByIdModel(
                id=element_id,
                errors=f"No activity execution or expriment with given id ({element_id}) found",
            ),
            None,
        )

    def get_scenario(self, element_id: Union[int, str], depth: int = 0):
        """
        Send request to mongo api to get activity executions and experiment from scenario

        Args:
            element_id (int | str): identity of experiment or activity execution which is included in scenario
            depth: (int): specifies how many related entities will be traversed to create the response

        Returns:
            Result of request as Scenario object
        """
        scenario, _ = self.get_scenario_by_element_id(element_id, depth)
        return scenario

    def get_scenario_by_activity_execution(
        self,
        activity_execution_id: Union[int, str],
        depth: int = 0,
        multiple: bool = False,
    ):
        """
        Send request to mongo api to get activity_executions from scenario which has activity execution id included

        Args:
            activity_execution_id (int | str): identity of activity execution included in scenario
            depth: (int): specifies how many related entities will be traversed to create the response
            multiple (bool): specifies if all scenarios should be returned or just first found

        Returns:
            Result of request as Scenario object
        """
        query = {"activity_executions": activity_execution_id}
        scenarios = self.get_multiple(query)
        if len(scenarios) == 0:
            return NotFoundByIdModel(
                id=activity_execution_id,
                errors="Given activity execution found, but it is not assigned to any scenario",
            )

        if multiple:
            [
                self._change_ae_ids_to_objects(
                    scenario, depth, source=Collections.ACTIVITY_EXECUTION
                )
                for scenario in scenarios
            ]
            return [ScenarioOut(**scenario) for scenario in scenarios]

        scenario = scenarios[0]
        self._change_ae_ids_to_objects(
            scenario, depth, source=Collections.ACTIVITY_EXECUTION
        )

        return ScenarioOut(**scenario)

    def get_scenario_by_experiment(
        self, experiment_id: Union[int, str], depth: int = 0
    ):
        """
        Send request to mongo api to get activity_executions from scenario which starts in experiment

        Args:
            experiment_id (int | str): identity of experiment where scenario starts
            depth: (int): specifies how many related entities will be traversed to create the response

        Returns:
            Result of request as Scenario object
        """
        query = {"experiment_id": experiment_id}
        scenarios = self.get_multiple(query)
        if len(scenarios) == 0:
            return NotFoundByIdModel(
                id=experiment_id,
                errors="Given experiment found, but it is not assigned to any scenario",
            )

        scenario = scenarios[0]
        scenario = self._change_ae_ids_to_objects(
            scenario, depth, source=Collections.EXPERIMENT
        )

        return ScenarioOut(**scenario)

    def _change_ae_ids_to_objects(self, scenario: List, depth: int, source: str):
        """Get activity executions objects based on id list"""
        activity_execution_ids = scenario["activity_executions"]
        scenario["activity_executions"] = [
            self.activity_execution_service.get_activity_execution(
                activity_execution_id=ae_id, depth=depth, source=source
            )
            for ae_id in activity_execution_ids
        ]
        return scenario

    def _check_activity_executions(self, activity_execution_ids: List):
        existing_activity_executions = self.activity_execution_service.get_multiple(
            query={
                "id": self.mongo_api_service.get_id_in_query(activity_execution_ids)
            },
        )
        all_given_ae_extist = len(existing_activity_executions) == len(
            activity_execution_ids
        )
        return all_given_ae_extist

    def _add_related_documents(self, experiment: dict, depth: int, source: str):
        pass  # this method is not used in scenario
