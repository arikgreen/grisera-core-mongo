from typing import Union
from bson import ObjectId
from mongo_service.collection_mapping import Collections
from grisera import (
    BasicObservableInformationOut,
    ObservableInformationOut, RecordingRelationIn,
)
from grisera import (
    ObservableInformationIn,
)
from mongo_service.service_mixins import (
    GenericMongoServiceMixin,
)
from grisera import RecordingService
from grisera import (
    RecordingPropertyIn,
    RecordingIn,
    BasicRecordingOut,
    RecordingOut,
    RecordingsOut,
)
from grisera import NotFoundByIdModel
from mongo_service import MongoApiService


class RecordingServiceMongoDB(RecordingService, GenericMongoServiceMixin):
    """
    Object to handle logic of recording requests. There are also observable information methods,
    as observable information documents are embedded within recording documents.
f
    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    participation_service (ParticipationService): Service to send participation requests
    registered_channel_service(RegisteredChannelService): Service to send registered channel requests
    observable_information_service(ObservableInformationService): Service to send observable information requests
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = RecordingOut
        self.registered_channel_service = None
        self.observable_information_service = None
        self.participation_service = None

    def save_recording(self, recording: RecordingIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new recording document

        Args:
            recording (RecordingIn): Recording to be added

        Returns:
            Result of request as recording object
        """
        participation = self.participation_service.get_participation(
            recording.participation_id, dataset_id
        )
        participation_exists = type(participation) is not NotFoundByIdModel
        if recording.participation_id is not None and not participation_exists:
            return RecordingOut(errors={"errors": "given participation does not exist"})

        related_registered_channel = (
            self.registered_channel_service.get_registered_channel(
                recording.registered_channel_id,
                dataset_id
            )
        )
        registered_channel_exists = type(related_registered_channel) is not NotFoundByIdModel
        if (
            recording.registered_channel_id is not None
            and not registered_channel_exists
        ):
            return RecordingOut(
                errors={"errors": "given registered channel does not exist"}
            )

        return self.create(recording, dataset_id)

    def get_recordings(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get recordings
        Returns:
            Result of request as list of recordings objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        results = [BasicRecordingOut(**result) for result in results_dict]
        return RecordingsOut(recordings=results)

    def get_recording(
        self, recording_id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given recording. This method uses mixin get implementation.

        Args:
            recording_id (Union[str, int]): Id of registered channel
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.
                          i.e. if for this service, if source="registered_channel", it means that this method was invoked
                          from registered channel service, so registered channel model will not be fetched, as it is already
                          in response.

        Returns:
            Result of request as registered channel object
        """
        return self.get_single(recording_id, dataset_id, depth, source)

    def delete_recording(self, recording_id: Union[str, int], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given recording

        Args:
            recording_id (Union[str, int]): Id of recording

        Returns:
            Result of request as recording object
        """
        return self.delete(recording_id, dataset_id)

    def update_recording(
        self, recording_id: Union[str, int], recording: RecordingPropertyIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given recording

        Args:
            recording_id (Union[str, int]): Id of participant state
            recording (RecordingPropertyIn): Properties to update

        Returns:
            Result of request as participant state object
        """
        existing_recording = self.get_recording(recording_id, dataset_id)

        for field, value in recording.dict().items():
            setattr(existing_recording, field, value)

        return self.update(recording_id, existing_recording, dataset_id)

    def update_recording_relationships(
        self, recording_id: Union[str, int], recording: RecordingRelationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given recording

        Args:
            recording_id (Union[str, int]): Id of recording
            recording (RecordingIn): Relationships to update

        Returns:
            Result of request as recording object
        """
        existing_recording = self.get_recording(recording_id, dataset_id)

        if type(existing_recording) is NotFoundByIdModel:
            return existing_recording

        related_registered_channel = (
            self.registered_channel_service.get_registered_channel(
                recording.registered_channel_id,
                dataset_id
            )
        )
        if type(related_registered_channel) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=recording.registered_channel_id,
                errors={"errors": "registered channel does not exist"},
            )

        related_participation = self.participation_service.get_participation(
            recording.participation_id,
            dataset_id
        )
        if type(related_participation) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=recording.registered_channel_id,
                errors={"errors": "participant does not exist"},
            )

        for field, value in recording.dict().items():
            setattr(existing_recording, field, value)

        return self.update(recording_id, existing_recording, dataset_id)

    def add_observable_information(
        self, observable_information: ObservableInformationIn, dataset_id: Union[int, str]
    ):
        """
        Add observable information to recording. Observable information is embedded in related recording.

        Args:
            observable_information (ObservableInformationIn): observable information to add

        Returns:
            Added observable information as BasicObservableInformationOut object
        """
        observable_information_dict = observable_information.dict()
        observable_information_dict["id"] = str(ObjectId())
        observable_information = ObservableInformationOut(**observable_information_dict)

        recording_id = observable_information.recording_id
        recording = self.get_single_dict(recording_id, dataset_id)
        observable_informations = recording.get(Collections.OBSERVABLE_INFORMATION, [])
        if observable_informations is None:
            observable_informations = []
        observable_informations.append(observable_information)
        recording[Collections.OBSERVABLE_INFORMATION] = observable_informations

        self.update(recording_id, RecordingOut(**recording), dataset_id)
        return ObservableInformationOut(**observable_information_dict)

    def update_observable_information(
        self,
        observable_information_id: Union[int, str],
        observable_information_dict: dict,
        dataset_id: Union[int, str]
    ):
        """
        Edit observable information in recording. Observable information is embedded in related recording.

        Args:
            observable_information_id (Union[int, str]): id of observable information that is to be updated
            observable_information_dict (dict): new version of observable information

        Returns:
            Updated observable information
        """
        self.remove_observable_information(ObservableInformationOut(**observable_information_dict), dataset_id)
        recording_id = observable_information_dict["recording_id"]
        recording = self.get_single_dict(recording_id, dataset_id)
        if type(recording) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=observable_information_id,
                errors={
                    "errors": "recording related to given observable information not found"
                },
            )

        observable_informations = recording[Collections.OBSERVABLE_INFORMATION]
        observable_informations.append(ObservableInformationOut(**observable_information_dict))
        self.update(recording_id, RecordingOut(**recording), dataset_id)
        return ObservableInformationOut(**observable_information_dict)

    def remove_observable_information(
        self, observable_information: ObservableInformationOut, dataset_id: Union[int, str]
    ):
        """
        Remove observable information from recording. Observable information is embedded in related recording.

        Args:
            observable_information (ObservableInformationOut): observable information to remove

        Returns:
            Removed observable information
        """
        observable_information_old = self.observable_information_service.get_observable_information(observable_information.id, dataset_id)
        recording_old_id = observable_information_old.recording_id
        recording_old = self.get_single_dict(recording_old_id, dataset_id)
        if type(recording_old) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=observable_information.id,
                errors={
                    "errors": "recording related to given observable information not found"
                },
            )


        to_remove_index = self._get_observable_information_index_from_recording(
            recording_old, observable_information.id
        )
        if to_remove_index is None:
            return NotFoundByIdModel(
                id=observable_information.id,
                errors={"errors": "observable information not found"},
            )
        del recording_old[Collections.OBSERVABLE_INFORMATION][to_remove_index]

        self.update(recording_old_id, RecordingOut(**recording_old), dataset_id)
        return observable_information

    def _add_related_documents(self, recording: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_registered_channel(recording, dataset_id, depth, source)
            self._add_related_participation(recording, dataset_id, depth, source)
            self._add_related_observable_informations(recording, dataset_id, depth, source)

    def _add_related_registered_channel(self, recording: dict, dataset_id: Union[int, str], depth: int, source: str):
        has_related_rc = recording["registered_channel_id"] is not None
        if source != Collections.REGISTERED_CHANNEL and has_related_rc:
            recording[
                "registered_channel"
            ] = self.registered_channel_service.get_single_dict(
                recording["registered_channel_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.RECORDING,
            )

    def _add_related_participation(self, recording: dict, dataset_id: Union[int, str], depth: int, source: str):
        has_participation = recording["participation_id"] is not None
        if source != Collections.PARTICIPATION and has_participation:
            recording["participation"] = self.participation_service.get_single_dict(
                recording["participation_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.RECORDING,
            )

    def _add_related_observable_informations(
        self, recording: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        """
        Observable information is embedded within recording model
        """
        has_observable_informations = (
            Collections.OBSERVABLE_INFORMATION in recording and recording[Collections.OBSERVABLE_INFORMATION] is not None
        )
        if source != Collections.OBSERVABLE_INFORMATION and has_observable_informations:
            for oi in recording[Collections.OBSERVABLE_INFORMATION]:
                self.observable_information_service._add_related_documents(
                    oi, dataset_id, depth - 1, Collections.RECORDING, recording
                )

    def _get_observable_information_index_from_recording(
        self, recording_dict: dict, observable_information_id: Union[str, int]
    ):
        """
        Observable information is embedded within recording model
        """
        observable_informations = recording_dict[Collections.OBSERVABLE_INFORMATION]
        return next(
            (
                i
                for i, oi in enumerate(observable_informations)
                if ObjectId(oi["id"]) == ObjectId(observable_information_id)
            ),
            None,
        )
