from typing import Union

from grisera import ActivityExecutionService
from grisera import ArrangementService
from grisera import (
    ArrangementIn,
    ArrangementOut,
    ArrangementsOut,
    BasicArrangementOut,
)
from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.collection_mapping import Collections


class ArrangementServiceMongoDB(ArrangementService, GenericMongoServiceMixin):
    """
    Object to handle logic of arrangement requests
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ArrangementOut
        self.activity_execution_service: ActivityExecutionService = None

    def save_arrangement(self, arrangement: ArrangementIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new arrangement

        Args:
            arrangement (ArrangementIn): Arrangement to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as arrangement object
        """
        return self.create(arrangement, dataset_id)

    def get_arrangements(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all arrangements

        Args:
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as list of arrangement objects
        """
        arrangements_dict = self.get_multiple(dataset_id)
        arrangements = [
            BasicArrangementOut(**arrangement_dict)
            for arrangement_dict in arrangements_dict
        ]
        return ArrangementsOut(arrangements=arrangements)

    def get_arrangement(
            self, arrangement_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given arrangement

        Args:
            depth: (int): specifies how many related entities will be traversed to create the response
            arrangement_id (int | str): identity of arrangement
            dataset_id (int | str): name of dataset
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as arrangement object
        """
        return self.get_single(arrangement_id, dataset_id, depth, source)

    def delete_arrangement(self, arrangement_id: int, dataset_id: Union[int, str]):
        return self.delete(arrangement_id, dataset_id)

    def update_arrangement(self, arrangement_id: int, arrangement: ArrangementIn, dataset_id: Union[int, str]):
        return self.update(arrangement_id, arrangement, dataset_id)

    def _add_related_documents(self, arrangement: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.ACTIVITY_EXECUTION and depth > 0:
            arrangement[
                "activity_executions"
            ] = self.activity_execution_service.get_multiple(
                dataset_id,
                {"arrangement_id": arrangement["id"]},
                depth=depth - 1,
                source=Collections.ARRANGEMENT,
            )
