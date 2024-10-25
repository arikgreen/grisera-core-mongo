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

    def save_experiment(self, experiment: ExperimentIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new experiment

        Args:
            experiment (ExperimentIn): Experiment to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as experiment object
        """
        return self.create(experiment, dataset_id)

    def get_experiments(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get experiments

        Args:
            dataset_id (int | str): name of dataset
            query: Query to mongo api. Empty by default.

        Returns:
            Result of request as list of experiments objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        experiments = [BasicExperimentOut(**result) for result in results_dict]
        return ExperimentsOut(experiments=experiments)

    def get_experiment(
        self, experiment_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given experiment

        Args:
            experiment_id (int | str): identity of experiment
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as experiment object
        """
        return self.get_single(experiment_id, dataset_id, depth, source)

    def delete_experiment(self, experiment_id: int, dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given experiment

        Args:
            experiment_id (int): Id of experiment
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as experiment object
        """
        return self.delete(experiment_id, dataset_id)

    def update_experiment(self, experiment_id: int, experiment: ExperimentIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to update given experiment

        Args:
            experiment_id (int): Id of experiment
            experiment (ExperimentIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as experiment object
        """
        return self.update(experiment_id, experiment, dataset_id)

    def _add_related_documents(self, experiment: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth <= 0 or source == Collections.ACTIVITY_EXECUTION or source == Collections.EXPERIMENT:
            return
        source = source if source != "" else Collections.EXPERIMENT

        related_scenario = self.scenario_service.get_scenarios_by_experiment(
            experiment["id"],
            dataset_id,
            depth=depth,
            source=source,
        )
        if type(related_scenario) is NotFoundByIdModel:
            return

        experiment["scenarios"] = related_scenario
