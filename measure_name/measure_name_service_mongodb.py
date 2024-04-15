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

    def save_measure_name(self, measure_name: MeasureNameIn):
        """
        Send request to mongo api to create new measure name

        Args:
            measure_name (MeasureNameIn): Measure name to be added

        Returns:
            Result of request as measure name object
        """
        return self.create(measure_name)

    def get_measure_names(self):
        """
        Send request to mongo api to get all measure names

        Returns:
            Result of request as list of measure name objects
        """
        result_dict = self.get_multiple()
        results = [BasicMeasureNameOut(**result) for result in result_dict]
        return MeasureNamesOut(measure_names=results)

    def get_measure_name(
        self, measure_name_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given measure name

        Args:
            measure_name_id (int | str): identity of measure name
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as measure name object
        """
        return self.get_single(measure_name_id, depth, source)

    def _add_related_documents(self, measure_name: dict, depth: int, source: str):
        if source != Collections.MEASURE and depth > 0:
            measure_name["measures"] = self.measure_service.get_multiple(
                {"measure_name_id": measure_name["id"]},
                depth=depth - 1,
                source=Collections.MEASURE_NAME,
            )
