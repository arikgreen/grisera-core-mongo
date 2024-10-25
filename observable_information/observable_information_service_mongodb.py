from typing import Union
from bson import ObjectId
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import (
    ObservableInformationIn,
    ObservableInformationOut,
    BasicObservableInformationOut,
    ObservableInformationsOut,
)
from grisera import (
    ObservableInformationService,
)
from grisera import NotFoundByIdModel


class ObservableInformationServiceMongoDB(
    ObservableInformationService, GenericMongoServiceMixin
):
    """
    Object to handle logic of observable information requests Observable information documents
    are embedded within recording documents.

    Attributes:
    recording_service (RecordingService): Service used to communicate with Recording
    modality_service (ModalityService): Service used to communicate with Modality
    life_activity_service (LifeActivityService): Service used to communicate with Life Activity
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ObservableInformationOut
        self.recording_service = None
        self.life_activity_service = None
        self.modality_service = None
        self.time_series_service = None

    def save_observable_information(
        self, observable_information: ObservableInformationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to create new observable information. Saving is performed by
        recording service, as observable information documents are embedded within recording
        documents.

        Args:
            observable_information (ObservableInformationIn): Observable information to be added.
            recording_id here is required

        Returns:
            Result of request as observable information object
        """
        related_recording = self.recording_service.get_recording(
            observable_information.recording_id, dataset_id
        )
        related_recording_exists = type(related_recording) is not NotFoundByIdModel
        if not related_recording_exists:
            return ObservableInformationOut(
                errors={"errors": "given recording does not exist"}
            )

        related_modality = self.modality_service.get_modality(
            observable_information.modality_id, dataset_id
        )
        related_modality_exists = type(related_modality) is not NotFoundByIdModel
        if (
            observable_information.modality_id is not None
            and not related_modality_exists
        ):
            return ObservableInformationOut(
                errors={"errors": "given modality does not exist"}
            )

        related_life_activity = self.life_activity_service.get_life_activity(
            observable_information.life_activity_id, dataset_id
        )
        related_life_activity_exists = type(related_life_activity) is not NotFoundByIdModel
        if (
            observable_information.life_activity_id is not None
            and not related_life_activity_exists
        ):
            return ObservableInformationOut(
                errors={"errors": "given life activity does not exist"}
            )

        return self.recording_service.add_observable_information(observable_information, dataset_id)

    def get_multiple(
        self, dataset_id: Union[int, str], query: dict = {}, depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get multiple observable informations based on query. Query has to be adjusted, as observable
        information documents are embedded within recording documents.
        """
        recording_query = {
            f"{Collections.OBSERVABLE_INFORMATION}.{field}": value
            for field, value in query.items()
        }
        recording_results = self.recording_service.get_multiple(
            dataset_id,
            recording_query,
            depth=depth - 1,
            source=Collections.OBSERVABLE_INFORMATION,
            projection=self._get_recording_projection(query),
        )
        result = []
        for recording_result in recording_results:
            if "observable_informations" in recording_result:
                observable_informations = recording_result["observable_informations"]
                del recording_result["observable_informations"]
                for observable_information in observable_informations:
                    self._add_related_documents(
                        observable_information,
                        dataset_id,
                        depth,
                        source,
                        recording_result,
                    )
                result += observable_informations

        return result

    def get_observable_informations(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all observable informations.
        """
        observable_information_dicts = self.get_multiple(dataset_id)
        results = [
            BasicObservableInformationOut(**result)
            for result in observable_information_dicts
        ]
        return ObservableInformationsOut(observable_informations=results)

    def get_single_dict(
        self, id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get observable information dict. Observable information is fetched from its
        recording.
        """
        observable_information_object_id = ObjectId(id)
        recording_result = self.recording_service.get_multiple(
            dataset_id,
            {
                f"{Collections.OBSERVABLE_INFORMATION}.id": observable_information_object_id
            },
            depth=depth - 1,
            source=Collections.OBSERVABLE_INFORMATION,
            projection=self._get_recording_projection(
                {"id": observable_information_object_id}
            ),
        )
        if (
            len(recording_result) == 0
            or len(recording_result[0][Collections.OBSERVABLE_INFORMATION]) == 0
        ):
            return NotFoundByIdModel(
                id=id,
                errors={"errors": "observable information not found"},
            )
        related_recording = recording_result[0]
        observable_information_dict = related_recording[
            Collections.OBSERVABLE_INFORMATION
        ][0]
        del related_recording[Collections.OBSERVABLE_INFORMATION]
        self._add_related_documents(
            observable_information_dict, dataset_id, depth, source, related_recording
        )
        return observable_information_dict

    def get_single(
        self, id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get single observable information object.
        """
        result = self.get_single_dict(id, dataset_id, depth, source, *args, **kwargs)
        if type(result) is NotFoundByIdModel:
            return result
        return ObservableInformationOut(**result)

    def get_observable_information(
        self,
        observable_information_id: Union[str, int],
        dataset_id: Union[int, str],
        depth: int = 0,
        source: str = "",
    ):
        """
        Send request to mongo api to get given observable information
        Args:
            observable_information_id (Union[str, int]): Id of observable information
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.
        Returns:
            Result of request as observable information object
        """
        return self.get_single(observable_information_id, dataset_id, depth, source)

    def delete_observable_information(self, observable_information_id: Union[str, int], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given observable information. Removal is performed by recording service,
        as observable information is embedded within recording
        Args:
            observable_information_id (Union[str, int]): Id of observable information
        Returns:
            Result of request as observable information object
        """
        observable_information = self.get_observable_information(
            observable_information_id,
            dataset_id
        )
        if type(observable_information) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=observable_information_id,
                errors={"errors": "observable information not found"},
            )
        return self.recording_service.remove_observable_information(
            observable_information, dataset_id
        )

    def update_observable_information_relationships(
        self,
        observable_information_id: Union[str, int],
        observable_information: ObservableInformationIn,
        dataset_id: Union[int, str],
    ):
        """
        Send request to mongo api to update given observable information
        Args:
            observable_information_id (Union[str, int]): Id of observable information
            observable_information (BasicObservableInformationOut): Relationships to update
        Returns:
            Result of request as observable information object
        """
        existing_observable_information = self.get_observable_information(observable_information_id, dataset_id)
        for field, value in observable_information.dict().items():
            setattr(existing_observable_information, field, value)

        return self.recording_service.update_observable_information(
            observable_information_id, existing_observable_information.dict(), dataset_id
        )

    def _add_related_documents(
        self,
        observable_information: dict,
        dataset_id: Union[int, str],
        depth: int,
        source: str,
        recording: dict,
    ):
        """Recording is taken from previous get query"""
        if depth > 0:
            self._add_related_time_series(observable_information, dataset_id, depth, source)
            self._add_related_modalities(observable_information, dataset_id, depth, source)
            self._add_related_life_activities(observable_information, dataset_id, depth, source)
            self._add_recording(observable_information, dataset_id, depth, source, recording)

    def _add_recording(
        self, observable_information: dict, dataset_id: Union[int, str], depth: int, source: str, recording: dict
    ):
        """Recording has already been added related documents"""
        if source != Collections.RECORDING:
            observable_information["recording"] = recording

    def _add_related_modalities(
        self, observable_information: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_modality = observable_information["modality_id"] is not None
        if source != Collections.MODALITY and has_related_modality:
            observable_information["modality"] = self.modality_service.get_single_dict(
                observable_information["modality_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.OBSERVABLE_INFORMATION,
            )

    def _add_related_life_activities(
        self, observable_information: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_la = observable_information["life_activity_id"] is not None
        if source != Collections.LIFE_ACTIVITY and has_related_la:
            observable_information[
                "life_activity"
            ] = self.life_activity_service.get_single_dict(
                observable_information["life_activity_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.OBSERVABLE_INFORMATION,
            )

    def _add_related_time_series(
        self, observable_information: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        if source != Collections.TIME_SERIES:
            observable_information[
                "timeSeries"
            ] = self.time_series_service.get_time_series_for_observable_information(
                observable_information_id=observable_information["id"],
                dataset_id=dataset_id,
                depth=depth - 1,
                source=Collections.OBSERVABLE_INFORMATION,
            )

    @staticmethod
    def _get_recording_projection(query):
        return {
            "observable_informations": {"$elemMatch": query} if query else 1,
            "additional_properties": 1,
            "participation_id": 1,
            "registered_channel_id": 1,
        }
