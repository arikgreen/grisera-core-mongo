from typing import Union

from grisera import (
    ExperimentIn,
    ExperimentsOut,
    BasicExperimentOut,
    ExperimentOut,
)
from grisera import ExperimentService
from grisera import NotFoundByIdModel
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import ScenarioService


class ExperimentServiceMongoDB(ExperimentService, GenericMongoServiceMixin):
    """
    Object to handle logic of experiments requests
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = ExperimentOut
        self.scenario_service: ScenarioService = None

    def save_experiment(self, experiment: ExperimentIn):
        """
        Send request to mongo api to create new experiment

        Args:
            experiment (ExperimentIn): Experiment to be added

        Returns:
            Result of request as experiment object
        """
        return self.create(experiment)

    def get_experiments(self, query: dict = {}):
        """
        Send request to mongo api to get experiments

        Returns:
            Result of request as list of experiments objects
        """
        results_dict = self.get_multiple(query)
        experiments = [BasicExperimentOut(**result) for result in results_dict]
        return ExperimentsOut(experiments=experiments)

    def get_experiment(
        self, experiment_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given experiment

        Args:
            experiment_id (int | str): identity of experiment
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as experiment object
        """
        return self.get_single(experiment_id, depth, source)

    def delete_experiment(self, experiment_id: int):
        """
        Send request to mongo api to delete given experiment

        Args:
        experiment_id (int): Id of experiment

        Returns:
            Result of request as experiment object
        """
        return self.delete(experiment_id)

    def update_experiment(self, experiment_id: int, experiment: ExperimentIn):
        """
        Send request to mongo api to update given experiment

        Args:
        experiment_id (int): Id of experiment
        experiment (ExperimentIn): Properties to update

        Returns:
            Result of request as experiment object
        """
        existing_activity_execution = self.get_experiment(experiment_id)
        for field, value in experiment.dict().items:
            setattr(existing_activity_execution, field, value)

        return BasicExperimentOut(**existing_activity_execution)

    def _add_related_documents(self, experiment: dict, depth: int, source: str):
        if depth <= 0 or source == Collections.ACTIVITY_EXECUTION:
            return

        related_scenario = self.scenario_service.get_scenario_by_experiment(
            experiment["id"]
        )
        if type(related_scenario) is NotFoundByIdModel:
            return

        experiment["activity_executions"] = related_scenario.activity_executions
