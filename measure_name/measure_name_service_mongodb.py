from typing import Union

from grisera import MeasureService
from grisera import (
    MeasureNameIn,
    MeasureNameOut,
    MeasureNamesOut,
    BasicMeasureNameOut,
)
from grisera import MeasureNameService
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin


class MeasureNameServiceMongoDB(MeasureNameService, GenericMongoServiceMixin):
    """
    Object to handle logic of measure name requests

    Attributes:
        mongo_api_service (MongoApiService): Service used to communicate with Mongo API
        measure_name_service (MeasureNameService): Service to manage measure name models
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.measure_service: MeasureService = None
        self.model_out_class = MeasureNameOut

    def save_measure_name(self, measure_name: MeasureNameIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new measure name

        Args:
            measure_name (MeasureNameIn): Measure name to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as measure name object
        """
        return self.create(measure_name, dataset_id)

    def get_measure_names(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all measure names

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of measure name objects
        """
        result_dict = self.get_multiple(dataset_id)
        results = [BasicMeasureNameOut(**result) for result in result_dict]
        return MeasureNamesOut(measure_names=results)

    def get_measure_name(
        self, measure_name_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given measure name

        Args:
            measure_name_id (int | str): identity of measure name
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as measure name object
        """
        return self.get_single(measure_name_id, dataset_id, depth, source)

    def delete_measure_name(self, measure_name_id: int, dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given measure_name
        Args:
            measure_name_id (int): ID of measure_name
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as measure_name object
        """
        return self.delete(measure_name_id, dataset_id)

    def update_measure_name(self, measure_name_id: int, measure_name: MeasureNameIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to update given measure_name
        Args:
            measure_name_id (int): ID of measure_name
            measure_name (MeasureNameIn): Measure_name to be updated
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as measure_name object
        """
        return self.update(measure_name_id, measure_name, dataset_id)

    def _add_related_documents(self, measure_name: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.MEASURE and depth > 0:
            measure_name["measures"] = self.measure_service.get_multiple(
                dataset_id,
                {"measure_name_id": measure_name["id"]},
                depth=depth - 1,
                source=Collections.MEASURE_NAME,
            )
