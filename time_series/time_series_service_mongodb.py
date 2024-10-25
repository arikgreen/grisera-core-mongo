from typing import Union, Optional, List

import bson

from starlette.datastructures import QueryParams
from grisera import TimeSeriesTransformationMultidimensional
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from grisera import (
    TimeSeriesPropertyIn,
    BasicTimeSeriesOut,
    TimeSeriesNodesOut,
    TimeSeriesOut,
    TimeSeriesIn,
    TimeSeriesRelationIn,
    TimeSeriesTransformationIn,
    SignalIn,
    SignalValueNodesIn,
    Type,
)
from grisera import NotFoundByIdModel
from grisera import TimeSeriesService
from grisera import (
    TimeSeriesTransformationFactory,
)


class TimeSeriesServiceMongoDB(TimeSeriesService):
    """
    Object to handle logic of time series requests

    Attributes:
        mongo_api_service (MongoApiService): Service used to communicate with MongoDB API
        measure_service (MeasureService): Service to manage measure models
        observable_information_service (ObservableInformationService): Service to manage observable information models
    """

    def __init__(self):
        self.mongo_api_service = MongoApiService()
        self.model_out_class = TimeSeriesOut
        self.measure_service = None
        self.observable_information_service = None

    def save_time_series(self, time_series: TimeSeriesIn, dataset_id: Union[int, str]):
        """
        Send request to graph api to create new time series

        Args:
            time_series (TimeSeriesIn): Time series to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as time series object
        """
        if (
            not time_series.observable_information_ids
            and time_series.observable_information_id
        ):
            time_series.observable_information_ids = [
                time_series.observable_information_id
            ]
        if (
            time_series.observable_information_ids
            and not self._check_related_observable_informations(
                time_series.observable_information_ids, dataset_id
            )
        ):
            return NotFoundByIdModel(
                errors={"errors": "given observable information does not exist"}
            )

        related_measure = self.measure_service.get_measure(time_series.measure_id, dataset_id)
        related_measure_exists = type(related_measure) is not NotFoundByIdModel
        if time_series.measure_id is not None and not related_measure_exists:
            return NotFoundByIdModel(errors={"errors": "given measure does not exist"})

        if len(time_series.signal_values) == 0:
            if time_series.type == Type.timestamp:
                time_series.signal_values = [
                    SignalIn(signal_value=SignalValueNodesIn(value=1), timestamp=1)
                ]
            else:
                time_series.signal_values = [
                    SignalIn(signal_value=SignalValueNodesIn(value=1), start_timestamp=1, end_timestamp=2)
                ]
        created_ts_id = self.mongo_api_service.create_time_series(
            time_series_in=time_series,
            dataset_id=dataset_id,
        )
        return self.get_time_series(created_ts_id, dataset_id)

    def get_multiple(
        self, dataset_id: Union[int, str], query: dict = {}, depth: int = 0, source: str = "", query_params=None
    ):
        results_dict = self.mongo_api_service.get_many_time_series(dataset_id, query, query_params)

        for result in results_dict:
            self._add_related_documents(result, dataset_id, depth, source)

        return results_dict

    def get_time_series_nodes(self, dataset_id: Union[int, str], params: QueryParams = None):
        """
        Send request to graph api to get time series nodes

        Returns:
            Result of request as list of time series nodes objects
        """
        time_series_dicts = self.get_multiple(query_params=params, dataset_id=dataset_id)
        results = [BasicTimeSeriesOut(**ts_dict) for ts_dict in time_series_dicts]
        return TimeSeriesNodesOut(time_series_nodes=results)

    def get_time_series(
        self,
        time_series_id: Union[int, str],
        dataset_id: Union[int, str],
        depth: int = 0,
        signal_min_value: Optional[int] = None,
        signal_max_value: Optional[int] = None,
        source: str = "",
    ):
        """
        Send request to graph api to get given time series

        Args:
            time_series_id (int | str): identity of time series
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            signal_min_value (Optional[int]): Filter signal values by min value
            signal_max_value (Optional[int]): Filter signal values by max value
            source: Helper arguments that specifies direction of collection traversion

        Returns:
            Result of request as time series object
        """
        try:
            bson.ObjectId(time_series_id)
        except bson.errors.InvalidId:
            return NotFoundByIdModel(id=time_series_id, errors="Invalid ID")
        time_series = self.mongo_api_service.get_time_series(
            ts_id=time_series_id,
            signal_min_value=signal_min_value,
            signal_max_value=signal_max_value,
            dataset_id=dataset_id
        )
        self._add_related_documents(time_series, dataset_id, depth, source)
        if type(time_series) == NotFoundByIdModel:
            return time_series
        return TimeSeriesOut(**time_series)

    def get_time_series_multidimensional(self, time_series_ids: List[Union[int, str]], dataset_id: Union[int, str]):
        """
        Send request to graph api to get given time series
        Args:
            time_series_ids (int | str): Ids of the time series
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as time series object
        """
        source_time_series = []
        for time_series_id in time_series_ids:
            time_series = self.get_time_series(time_series_id, dataset_id)
            if time_series.errors is not None:
                return time_series
            source_time_series.append(time_series)
        result = TimeSeriesTransformationMultidimensional().transform(
            source_time_series
        )
        for time_series in source_time_series:
            time_series.signal_values = []
        result.time_series = source_time_series
        return result

    def delete_time_series(self, time_series_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to graph api to delete given time series

        Args:
            time_series_id (int | str): identity of time series
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as time series object
        """
        get_response = self.get_time_series(time_series_id, dataset_id)
        self.mongo_api_service.delete_time_series(time_series_id, dataset_id)
        return get_response

    def update_time_series(
        self, time_series_id: Union[int, str], time_series: TimeSeriesPropertyIn, dataset_id: Union[int, str]
    ):
        """
        Send request to graph api to update given time series

        Args:
            time_series_id (int | str): identity of time series
            time_series (TimeSeriesPropertyIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as time series object
        """
        time_series.signal_values = []
        update_dict = time_series.dict()
        update_dict.pop("signal_values")
        self.mongo_api_service.update_time_series_metadata(update_dict, time_series_id, dataset_id)
        return self.get_time_series(time_series_id, dataset_id)

    def update_time_series_relationships(
        self, time_series_id: Union[int, str], time_series: TimeSeriesRelationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to graph api to update given time series

        Args:
            time_series_id (int | str): identity of time series
            time_series (TimeSeriesRelationIn): Relationships to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as time series object
        """
        if (
            not time_series.observable_information_ids
            and time_series.observable_information_id
        ):
            time_series.observable_information_ids = [
                time_series.observable_information_id
            ]
        get_response = self.get_time_series(time_series_id, dataset_id)

        if type(get_response) is NotFoundByIdModel:
            return get_response

        if not self._check_related_observable_informations(
            time_series.observable_information_ids, dataset_id
        ):
            return TimeSeriesOut(
                errors={"errors": "given observable information does not exist"}
            )

        related_measure = self.measure_service.get_measure(time_series.measure_id, dataset_id)
        related_measure_exists = type(related_measure) is not NotFoundByIdModel
        if time_series.measure_id is not None and not related_measure_exists:
            return TimeSeriesOut(errors={"errors": "given measure does not exist"})

        self.mongo_api_service.update_time_series_metadata(
            time_series.dict(), time_series_id, dataset_id
        )
        return self.get_time_series(time_series_id, dataset_id)

    def transform_time_series(
        self, time_series_transformation: TimeSeriesTransformationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to graph api to create new transformed time series

        Args:
            time_series_transformation (TimeSeriesTransformationIn): Time series transformation parameters
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as time series object
        """
        source_time_series = []
        for time_series_id in time_series_transformation.source_time_series_ids:
            time_series = self.get_time_series(time_series_id, dataset_id)
            if time_series.errors is not None:
                return time_series
            source_time_series.append(time_series)
        try:
            new_time_series, new_signal_values_id_mapping = (
                TimeSeriesTransformationFactory()
                .get_transformation(time_series_transformation.name)
                .transform(
                    source_time_series, time_series_transformation.additional_properties
                )
            )
        except Exception as e:
            return TimeSeriesNodesOut(errors=str(e))
        new_time_series.measure_id = time_series_transformation.destination_measure_id
        new_time_series.observable_information_ids = (
            time_series_transformation.destination_observable_information_ids
        )

        result = self.save_time_series(new_time_series, dataset_id)

    def get_time_series_for_observable_information(
        self,
        observable_information_id: Union[str, int],
        dataset_id: Union[int, str],
        depth: int = 0,
        source: str = "",
    ):
        query = {"metadata.observable_information_ids": observable_information_id}
        return self.get_multiple(dataset_id, query, depth, source)

    def _add_related_documents(self, time_series: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_measure(time_series, dataset_id, depth, source)
            self._add_observable_informations(time_series, dataset_id, depth, source)

    def _add_measure(self, time_series: dict, dataset_id: Union[int, str], depth: int, source: str):
        has_related_measure = time_series["measure_id"] is not None
        if source != Collections.MEASURE and has_related_measure:
            time_series["measure"] = self.measure_service.get_single_dict(
                time_series["measure_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.TIME_SERIES,
            )

    def _add_observable_informations(self, time_series: dict, dataset_id: Union[int, str], depth: int, source: str):
        if time_series["observable_information_ids"] is None:
            return
        if source != Collections.OBSERVABLE_INFORMATION:
            time_series[
                "observable_informations"
            ] = self.observable_information_service.get_multiple(
                dataset_id,
                {
                    "id": self.mongo_api_service.get_id_in_query(
                        time_series["observable_information_ids"]
                    )
                },
                depth=depth - 1,
                source=Collections.TIME_SERIES,
            )

    def _check_related_observable_informations(self, observable_information_ids: List, dataset_id: Union[int, str]):
        existing_observable_informations = (
            self.observable_information_service.get_multiple(
                dataset_id=dataset_id,
                query={
                    "id": self.mongo_api_service.get_id_in_query(
                        observable_information_ids
                    )
                },
            )
        )
        all_given_oi_exist = len(existing_observable_informations) == len(
            observable_information_ids
        )
        return all_given_oi_exist
