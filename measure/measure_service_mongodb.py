from typing import Union

from grisera import (
    MeasurePropertyIn,
    BasicMeasureOut,
    MeasuresOut,
    MeasureOut,
    MeasureIn,
    MeasureRelationIn,
)
from grisera import MeasureService
from grisera import MeasureNameService
from grisera import NotFoundByIdModel
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin


class MeasureServiceMongoDB(MeasureService, GenericMongoServiceMixin):
    """
    Object to handle logic of measure requests

    Attributes:
        mongo_api_service (MongoApiService): Service used to communicate with Mongo API
        measure_name_service (MeasureNameService): Service to manage measure name models
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = MeasureOut
        self.time_series_service = None
        self.measure_name_service = None

    def save_measure(self, measure: MeasureIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new measure

        Args:
            measure (MeasureIn): Measure to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as measure object
        """
        related_mn = self.measure_name_service.get_measure_name(measure.measure_name_id, dataset_id)
        mn_exists = type(related_mn) is not NotFoundByIdModel
        if measure.measure_name_id is not None and not mn_exists:
            return MeasureOut(errors={"errors": "given measure name does not exist"})

        return self.create(measure, dataset_id)

    def get_measures(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get measures

        Args:
            dataset_id (int | str): name of dataset
            query (dict): query for filtering measures

        Returns:
            Result of request as list of measures objects
        """
        measures_dict = self.get_multiple(dataset_id, query)
        results = [BasicMeasureOut(**result) for result in measures_dict]
        return MeasuresOut(measures=results)

    def get_measure(
        self, measure_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given measure

        Args:
            measure_id (int | str): identity of measure
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as measure object
        """
        return self.get_single(measure_id, dataset_id, depth, source)

    def delete_measure(self, measure_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given measure

        Args:
            measure_id (int | str): identity of measure
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as measure object
        """
        return self.delete(measure_id, dataset_id)

    def update_measure(self, measure_id: Union[int, str], measure: MeasurePropertyIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to update given measure

        Args:
            measure_id (int | str): identity of measure
            measure (MeasurePropertyIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as measure object
        """
        existing_measure = self.get_measure(measure_id, dataset_id)
        for field, value in measure.dict().items():
            setattr(existing_measure, field, value)

        self.mongo_api_service.update_document(
            measure_id,
            existing_measure,
            dataset_id,
        )
        return existing_measure

    def update_measure_relationships(
        self, measure_id: Union[int, str], measure: MeasureRelationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given measure

        Args:
            measure_id (int | str): identity of measure
            measure (MeasureRelationIn): Relationships to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as measure object
        """
        existing_measure = self.get_measure(measure_id, dataset_id)



        if type(existing_measure) is NotFoundByIdModel:
            return existing_measure



        related_mn = self.measure_name_service.get_measure_name(measure.measure_name_id, dataset_id)
        mn_exists = type(related_mn) is not NotFoundByIdModel
        if measure.measure_name_id is not None and not mn_exists:
            return MeasureOut(errors={"errors": "given measure name does not exist"})

        existing_measure_in = MeasureIn(**existing_measure.dict())

        existing_measure_in.measure_name_id = measure.measure_name_id

        self.mongo_api_service.update_document(
            measure_id,
            existing_measure_in,
            dataset_id
        )
        return self.get_measure(measure_id, dataset_id)


    def _add_related_documents(self, measure: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_time_series(measure, dataset_id, depth, source)
            self._add_related_measure_name(measure, dataset_id, depth, source)

    def _add_related_time_series(self, measure: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.TIME_SERIES:
            measure["time_series"] = self.time_series_service.get_multiple(
                dataset_id,
                {"measure_id": measure["id"]},
                depth=depth - 1,
                source=Collections.MEASURE,
            )

    def _add_related_measure_name(self, measure: dict, dataset_id: Union[int, str], depth: int, source: str):
        has_related_measure_name = measure["measure_name_id"] is not None
        if source != Collections.MEASURE_NAME and has_related_measure_name:
            measure["measure_name"] = self.measure_name_service.get_single_dict(
                measure["measure_name_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.MEASURE,
            )
